# -*- coding: utf-8 -*-
"""P0-3：时效授权（ACL 过期）。"""
import os, shutil, tempfile, time
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="acl_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    did = c.post("/api/docs", json={"title": "doc.md", "content": "secret"}, headers=h).json()["doc_id"]

    # 创建 Guest 账号
    c.post("/api/guests", json={"username": "guest1", "password": "p@ssw0rd"}, headers=h)

    # 无过期 ACL
    r = c.put(f"/api/docs/{did}/acl?target_username=guest1&permission=read", headers=h)
    assert r.status_code == 200 and r.json().get("expires_at") is None, r.text

    # 过期 1 天
    r = c.put(f"/api/docs/{did}/acl?target_username=guest1&permission=read&expires_days=1", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["expires_at"] is not None, r.json()

    # Guest 登录 + 访问文档（未过期）
    tg = c.post("/api/auth/login", json={"username": "guest1", "password": "p@ssw0rd"}).json()["token"]
    hg = {"Authorization": f"Bearer {tg}"}
    owner_uid = c.get("/api/auth/me", headers=h).json()["user_id"]
    r = c.get(f"/api/guest/docs/{owner_uid}/{did}", headers=hg)
    assert r.status_code == 200 and r.json()["content"] == "secret", r.text

    # 手动设置已过期：直接改 DB
    import sqlite3 as _s
    udb = os.path.join(TMP, "users", c.get("/api/auth/me", headers=h).json()["user_id"], "docs.db")
    conn = _s.connect(udb)
    conn.execute("UPDATE doc_acl SET expires_at='2020-01-01T00:00:00+00:00' WHERE doc_id=?", (did,))
    conn.commit(); conn.close()

    # Guest 访问 → 403 过期
    r = c.get(f"/api/guest/docs/{c.get('/api/auth/me', headers=h).json()['user_id']}/{did}", headers=hg)
    assert r.status_code == 403 and "过期" in r.json()["detail"], r.text

    # Guest 文档列表不再包含已过期（guest_get_doc 拦截；list 不检查但访问被拒）

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
