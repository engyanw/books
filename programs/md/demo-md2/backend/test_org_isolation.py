# -*- coding: utf-8 -*-
"""多租户组织隔离：组织内用户/团队仅同组织可见。"""
import os, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="org_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def make_admin(c, name):
    c.post("/api/auth/register", json={"username": name, "password": "pw123456"})
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username=?", (name,))
    conn.commit(); conn.close()
    return c.post("/api/auth/login", json={"username": name, "password": "pw123456"}).json()["token"]


with TestClient(main.app) as c:
    admin_tok = make_admin(c, "root")
    ah = {"Authorization": f"Bearer {admin_tok}"}

    # 创建两个组织
    o1 = c.post("/api/admin/orgs", json={"name": "Acme", "slug": "acme"}, headers=ah).json()
    o2 = c.post("/api/admin/orgs", json={"name": "Globex", "slug": "globex"}, headers=ah).json()
    o1_id, o2_id = o1["org_id"], o2["org_id"]
    assert o1_id != o2_id

    # 注册两组织各一个用户，分配到组织
    c.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})
    c.post("/api/auth/register", json={"username": "bob", "password": "pw123456"})
    c.post("/api/admin/orgs/{}/members".format(o1_id), json={"username": "alice"}, headers=ah)
    c.post("/api/admin/orgs/{}/members".format(o2_id), json={"username": "bob"}, headers=ah)

    alice_tok = c.post("/api/auth/login", json={"username": "alice", "password": "pw123456"}).json()["token"]
    bob_tok = c.post("/api/auth/login", json={"username": "bob", "password": "pw123456"}).json()["token"]
    alice_h = {"Authorization": f"Bearer {alice_tok}"}
    bob_h = {"Authorization": f"Bearer {bob_tok}"}

    # alice 看自己组织 Acme：应见 alice，不见 bob
    r = c.get(f"/api/org/{o1_id}/users", headers=alice_h).json()
    names = {u["username"] for u in r["items"]}
    assert names == {"alice"}, names

    # alice 访问 Globex → 403（租户隔离）
    assert c.get(f"/api/org/{o2_id}/users", headers=alice_h).status_code == 403

    # bob 看 Globex：见 bob 不见 alice
    r2 = c.get(f"/api/org/{o2_id}/users", headers=bob_h).json()
    assert {u["username"] for u in r2["items"]} == {"bob"}, r2

    # 管理员看全部组织
    orgs = c.get("/api/admin/orgs", headers=ah).json()["items"]
    assert {o["name"] for o in orgs} == {"Acme", "Globex"}
    assert next(o for o in orgs if o["name"] == "Acme")["user_count"] == 1

    # 在 Acme 下建团队（通过 alice 建团队，后端应记 org_id=alice 的 org）
    # 现有 POST /api/teams 不带 org_id；这里测组织内团队只读端点
    # 直接 SQL 给 Acme 建个团队带 org_id 验证列表隔离
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    import secrets as _s, time as _t
    tid1 = _s.token_urlsafe(8); now = main._utcnow_iso()
    conn.execute("INSERT INTO teams (team_id, name, slug, owner_user_id, created_at, org_id) VALUES (?,?,?,?,?,?)",
                 (tid1, "AcmeTeam", "acme-team", "x", now, o1_id))
    conn.commit(); conn.close()
    r3 = c.get(f"/api/org/{o1_id}/teams", headers=alice_h).json()
    assert r3["items"][0]["name"] == "AcmeTeam"
    # bob 看不到 Acme 团队
    assert c.get(f"/api/org/{o1_id}/teams", headers=bob_h).status_code == 403

print("ALL PASSED")
