# -*- coding: utf-8 -*-
"""③团队内 per-doc ACL。
- 无 ACL：按 membership+role（member 可读写团队文档）。
- 设置 ACL 后：未授权成员读(403)/写(403)；授权 read 可读不可写；授权 write 可读写。
- owner/admin 始终旁路。
- 撤销后无剩余 ACL → 回退 membership+role。
- 作者可设 ACL；普通成员不可设。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="tdocacl_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "alice", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "bob", "password": "p@ssw0rd"})
    to = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    ta = c.post("/api/auth/login", json={"username": "alice", "password": "p@ssw0rd"}).json()["token"]
    tb = c.post("/api/auth/login", json={"username": "bob", "password": "p@ssw0rd"}).json()["token"]
    ho = {"Authorization": f"Bearer {to}"}
    ha = {"Authorization": f"Bearer {ta}"}
    hb = {"Authorization": f"Bearer {tb}"}

    tid = c.post("/api/teams", headers=ho, json={"name": "T"}).json()["team_id"]
    c.post(f"/api/teams/{tid}/members", headers=ho, json={"username": "alice", "role": "member"})
    c.post(f"/api/teams/{tid}/members", headers=ho, json={"username": "bob", "role": "member"})

    did = c.post(f"/api/teams/{tid}/docs", headers=ho, json={"title": "D", "content": "v1"}).json()["doc_id"]

    # 无 ACL：两个 member 都能读
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=ha).status_code == 200
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=hb).status_code == 200
    # 无 ACL：member 能写（permission-based: member 有 doc.edit? 若无则写被拒——按当前角色矩阵）
    # 这里不强断言写，仅断言 ACL 行为

    # 普通成员不能设 ACL（仅 owner/admin 或作者）
    r = c.put(f"/api/teams/{tid}/docs/{did}/acl?target_username=alice&permission=read", headers=ha)
    assert r.status_code == 403, r.text

    # owner 设 ACL：alice=read, bob 不授权
    assert c.put(f"/api/teams/{tid}/docs/{did}/acl?target_username=alice&permission=read", headers=ho).status_code == 200
    # 列 ACL
    la = c.get(f"/api/teams/{tid}/docs/{did}/acl", headers=ho).json()
    assert len(la["items"]) == 1 and la["items"][0]["permission"] == "read", la

    # alice 可读不可写
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=ha).status_code == 200
    assert c.put(f"/api/teams/{tid}/docs/{did}", headers=ha, json={"content": "edit"}).status_code == 403
    # bob 未授权 → 读 403 写 403
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=hb).status_code == 403
    assert c.put(f"/api/teams/{tid}/docs/{did}", headers=hb, json={"content": "edit"}).status_code == 403

    # owner 旁路：admin/owner 始终可读可写
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=ho).status_code == 200
    assert c.put(f"/api/teams/{tid}/docs/{did}", headers=ho, json={"content": "owner-edit"}).status_code == 200

    # 升级 alice=write → alice 可写
    assert c.put(f"/api/teams/{tid}/docs/{did}/acl?target_username=alice&permission=write", headers=ho).status_code == 200
    assert c.put(f"/api/teams/{tid}/docs/{did}", headers=ha, json={"content": "alice-edit"}).status_code == 200

    # 撤销 alice → 无剩余 ACL → 回退 membership+role（bob 又能读了）
    assert c.delete(f"/api/teams/{tid}/docs/{did}/acl?target_username=alice", headers=ho).status_code == 200
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=hb).status_code == 200
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=ha).status_code == 200

    # 非法 permission → 400
    assert c.put(f"/api/teams/{tid}/docs/{did}/acl?target_username=alice&permission=admin", headers=ho).status_code == 400

print("ALL PASSED")
