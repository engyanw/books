# -*- coding: utf-8 -*-
"""#4 SIEM 导出端点 回归。

验证 GET /api/admin/audit/export?fmt=... 输出 SIEM 采集格式：
  - fmt=cef：每行 CEF:0|md-docs|audit|1.0|<action>|...|3|ts=... user=... detail=...
  - fmt=jsonl：每行一个紧凑 JSON（application/x-ndjson），字段齐全。
  - fmt=syslog：PRI<37> 行，含 action/user/detail。
  - 非管理员 403；非法 fmt 回退 json（200）。
"""
import os, shutil, tempfile, json
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="siem_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"

import main  # noqa: E402


def _line(s):
    s = s.strip()
    return s.splitlines()


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    import asyncio
    async def _promote():
        async with main._registry_transaction() as db:
            await db.execute("UPDATE users SET is_admin=1 WHERE username=?", ("admin",))
    asyncio.run(_promote())
    t = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 触发若干审计（创建文档 + admin 动作）
    c.post("/api/docs", headers=h, json={"title": "t", "content": "# body"})
    asyncio.run(main._audit("admin-user", None, "user.login", "user", "u1", "from 1.2.3.4"))
    # detail 含换行/竖线，验证转义
    asyncio.run(main._audit("admin-user", None, "doc.update", "doc", "d1", "line1\nline2|pipe"))

    # --- CEF ---
    r = c.get("/api/admin/audit/export?fmt=cef", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/plain"), r.headers
    assert "audit.cef" in r.headers["content-disposition"], r.headers
    lines = _line(r.text)
    assert len(lines) >= 1
    assert lines[0].startswith("CEF:0|md-docs|audit|1.0|"), lines[0]
    # 竖线/换行被转义：CEF 行不应被 detail 内的 \n / | 撑断
    assert all("\n" not in ln for ln in lines), "CEF 行内不应含原始换行"
    # detail 里的换行被转成 \\n
    assert any("line1\\nline2" in ln for ln in lines), lines

    # --- JSONL ---
    r = c.get("/api/admin/audit/export?fmt=jsonl", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/x-ndjson"), r.headers
    lines = _line(r.text)
    assert len(lines) >= 1
    obj = json.loads(lines[0])
    assert {"id", "ts", "user_id", "action", "detail"} <= set(obj.keys()), obj
    # 每行都是合法 JSON
    for ln in lines:
        json.loads(ln)

    # --- Syslog ---
    r = c.get("/api/admin/audit/export?fmt=syslog", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/syslog"), r.headers
    lines = _line(r.text)
    assert len(lines) >= 1
    assert lines[0].startswith("<37>"), lines[0]
    assert "md-docs[audit]" in lines[0], lines[0]

    # --- 非管理员 403 ---
    c.post("/api/auth/register", json={"username": "plain", "password": "p@ssw0rd"})
    pt = c.post("/api/auth/login", json={"username": "plain", "password": "p@ssw0rd"}).json()["token"]
    ph = {"Authorization": f"Bearer {pt}"}
    r = c.get("/api/admin/audit/export?fmt=cef", headers=ph)
    assert r.status_code == 403, r.text

    # --- 非法 fmt 回退 json（200，数组）---
    r = c.get("/api/admin/audit/export?fmt=bogus", headers=h)
    assert r.status_code == 200, r.text
    arr = r.json()
    assert isinstance(arr, list) and len(arr) >= 1, arr

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
