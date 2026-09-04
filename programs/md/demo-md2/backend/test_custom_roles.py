# -*- coding: utf-8 -*-
"""P2-20 自定义角色 + 权限矩阵：CRUD 角色与可配置权限，权限门控生效。"""
import os, tempfile, shutil
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="roles_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def reg(c, u):
    c.post("/api/auth/register", json={"username": u, "password": "pw123456"})
    return c.post("/api/auth/login", json={"username": u, "password": "pw123456"}).json()["token"]


with TestClient(main.app) as c:
    ta = reg(c, "alice")
    tb = reg(c, "bob")
    ha = {"Authorization": f"Bearer {ta}"}
    hb = {"Authorization": f"Bearer {tb}"}

    tid = c.post("/api/teams", json={"name": "Eng"}, headers=ha).json()["team_id"]

    # 1) 默认 4 个内建角色，owner 拥有全部权限
    roles = c.get(f"/api/teams/{tid}/roles", headers=ha).json()
    names = {r["role"] for r in roles["items"]}
    assert {"viewer", "member", "admin", "owner"} <= names, names
    owner_role = next(r for r in roles["items"] if r["role"] == "owner")
    assert set(owner_role["permissions"]) == set(roles["available_permissions"]), owner_role

    # 2) 创建自定义角色 auditor（review.decide + doc.publish）
    r = c.post(f"/api/teams/{tid}/roles", json={"role": "auditor", "permissions": ["review.decide", "doc.publish"]}, headers=ha)
    assert r.status_code == 201, r.text
    assert set(r.json()["permissions"]) == {"doc.publish", "review.decide"}

    # 3) 不能创建与内建同名角色
    assert c.post(f"/api/teams/{tid}/roles", json={"role": "admin", "permissions": []}, headers=ha).status_code == 400

    # 4) 非 owner 不能管理角色（bob 非 member）
    assert c.post(f"/api/teams/{tid}/roles", json={"role": "x", "permissions": []}, headers=hb).status_code == 403

    # 5) 更新内建 member 矩阵：剥夺 member.invite（默认 member 本就没有，验证写入生效）
    upd = c.put(f"/api/teams/{tid}/roles/member", json={"role": "member", "permissions": ["doc.create", "doc.edit"]}, headers=ha)
    assert upd.status_code == 200, upd.text
    assert set(upd.json()["permissions"]) == {"doc.create", "doc.edit"}
    # 重新读回确认持久化
    member_now = next(r for r in c.get(f"/api/teams/{tid}/roles", headers=ha).json()["items"] if r["role"] == "member")
    assert set(member_now["permissions"]) == {"doc.create", "doc.edit"}

    # 6) owner 矩阵不可改
    assert c.put(f"/api/teams/{tid}/roles/owner", json={"role": "owner", "permissions": []}, headers=ha).status_code == 400

    # 7) 给 bob 指派自定义角色 auditor 并验证权限门控
    c.post(f"/api/teams/{tid}/members", json={"username": "bob", "role": "auditor"}, headers=ha)
    # auditor 没有 member.invite → 邀请被拒
    assert c.post(f"/api/teams/{tid}/members", json={"username": "alice", "role": "member"}, headers=hb).status_code == 403

    # 8) 给 auditor 增加 member.invite 后 bob 可邀请
    c.put(f"/api/teams/{tid}/roles/auditor", json={"role": "auditor", "permissions": ["member.invite"]}, headers=ha)
    tc = reg(c, "carol")
    # bob 现在可邀请 carol（按用户名）
    inv = c.post(f"/api/teams/{tid}/members", json={"username": "carol", "role": "viewer"}, headers=hb)
    assert inv.status_code == 201, inv.text

    # 9) 不能删除内建角色
    assert c.delete(f"/api/teams/{tid}/roles/admin", headers=ha).status_code == 400
    # 仍有成员持有 auditor → 不能删
    assert c.delete(f"/api/teams/{tid}/roles/auditor", headers=ha).status_code == 409
    # 先把 bob 改回 member 再删 auditor
    bob_uid = c.get("/api/auth/me", headers=hb).json()["user_id"]
    assert c.put(f"/api/teams/{tid}/members/{bob_uid}?role=member", headers=ha).status_code == 200
    assert c.delete(f"/api/teams/{tid}/roles/auditor", headers=ha).status_code == 200
    # 再删已不存在的角色 → 404
    assert c.delete(f"/api/teams/{tid}/roles/auditor", headers=ha).status_code == 404

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
