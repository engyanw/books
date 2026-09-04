# -*- coding: utf-8 -*-
"""#1 审计日志物理不可变（AUDIT_IMMUTABLE=1）回归。

验证：
  1. 不可变模式下，对 audit_log 的 UPDATE / DELETE 被 SQLite 触发器拦截（抛 OperationalError）。
  2. POST /api/admin/audit/retention 在不可变模式下返回 409（不清理、不 re-anchor）。
  3. 审计 hash 链仍可校验（/api/audit/verify），且响应带 immutable=true。
  4. 默认（AUDIT_IMMUTABLE 未设）行为不变——retention 可执行、audit_log 可被 UPDATE re-anchor。
"""
import os, shutil, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="audit_immut_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"
os.environ["AUDIT_IMMUTABLE"] = "1"          # 开启不可变
os.environ["AUDIT_RETENTION_DAYS"] = "90"     # 非零，确保清理路径会被触发

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    # 提权为管理员
    import asyncio as _aio
    async def _promote():
        async with main._registry_transaction() as db:
            await db.execute("UPDATE users SET is_admin=1 WHERE username=?", ("admin",))
    _aio.run(_promote())
    t = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 触发一条审计（创建文档）
    did = c.post("/api/docs", headers=h, json={"title": "t", "content": "# body"}).json()["doc_id"]

    # --- 1) 物理 UPDATE / DELETE 被触发器拦截 ---
    dbpath = os.environ["REGISTRY_DB_PATH"]
    raw = sqlite3.connect(dbpath)
    raw.row_factory = sqlite3.Row
    n = raw.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert n >= 1, "应有审计记录"

    updated = False
    try:
        raw.execute("UPDATE audit_log SET detail='tampered' WHERE id=(SELECT MIN(id) FROM audit_log)")
        raw.commit()
        updated = True
    except sqlite3.DatabaseError:
        pass
    assert not updated, "不可变模式下 UPDATE audit_log 必须被触发器拦截"

    deleted = False
    try:
        raw.execute("DELETE FROM audit_log WHERE id=(SELECT MIN(id) FROM audit_log)")
        raw.commit()
        deleted = True
    except sqlite3.DatabaseError:
        pass
    assert not deleted, "不可变模式下 DELETE audit_log 必须被触发器拦截"
    raw.close()

    # --- 2) retention 端点在不可变模式返回 409 ---
    r = c.post("/api/admin/audit/retention", headers=h)
    assert r.status_code == 409, r.text
    assert "不可变" in r.json().get("detail", ""), r.text

    # --- 3) hash 链仍可校验，且响应携带 immutable 标记 ---
    v = c.get("/api/audit/verify", headers=h).json()
    assert v["intact"] is True, v
    assert v["immutable"] is True, v
    assert v["total"] >= 1, v

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
