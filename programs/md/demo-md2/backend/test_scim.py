# -*- coding: utf-8 -*-
"""B2 回归：SCIM 2.0 用户/组同步。
覆盖：鉴权（SCIM_TOKEN）、Users 增查改停、Groups 增查删、filter。
"""
import os, shutil, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="scim_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["SCIM_TOKEN"] = "scim-secret-123"

import main  # noqa: E402

H = {"Authorization": "Bearer scim-secret-123"}

with TestClient(main.app) as c:
    # 无鉴权 → 401
    assert c.get("/api/scim/v2/Users").status_code == 401
    # 错误 token → 403
    assert c.get("/api/scim/v2/Users", headers={"Authorization": "Bearer wrong"}).status_code == 403

    # 创建 User
    r = c.post("/api/scim/v2/Users", headers=H, json={
        "userName": "alice", "displayName": "Alice Wang",
        "emails": [{"value": "alice@example.com", "primary": True}],
    })
    assert r.status_code == 201, r.text
    alice = r.json()
    assert alice["userName"] == "alice"
    assert alice["displayName"] == "Alice Wang"
    assert alice["emails"][0]["value"] == "alice@example.com"
    alice_id = alice["id"]

    # 重复创建 → 409
    assert c.post("/api/scim/v2/Users", headers=H, json={"userName": "alice"}).status_code == 409

    # GET 单个
    assert c.get(f"/api/scim/v2/Users/{alice_id}", headers=H).json()["userName"] == "alice"

    # 列表 + filter
    c.post("/api/scim/v2/Users", headers=H, json={"userName": "bob", "displayName": "Bob"})
    lst = c.get("/api/scim/v2/Users", headers=H).json()
    assert lst["totalResults"] >= 2, lst
    f = c.get("/api/scim/v2/Users?filter=userName%20eq%20%22bob%22", headers=H).json()
    assert f["totalResults"] == 1 and f["Resources"][0]["userName"] == "bob", f

    # PUT 替换
    put = c.put(f"/api/scim/v2/Users/{alice_id}", headers=H, json={
        "userName": "alice", "displayName": "Alice L", "active": False,
        "emails": [{"value": "alice2@example.com"}],
    }).json()
    assert put["displayName"] == "Alice L"
    assert put["active"] is False
    assert put["emails"][0]["value"] == "alice2@example.com"

    # PATCH 改 active 回 true
    patch = c.patch(f"/api/scim/v2/Users/{alice_id}", headers=H, json={
        "Operations": [{"op": "replace", "path": "active", "value": True}]
    }).json()
    assert patch["active"] is True

    # 停用的用户不能登录（DELETE → active=0）。先设置已知密码以隔离"停用"逻辑
    import sqlite3 as _sql
    conn = _sql.connect(os.path.join(TMP, "registry.db"))
    conn.execute("UPDATE users SET password_hash=? WHERE user_id=?",
                 (main._hash_password("p@ssw0rd"), alice_id))
    conn.commit(); conn.close()
    c.delete(f"/api/scim/v2/Users/{alice_id}", headers=H)
    login = c.post("/api/auth/login", json={"username": "alice", "password": "p@ssw0rd"})
    assert login.status_code == 403, login.text  # 账号已停用

    # Groups
    bob = c.get("/api/scim/v2/Users?filter=userName%20eq%20%22bob%22", headers=H).json()["Resources"][0]
    g = c.post("/api/scim/v2/Groups", headers=H, json={
        "displayName": "Engineering", "members": [{"value": alice_id}, {"value": bob["id"]}],
    }).json()
    assert g["displayName"] == "Engineering"
    assert len(g["members"]) == 2, g
    gid = g["id"]

    assert c.get(f"/api/scim/v2/Groups/{gid}", headers=H).json()["displayName"] == "Engineering"
    assert c.get(f"/api/scim/v2/Groups/{gid}", headers=H).json()["members"] and len(
        c.get(f"/api/scim/v2/Groups/{gid}", headers=H).json()["members"]) == 2

    # 列组
    gl = c.get("/api/scim/v2/Groups", headers=H).json()
    assert gl["totalResults"] >= 1, gl

    # 删组 → 204
    assert c.delete(f"/api/scim/v2/Groups/{gid}", headers=H).status_code == 204
    assert c.get(f"/api/scim/v2/Groups/{gid}", headers=H).status_code == 404

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
