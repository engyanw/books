# -*- coding: utf-8 -*-
"""⑩团队文档行级 diff 审阅。
- 创建→v1 快照；更新产生 v2 快照；列表/获取可用。
- diff(v1→v2) 返回 added/removed/modified + unified。
- diff(v1→current) 对比当前内容。
- ACL：未授权读者被拒（403）；成员可读。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="tdiff_")
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

    tid = c.post("/api/teams", headers=ho, json={"name": "TD"}).json()["team_id"]
    c.post(f"/api/teams/{tid}/members", headers=ho, json={"username": "alice", "role": "member"})
    c.post(f"/api/teams/{tid}/members", headers=ho, json={"username": "bob", "role": "member"})

    did = c.post(f"/api/teams/{tid}/docs", headers=ho, json={"title": "D", "content": "第一行\n第二行"}).json()["doc_id"]
    # 第二次更新 → v2
    c.put(f"/api/teams/{tid}/docs/{did}", headers=ho, json={"content": "第一行改\n第二行\n第三行新增"})

    # 版本列表（至少 2 条）
    lv = c.get(f"/api/teams/{tid}/docs/{did}/versions", headers=ho).json()
    assert len(lv["items"]) >= 2, lv
    v1 = lv["items"][-1]["id"]   # 最旧
    v2 = lv["items"][0]["id"]    # 最新

    # 获取某版本
    gv = c.get(f"/api/teams/{tid}/docs/{did}/versions/{v1}", headers=ho).json()
    assert "第一行" in gv["content"], gv

    # diff v1→v2
    d = c.get(f"/api/teams/{tid}/docs/{did}/versions/{v1}/diff/{v2}", headers=ho).json()
    diff = d["diff"]
    assert diff["added_count"] >= 1, diff
    assert diff["removed_count"] >= 1, diff
    assert "第三行新增" in diff["unified"], diff["unified"]
    assert any(a["content"] == "第三行新增" for a in diff["added"]), diff
    assert any(r["content"] == "第一行" for r in diff["removed"]), diff

    # diff v1→current
    dc = c.get(f"/api/teams/{tid}/docs/{did}/versions/{v1}/diff/current", headers=ho).json()
    assert dc["diff"]["added_count"] >= 1, dc

    # ACL：owner 限制 bob 读
    c.put(f"/api/teams/{tid}/docs/{did}/acl?target_username=alice&permission=read", headers=ho)
    # bob 未授权 → 版本列表 403
    assert c.get(f"/api/teams/{tid}/docs/{did}/versions", headers=hb).status_code == 403
    # alice 授权 read → 可读版本但不可 diff 写？读路径放行
    assert c.get(f"/api/teams/{tid}/docs/{did}/versions", headers=ha).status_code == 200
    assert c.get(f"/api/teams/{tid}/docs/{did}/versions/{v1}/diff/{v2}", headers=ha).status_code == 200

print("ALL PASSED")
