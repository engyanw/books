# -*- coding: utf-8 -*-
"""#5 配额与计量阻断 回归（验证已存在能力，锁紧行为）。

核查确认：AI 配额超限 429（_ai_quota_check）、存储配额超限 429
（_doc_quota_check_user）、用量端点 /api/usage 返回 count/max。本测试
锁定这些既有契约，防止回归。
"""
import os, shutil, tempfile, asyncio
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="quota_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"
os.environ["AI_USER_DAILY_QUOTA"] = "1"          # 每日 1 次
os.environ["USER_MAX_DOCS"] = "2"                 # 最多 2 篇
os.environ["USER_MAX_STORAGE_BYTES"] = "1000000"  # 1MB

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    me = c.get("/api/auth/me", headers=h).json()
    uid = me["user_id"]

    # 清掉注册时播种的示例文档，得到干净配额基线
    async def _clean_docs():
        async with main._db_transaction(uid) as db:
            await db.execute("UPDATE documents SET deleted_at=? WHERE deleted_at IS NULL", (main._utcnow_iso(),))
    asyncio.run(_clean_docs())

    # --- 1) AI 配额：预置 1 次用量 → 配额超限返回错误串 ---
    asyncio.run(main._ai_usage_inc(uid, None, 1))
    err = asyncio.run(main._ai_quota_check(uid, None))
    assert err and "配额上限" in err, err
    # ai_chat 端点：配额检查在 config 查询之前，超限直接 429（不依赖 AI 上游/配置）
    r = c.post("/api/ai/chat", headers=h, json={"config_id": "x", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 429, (r.status_code, r.text)

    # --- 2) 存储配额：USER_MAX_DOCS=2，第 3 篇被拒 ---
    c.post("/api/docs", headers=h, json={"title": "d1", "content": "# a"})
    c.post("/api/docs", headers=h, json={"title": "d2", "content": "# b"})
    r = c.post("/api/docs", headers=h, json={"title": "d3", "content": "# c"})
    assert r.status_code == 429, (r.status_code, r.text)
    assert "上限" in r.json().get("detail", ""), r.text

    # --- 3) /api/usage 返回 count 与 max ---
    r = c.get("/api/usage", headers=h)
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["docs"]["count"] == 2 and u["docs"]["max"] == 2, u
    assert u["ai_today"]["max"] == 1, u
    # 个人用量结构中应含 storage max
    assert u["storage"]["max"] == 1000000, u

    # --- 4) 未设配额时（0=不限制）放行：新建进程模拟——这里仅断言函数语义 ---
    # _ai_quota_check 在 quota=0 时返回 None（不限）
    main.AI_USER_DAILY_QUOTA = 0
    assert asyncio.run(main._ai_quota_check(uid, None)) is None

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
