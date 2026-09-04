# -*- coding: utf-8 -*-
"""#2 出站邮件/通知摘要（每日未读汇总）回归。

SMTP 投递能力已存在（_send_email/email_templates），但缺"每日未读通知汇总"。
本测试验证新增的摘要链路：
  1. _send_digest_to_user：有未读 + 配置 SMTP + 用户有 email → 渲染 notification_digest 并投递。
  2. 无未读 → sent=False reason=no_unread；无 SMTP → reason=smtp_not_configured；无 email → no_email。
  3. _digest_scan_once：扫描所有有未读通知的用户，逐个投递。
  4. POST /api/notifications/digest/send（自助触发）与 POST /api/admin/notifications/digest（管理员全局）。
SMTP 通过 monkeypatch 替换为内存捕获，不产生真实外发。
"""
import os, shutil, tempfile, asyncio
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="digest_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"
os.environ["EMAIL_DIGEST_ENABLED"] = "1"
os.environ["EMAIL_DIGEST_INTERVAL_SECONDS"] = "999999"  # 不让后台循环自行触发
os.environ["EMAIL_DIGEST_LOOKBACK_DAYS"] = "0"
os.environ["SMTP_HOST"] = "smtp.test.local"
os.environ["SMTP_FROM"] = "noreply@test.local"

import main  # noqa: E402

# --- 内存化 SMTP：捕获投递 ---
sent_mails = []


async def _fake_send_email(to, subject, body):
    sent_mails.append({"to": to, "subject": subject, "body": body})
    return True


main._send_email = _fake_send_email  # email_templates 运行时 from main import _send_email 会取到这个


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    me = c.get("/api/auth/me", headers=h).json()
    uid = me["user_id"]

    # 给用户补 email
    async def _set_email():
        async with main._registry_transaction() as db:
            await db.execute("UPDATE users SET email=? WHERE user_id=?", ("u@test.local", uid))
    asyncio.run(_set_email())

    # 造 2 条未读 + 1 条已读
    asyncio.run(main._notify(uid, "mention", detail="hello @you", link="/x"))
    asyncio.run(main._notify(uid, "review.request", detail="请评审文档 D1", link="/?review=r1"))
    asyncio.run(main._notify(uid, "share.access", detail="文档被访问"))
    # 把第三条标已读
    async def _mark_last_read():
        async with main._registry_transaction() as db:
            await db.execute("UPDATE notifications SET is_read=1 WHERE id=(SELECT MAX(id) FROM notifications WHERE user_id=?)", (uid,))
    asyncio.run(_mark_last_read())

    # --- 1) 单用户摘要：投递成功 ---
    sent_mails.clear()
    res = asyncio.run(main._send_digest_to_user(uid))
    assert res["sent"] is True, res
    assert res["unread"] == 2, res
    assert len(sent_mails) == 1, sent_mails
    mail = sent_mails[0]
    assert mail["to"] == "u@test.local", mail
    assert "未读" in mail["subject"], mail
    assert "hello @you" in mail["body"], mail
    assert "请评审文档 D1" in mail["body"], mail
    print("digest send OK:", mail["subject"])

    # --- 2) 无未读 → no_unread ---
    asyncio.run(main._notify(uid, "x", detail="t"))  # 再加一条未读，确保不是 0
    # 全部标已读
    async def _read_all():
        async with main._registry_transaction() as db:
            await db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
    asyncio.run(_read_all())
    sent_mails.clear()
    res = asyncio.run(main._send_digest_to_user(uid))
    assert res["sent"] is False and res["reason"] == "no_unread", res
    assert sent_mails == [], sent_mails

    # --- 3) 无 SMTP → smtp_not_configured（再造未读后临时清空 SMTP_HOST）---
    asyncio.run(main._notify(uid, "mention", detail="unread again"))
    saved_smtp = main.SMTP_HOST
    main.SMTP_HOST = ""
    try:
        res = asyncio.run(main._send_digest_to_user(uid))
        assert res["sent"] is False and res["reason"] == "smtp_not_configured", res
    finally:
        main.SMTP_HOST = saved_smtp

    # --- 4) 无 email → no_email（清空用户 email）---
    async def _clear_email():
        async with main._registry_transaction() as db:
            await db.execute("UPDATE users SET email='' WHERE user_id=?", (uid,))
    asyncio.run(_clear_email())
    res = asyncio.run(main._send_digest_to_user(uid))
    assert res["sent"] is False and res["reason"] == "no_email", res

    # 恢复 email 供后续端点测试
    async def _restore_email():
        async with main._registry_transaction() as db:
            await db.execute("UPDATE users SET email=? WHERE user_id=?", ("u@test.local", uid))
    asyncio.run(_restore_email())

    # --- 5) _digest_scan_once 扫描所有有未读用户 ---
    sent_mails.clear()
    results = asyncio.run(main._digest_scan_once())
    assert any(r["user_id"] == uid and r["sent"] for r in results), results
    assert len(sent_mails) >= 1, sent_mails

    # --- 6) 自助端点 POST /api/notifications/digest/send ---
    r = c.post("/api/notifications/digest/send", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sent"] is True, body

    # --- 7) 管理员全局触发：非管理员 403，管理员 200 ---
    r = c.post("/api/admin/notifications/digest", headers=h)
    assert r.status_code == 403, r.text
    async def _promote():
        async with main._registry_transaction() as db:
            await db.execute("UPDATE users SET is_admin=1 WHERE user_id=?", (uid,))
    asyncio.run(_promote())
    sent_mails.clear()
    r = c.post("/api/admin/notifications/digest", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attempted"] >= 1 and body["sent"] >= 1, body

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
