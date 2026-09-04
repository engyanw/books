# -*- coding: utf-8 -*-
"""P2-10 ACL 角色粒度：commenter/reviewer 细粒度角色——评审/评论可用，编辑被拒。
owner/member 行为不回归（member 仍可创建/编辑/删除团队文档）。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="role_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "com", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "rev", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "mem", "password": "p@ssw0rd"})
    to = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    tc = c.post("/api/auth/login", json={"username": "com", "password": "p@ssw0rd"}).json()["token"]
    tr = c.post("/api/auth/login", json={"username": "rev", "password": "p@ssw0rd"}).json()["token"]
    tm = c.post("/api/auth/login", json={"username": "mem", "password": "p@ssw0rd"}).json()["token"]
    ho = {"Authorization": f"Bearer {to}"}

    # owner 建团队（自动播种内建角色，含 commenter/reviewer）
    tid = c.post("/api/teams", headers=ho, json={"name": "T"}).json()["team_id"]
    # 分派细粒度角色
    assert c.post(f"/api/teams/{tid}/members", headers=ho, json={"username": "com", "role": "commenter"}).status_code == 201
    assert c.post(f"/api/teams/{tid}/members", headers=ho, json={"username": "rev", "role": "reviewer"}).status_code == 201
    assert c.post(f"/api/teams/{tid}/members", headers=ho, json={"username": "mem", "role": "member"}).status_code == 201

    hc = {"Authorization": f"Bearer {tc}"}
    hr = {"Authorization": f"Bearer {tr}"}
    hm = {"Authorization": f"Bearer {tm}"}

    # owner 先建一篇团队文档供编辑测试
    did = c.post(f"/api/teams/{tid}/docs", headers=ho, json={"title": "d", "content": "x"}).json()["doc_id"]

    # commenter 不能创建/编辑团队文档（缺 doc.create/doc.edit）
    assert c.post(f"/api/teams/{tid}/docs", headers=hc, json={"title": "x", "content": "y"}).status_code == 403
    assert c.put(f"/api/teams/{tid}/docs/{did}", headers=hc, json={"content": "edit"}).status_code == 403
    # reviewer 同样不能创建/编辑
    assert c.post(f"/api/teams/{tid}/docs", headers=hr, json={"title": "x", "content": "y"}).status_code == 403
    assert c.put(f"/api/teams/{tid}/docs/{did}", headers=hr, json={"content": "edit"}).status_code == 403

    # member 仍可创建/编辑/删除（不回归）
    assert c.post(f"/api/teams/{tid}/docs", headers=hm, json={"title": "m", "content": "z"}).status_code == 201
    assert c.put(f"/api/teams/{tid}/docs/{did}", headers=hm, json={"content": "edited"}).status_code == 200
    did2 = c.post(f"/api/teams/{tid}/docs", headers=hm, json={"title": "del", "content": "z"}).json()["doc_id"]
    assert c.delete(f"/api/teams/{tid}/docs/{did2}", headers=hm).status_code == 200

    # commenter/reviewer 可读团队文档列表（viewer+ 即可，二者 rank≥viewer）
    assert c.get(f"/api/teams/{tid}/docs", headers=hc).status_code == 200
    assert c.get(f"/api/teams/{tid}/docs", headers=hr).status_code == 200

    # 角色矩阵可查：commenter/reviewer 内建角色存在
    roles = c.get(f"/api/teams/{tid}/roles", headers=ho).json()["items"]
    rmap = {r["role"]: set(r["permissions"]) for r in roles}
    assert "commenter" in rmap and "reviewer" in rmap, rmap.keys()
    assert "doc.comment" in rmap["commenter"] and "doc.edit" not in rmap["commenter"], rmap["commenter"]
    assert "review.decide" in rmap["reviewer"] and "doc.edit" not in rmap["reviewer"], rmap["reviewer"]

print("ALL PASSED")
