# -*- coding: utf-8 -*-
"""Tier-1 多团队基础：团队/成员/角色/RBAC/审计/管理后台。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="teams_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

def reg(client, u, p):
    r = client.post("/api/auth/register", json={"username": u, "password": p})
    return client.post("/api/auth/login", json={"username": u, "password": p}).json()["token"]

with TestClient(main.app) as c:
    ta = reg(c, "alice", "p@ssw0rd")
    tb = reg(c, "bob", "p@ssw0rd")
    tc = reg(c, "carol", "p@ssw0rd")
    ha, hb, hc = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}, {"Authorization": f"Bearer {tc}"}

    # 1) alice 建团队
    r = c.post("/api/teams", json={"name": "Platform"}, headers=ha)
    assert r.status_code == 201, r.text
    tid = r.json()["team_id"]
    assert r.json()["role"] == "owner"

    # 2) 列我的团队
    teams = c.get("/api/teams", headers=ha).json()["items"]
    assert len(teams) == 1 and teams[0]["name"] == "Platform"

    # 3) 邀请 bob 为 member、carol 为 viewer
    assert c.post(f"/api/teams/{tid}/members", json={"username": "bob", "role": "member"}, headers=ha).status_code == 201
    assert c.post(f"/api/teams/{tid}/members", json={"username": "carol", "role": "viewer"}, headers=ha).status_code == 201
    # 非 admin 不能邀请
    assert c.post(f"/api/teams/{tid}/members", json={"username": "carol", "role": "member"}, headers=hb).status_code == 403

    # 4) 团队详情含成员
    det = c.get(f"/api/teams/{tid}", headers=ha).json()
    assert len(det["members"]) == 3

    # 5) RBAC：carol(viewer) 不能建文档；bob(member) 可以
    assert c.post(f"/api/teams/{tid}/docs", json={"title": "x.md", "content": "hi"}, headers=hc).status_code == 403
    r = c.post(f"/api/teams/{tid}/docs", json={"title": "spec.md", "content": "v1"}, headers=hb)
    assert r.status_code == 201, r.text
    did = r.json()["doc_id"]

    # 6) viewer 可读（需先发布——reader/editor 视图分离后 viewer 只看 published）
    import sqlite3 as _s
    tdb = os.path.join(TMP, "teams", tid, "docs.db")
    conn = _s.connect(tdb); conn.execute("UPDATE documents SET status='published' WHERE doc_id=?", (did,)); conn.commit(); conn.close()
    got = c.get(f"/api/teams/{tid}/docs/{did}", headers=hc)
    assert got.status_code == 200 and got.json()["content"] == "v1"

    # 7) 更新 + 版本
    r = c.put(f"/api/teams/{tid}/docs/{did}", json={"content": "v2", "version": 1}, headers=hb)
    assert r.status_code == 200 and r.json()["version"] == 2

    # 8) 非成员(dave) 访问被拒
    td = reg(c, "dave", "p@ssw0rd"); hd = {"Authorization": f"Bearer {td}"}
    assert c.get(f"/api/teams/{tid}/docs", headers=hd).status_code == 403

    # 9) 审计日志：团队 admin 可查
    aud = c.get(f"/api/audit?team_id={tid}&limit=50", headers=ha).json()["items"]
    actions = [a["action"] for a in aud]
    assert "team.create" in actions and "doc.create" in actions and "team.member.add" in actions, actions
    # viewer 不能查审计
    assert c.get(f"/api/audit?team_id={tid}", headers=hc).status_code == 403

    # 10) 管理后台：alice 默认非 admin -> 403
    assert c.get("/api/admin/users", headers=ha).status_code == 403
    # 直接把 alice 设为 admin（模拟运维）
    import sqlite3
    reg_db = os.path.join(TMP, "registry.db")
    conn = sqlite3.connect(reg_db); conn.execute("UPDATE users SET is_admin=1 WHERE username='alice'"); conn.commit(); conn.close()
    # 现在 alice 可看用户/团队/全局审计
    users = c.get("/api/admin/users", headers=ha).json()["items"]
    assert any(u["username"] == "bob" for u in users)
    teams_all = c.get("/api/admin/teams", headers=ha).json()["items"]
    assert any(t["team_id"] == tid for t in teams_all)
    gaud = c.get("/api/audit?limit=10", headers=ha).json()["items"]
    assert len(gaud) > 0
    # 非 admin 仍 403
    assert c.get("/api/admin/users", headers=hb).status_code == 403

    # 11) 移除成员；owner 不可移除
    assert c.delete(f"/api/teams/{tid}/members/{c.get('/api/auth/me', headers=ha).json()['user_id']}", headers=ha).status_code == 400
    assert c.delete(f"/api/teams/{tid}/members/{c.get('/api/auth/me', headers=hc).json()['user_id']}", headers=ha).status_code == 200

    # 12) 删除团队（owner）
    assert c.delete(f"/api/teams/{tid}", headers=hb).status_code == 403  # bob 非 owner
    assert c.delete(f"/api/teams/{tid}", headers=ha).status_code == 200
    assert c.get("/api/teams", headers=ha).json()["items"] == []

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
