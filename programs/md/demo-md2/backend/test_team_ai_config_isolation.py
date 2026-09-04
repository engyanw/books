# -*- coding: utf-8 -*-
"""团队 AI 配置/对话历史不得泄漏到当前用户个人库。

回归点：团队空间下创建/更新/删除 AI 配置、保存/加载/分叉对话历史，必须落团队库；
前端历史靠 activeTeamId 路由，后端必须有对应团队端点（曾缺失 → 全部落个人库）。
"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="team_ai_cfg_")
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
    ha, hb = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}

    # alice 建团队，邀请 bob=member
    tid = c.post("/api/teams", json={"name": "Eng"}, headers=ha).json()["team_id"]
    c.post(f"/api/teams/{tid}/members", json={"username": "bob", "role": "member"}, headers=ha)

    # ---------- AI 配置 ----------
    # 1) member 建团队 AI 配置（admin 才行？此处 alice(owner/admin) 建）
    r = c.post(f"/api/teams/{tid}/ai/configs", json={"name": "team-llm", "api_url": "https://api.example.com/v1", "api_key": "sk-secret", "model": "gpt-4o-mini"}, headers=ha)
    assert r.status_code == 201, r.text
    cfgid = r.json()["id"]

    # 2) 核心回归：团队配置不得出现在创建者个人 AI 配置列表
    mine = [c["id"] for c in c.get("/api/ai/configs", headers=ha).json()["items"]]
    assert cfgid not in mine, "团队 AI 配置泄漏到个人库！"

    # 3) 团队配置列表可见
    titems = c.get(f"/api/teams/{tid}/ai/configs", headers=hb).json()["items"]
    assert any(c["id"] == cfgid for c in titems), titems

    # 4) 更新团队配置（不传 key 保留原密钥）
    r = c.put(f"/api/teams/{tid}/ai/configs/{cfgid}", json={"name": "team-llm-renamed", "model": "gpt-4o"}, headers=ha)
    assert r.status_code == 200 and r.json()["name"] == "team-llm-renamed", r.text
    # 个人配置列表仍不含
    assert cfgid not in [c["id"] for c in c.get("/api/ai/configs", headers=ha).json()["items"]]

    # 5) 删除团队配置
    assert c.delete(f"/api/teams/{tid}/ai/configs/{cfgid}", headers=ha).status_code == 200
    assert cfgid not in [c["id"] for c in c.get(f"/api/teams/{tid}/ai/configs", headers=ha).json()["items"]]

    # ---------- AI 对话历史 ----------
    # 6) 保存团队对话
    r = c.post(f"/api/teams/{tid}/ai/conversations", json={"messages": [{"role": "user", "content": "hello team"}]}, headers=hb)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["title"]  # 自动标题

    # 7) 核心回归：团队对话不得出现在个人对话历史
    mine_conv = [c["id"] for c in c.get("/api/ai/conversations", headers=hb).json()["items"]]
    assert cid not in mine_conv, "团队 AI 对话泄漏到个人库！"

    # 8) 团队对话列表可见（member）
    tconv = c.get(f"/api/teams/{tid}/ai/conversations", headers=hb).json()["items"]
    assert any(c["id"] == cid for c in tconv), tconv

    # 9) 加载团队对话（含 messages）
    r = c.get(f"/api/teams/{tid}/ai/conversations/{cid}", headers=hb)
    assert r.status_code == 200 and r.json()["messages"][0]["content"] == "hello team", r.text

    # 10) 更新团队对话
    r = c.put(f"/api/teams/{tid}/ai/conversations/{cid}", json={"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]}, headers=hb)
    assert r.status_code == 200, r.text
    assert c.get(f"/api/teams/{tid}/ai/conversations/{cid}", headers=hb).json()["msg_count"] == 2

    # 11) 分叉团队对话（fork@1）
    r = c.post(f"/api/teams/{tid}/ai/conversations/{cid}/fork?fork_at=1", headers=hb)
    assert r.status_code == 201 and r.json()["parent_id"] == cid and r.json()["fork_at"] == 1, r.text
    fork_id = r.json()["id"]
    assert fork_id not in [c["id"] for c in c.get("/api/ai/conversations", headers=hb).json()["items"]], "团队分叉泄漏到个人库！"

    # 12) 删除团队对话
    assert c.delete(f"/api/teams/{tid}/ai/conversations/{cid}", headers=hb).status_code == 200
    assert c.get(f"/api/teams/{tid}/ai/conversations/{cid}", headers=hb).status_code == 404

    # 13) 审计含 ai.conv.* / ai.config.*
    aud = [a["action"] for a in c.get(f"/api/audit?team_id={tid}&limit=100", headers=ha).json()["items"]]
    assert "ai.config.create" in aud and "ai.conv.create" in aud and "ai.conv.fork" in aud and "ai.conv.delete" in aud, aud

    # 14) 非成员不能访问团队对话
    tc = reg(c, "carol", "p@ssw0rd"); hc = {"Authorization": f"Bearer {tc}"}
    assert c.get(f"/api/teams/{tid}/ai/conversations", headers=hc).status_code == 403

print("ALL PASSED")
