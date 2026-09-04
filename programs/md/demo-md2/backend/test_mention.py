# -*- coding: utf-8 -*-
"""B3 回归：@mention 解析 + 通知。
覆盖：解析 @username、评论/文档触发通知、跳过自提及、/auth/me 补 display_name。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="mention_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

# 单元：纯解析
assert main._parse_mentions("hi @alice and @bob!") == ["alice", "bob"]
assert main._parse_mentions("@alice @alice") == ["alice"]  # 去重
assert main._parse_mentions("email a@b.com not a mention") == []  # 无前导空白
assert main._parse_mentions(" @charlie") == ["charlie"]
assert main._parse_mentions(None) == []
print("parse OK")

with TestClient(main.app) as c:
    # 注册 alice（作者）和 bob（被提及者）
    c.post("/api/auth/register", json={"username": "alice", "password": "p@ssw0rd"})
    t_bob = c.post("/api/auth/register", json={"username": "bob", "password": "p@ssw0rd"}).json()["token"]
    # /auth/me 补 display_name
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {t_bob}"}).json()
    assert me["display_name"] == "bob", me
    assert "avatar_url" in me and "org_id" in me, me

    # alice 创建文档
    ta = c.post("/api/auth/login", json={"username": "alice", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    doc = c.post("/api/docs", headers=ha, json={"title": "t", "content": "init"}).json()
    doc_id = doc["doc_id"]

    # alice 更新文档内容，@bob → bob 应收到 mention 通知
    c.put(f"/api/docs/{doc_id}", headers=ha, json={"content": "hey @bob please review"})
    # bob 查通知
    nb = c.get("/api/notifications", headers={"Authorization": f"Bearer {t_bob}"}).json()
    mentions = [n for n in nb.get("items", []) if n.get("type") == "mention"]
    assert mentions, f"bob 未收到 mention 通知: {nb}"
    assert "bob" in mentions[0]["detail"], mentions[0]

    # 自提及不通知：alice 在文档里 @alice，alice 不应收到自己的 mention
    before = len([n for n in c.get("/api/notifications", headers=ha).json().get("items", []) if n.get("type") == "mention"])
    c.put(f"/api/docs/{doc_id}", headers=ha, json={"content": "self @alice note"})
    after = len([n for n in c.get("/api/notifications", headers=ha).json().get("items", []) if n.get("type") == "mention"])
    assert after == before, "alice 不应收到自提及通知"

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
