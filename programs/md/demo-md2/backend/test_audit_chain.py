# -*- coding: utf-8 -*-
"""P1-6：审计日志 hash 链防篡改 + 校验。"""
import os, shutil, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="audit_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "au", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "au", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 触发一些审计日志（register 有 _audit，create_team 有 _audit）
    c.post("/api/docs", json={"title": "a.md", "content": "x"}, headers=h)
    c.post("/api/teams", json={"name": "T"}, headers=h)
    c.post("/api/docs", json={"title": "b.md", "content": "y"}, headers=h)

    # 设为 admin 才能调 verify
    conn = sqlite3.connect(os.path.join(TMP, "registry.db"))
    conn.execute("UPDATE users SET is_admin=1 WHERE username='au'")
    conn.commit(); conn.close()

    # 校验链完整性 → intact
    r = c.get("/api/audit/verify", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    print("verify:", data)
    assert data["intact"] is True and data["broken_count"] == 0, data
    assert data["total"] >= 1, data  # 至少 register 的 _audit

    # 篡改一条记录
    conn = sqlite3.connect(os.path.join(TMP, "registry.db"))
    conn.execute("UPDATE audit_log SET detail='TAMPERED' WHERE id=1")
    conn.commit(); conn.close()

    # 再校验 → broken
    r = c.get("/api/audit/verify", headers=h)
    data = r.json()
    print("after tamper:", data)
    assert data["intact"] is False and data["broken_count"] >= 1, data

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
