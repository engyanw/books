# -*- coding: utf-8 -*-
"""团队文件夹端点 + 团队/个人库隔离回归。

回归点：团队空间下创建的文件夹/文件必须落团队库，不得误写入当前用户个人库。
（历史 bug：前端 saveDraft/rename/delete/move 无视 activeTeamId，且后端无
 /api/teams/{tid}/folders 端点 → 团队文件夹全部落到个人 /api/folders。）
"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="team_folders_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

def reg(client, u, p):
    client.post("/api/auth/register", json={"username": u, "password": p})
    return client.post("/api/auth/login", json={"username": u, "password": p}).json()["token"]

with TestClient(main.app) as c:
    ta = reg(c, "alice", "p@ssw0rd")
    tb = reg(c, "bob", "p@ssw0rd")
    tc = reg(c, "carol", "p@ssw0rd")
    ha, hb, hc = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}, {"Authorization": f"Bearer {tc}"}

    # alice 建团队，邀请 bob=member、carol=viewer
    tid = c.post("/api/teams", json={"name": "Platform"}, headers=ha).json()["team_id"]
    c.post(f"/api/teams/{tid}/members", json={"username": "bob", "role": "member"}, headers=ha)
    c.post(f"/api/teams/{tid}/members", json={"username": "carol", "role": "viewer"}, headers=ha)

    # 1) viewer 不能建文件夹（403）；member 可以建（201）
    assert c.post(f"/api/teams/{tid}/folders", json={"name": "docs", "path": ""}, headers=hc).status_code == 403
    r = c.post(f"/api/teams/{tid}/folders", json={"name": "docs", "path": ""}, headers=hb)
    assert r.status_code == 201, r.text
    fid = r.json()["doc_id"]

    # 2) 同目录重名 → 409
    assert c.post(f"/api/teams/{tid}/folders", json={"name": "docs", "path": ""}, headers=hb).status_code == 409

    # 3) 在团队文件夹内建文档（path = 文件夹完整路径 "docs"）
    r = c.post(f"/api/teams/{tid}/docs", json={"title": "spec.md", "content": "v1", "path": "docs"}, headers=hb)
    assert r.status_code == 201, r.text
    did = r.json()["doc_id"]

    # 4) 核心回归：团队文件夹/文档不得出现在创建者的个人库
    mine = c.get("/api/docs", headers=hb).json()["items"]
    mine_ids = {d["doc_id"] for d in mine}
    assert fid not in mine_ids, "团队文件夹泄漏到个人库！"
    assert did not in mine_ids, "团队文档泄漏到个人库！"

    # 5) 团队库列表应包含该文件夹与文档
    tdocs = c.get(f"/api/teams/{tid}/docs", headers=hb).json()["items"]
    tids = {d["doc_id"] for d in tdocs}
    assert fid in tids and did in tids, [d.get("title") for d in tdocs]
    folder_node = next(d for d in tdocs if d["doc_id"] == fid)
    assert folder_node["kind"] == "folder"

    # 6) 重命名文件夹 → 级联更新后代 path（docs -> archive）
    r = c.put(f"/api/teams/{tid}/folders/{fid}", json={"name": "archive"}, headers=hb)
    assert r.status_code == 200, r.text
    after = c.get(f"/api/teams/{tid}/docs/{did}", headers=hb).json()
    assert after["path"] == "archive", after["path"]

    # 7) 移动团队文件（path 更新，复用 update_team_doc 的 path 支持）
    r = c.put(f"/api/teams/{tid}/docs/{did}", json={"path": ""}, headers=hb)
    assert r.status_code == 200, r.text
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=hb).json()["path"] == ""

    # 8) 目标位置重名 → 409（团队库范围 dup 检查）
    c.post(f"/api/teams/{tid}/docs", json={"title": "dup.md", "content": "", "path": ""}, headers=hb)
    assert c.put(f"/api/teams/{tid}/docs/{did}", json={"title": "dup.md"}, headers=hb).status_code == 409

    # 9) 删除文件夹 → 其内后代一并软删
    #    （did 已被移出 archive 到根，故新建一个子文档验证级联软删）
    r = c.post(f"/api/teams/{tid}/docs", json={"title": "child.md", "content": "", "path": "archive"}, headers=hb)
    child_id = r.json()["doc_id"]
    r = c.delete(f"/api/teams/{tid}/folders/{fid}", headers=hb)
    assert r.status_code == 200 and r.json()["deleted"], r.text
    assert r.json()["count"] >= 1
    # 子文档随文件夹软删（404）；被移出到根的 did 仍存活（200）
    assert c.get(f"/api/teams/{tid}/docs/{child_id}", headers=hb).status_code == 404
    assert c.get(f"/api/teams/{tid}/docs/{did}", headers=hb).status_code == 200

    # 10) 审计：folder create/delete 事件落团队审计
    aud = c.get(f"/api/audit?team_id={tid}&limit=50", headers=ha).json()["items"]
    actions = [a["action"] for a in aud]
    assert "doc.create" in actions and "doc.delete" in actions, actions

print("ALL PASSED")
