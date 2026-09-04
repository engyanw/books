# -*- coding: utf-8 -*-
"""团队文档分享端点 + 团队/个人库隔离 + 公开访问路由回归。

回归点：团队文档分享必须落团队库并在 shares 注册库登记 team_id；
公开 /api/share/{code} 与 /s/{code} 必须能路由到团队库（历史 bug：前端无视
activeTeamId 全部 POST /api/docs/{id}/share，而该端点只查属主个人库 → 404）。
"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="team_share_")
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
    tid = c.post("/api/teams", json={"name": "Shared"}, headers=ha).json()["team_id"]
    c.post(f"/api/teams/{tid}/members", json={"username": "bob", "role": "member"}, headers=ha)
    c.post(f"/api/teams/{tid}/members", json={"username": "carol", "role": "viewer"}, headers=ha)

    # bob 在团队建文档
    r = c.post(f"/api/teams/{tid}/docs", json={"title": "team-note.md", "content": "hello team"}, headers=hb)
    assert r.status_code == 201, r.text
    did = r.json()["doc_id"]

    # 1) viewer 不能分享（无 doc.edit → 403）；member 可以（200）
    assert c.post(f"/api/teams/{tid}/docs/{did}/share", json={"expires_days": 30}, headers=hc).status_code == 403
    r = c.post(f"/api/teams/{tid}/docs/{did}/share", json={"expires_days": 30, "mode": "editable", "max_views": 5}, headers=hb)
    assert r.status_code == 200, r.text
    code = r.json()["share_code"]
    assert r.json()["mode"] == "editable"

    # 2) 核心回归：团队分享不得出现在创建者个人 /api/shares
    mine = [s["doc_id"] for s in c.get("/api/shares", headers=hb).json()["items"]]
    assert did not in mine, "团队分享泄漏到个人库！"

    # 3) 团队分享列表可见（member & viewer）
    tsh = c.get(f"/api/teams/{tid}/shares", headers=hb).json()["items"]
    assert any(s["doc_id"] == did for s in tsh), tsh
    tsh2 = c.get(f"/api/teams/{tid}/shares", headers=hc).json()["items"]
    assert any(s["doc_id"] == did for s in tsh2), tsh2

    # 4) 公开访问能路由到团队库（/api/share/{code} 返回团队文档内容）
    r = c.get(f"/api/share/{code}")
    assert r.status_code == 200 and r.json()["title"] == "team-note.md", r.text
    assert r.json()["content"] == "hello team"
    assert r.json()["max_views"] == 5

    # 5) /s/{code} 页面存在性校验通过
    assert c.get(f"/s/{code}").status_code == 200

    # 6) 可编辑分享回写（PUT /api/share/{code}）落团队库
    r = c.put(f"/api/share/{code}", json={"title": "team-note.md", "content": "edited team"})
    assert r.status_code == 200, r.text
    # 团队文档版本+1 且内容更新
    doc = c.get(f"/api/teams/{tid}/docs/{did}", headers=hb).json()
    assert doc["content"] == "edited team", doc["content"]

    # 7) 更新分享属性（PUT /api/teams/{tid}/docs/{id}/share）
    r = c.put(f"/api/teams/{tid}/docs/{did}/share", json={"mode": "readonly", "max_views": 10}, headers=hb)
    assert r.status_code == 200 and r.json()["mode"] == "readonly" and r.json()["max_views"] == 10, r.text

    # 8) 取消分享（DELETE 团队端点）
    assert c.delete(f"/api/teams/{tid}/docs/{did}/share", headers=hb).status_code == 200
    # 公开访问失效
    assert c.get(f"/api/share/{code}").status_code == 404
    # 团队分享列表不再含
    assert all(s["doc_id"] != did for s in c.get(f"/api/teams/{tid}/shares", headers=hb).json()["items"])

    # 9) 审计含 doc.share.* 事件
    aud = [a["action"] for a in c.get(f"/api/audit?team_id={tid}&limit=100", headers=ha).json()["items"]]
    assert "doc.share.create" in aud and "doc.share.update" in aud and "doc.share.cancel" in aud, aud

print("ALL PASSED")
