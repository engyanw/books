# -*- coding: utf-8 -*-
"""验证 AI 对话历史 CRUD：保存（自动标题）/列表/加载/更新/删除。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="aiconv_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as client:
    client.post("/api/auth/register", json={"username": "convu", "password": "p@ssw0rd"})
    token = client.post("/api/auth/login", json={"username": "convu", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # 初始列表为空
    assert client.get("/api/ai/conversations", headers=h).json()["items"] == []

    # 保存：自动标题取首条 user 消息
    r = client.post("/api/ai/conversations", json={
        "messages": [
            {"role": "user", "content": "如何用 Markdown 写表格？"},
            {"role": "assistant", "content": "用 | 分隔..."},
        ]
    }, headers=h)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["title"] == "如何用 Markdown 写表格？" and r.json()["msg_count"] == 2, r.json()

    # 列表回显（仅元数据，不含 messages 正文）
    items = client.get("/api/ai/conversations", headers=h).json()["items"]
    assert len(items) == 1 and items[0]["id"] == cid and items[0]["title"].startswith("如何用 Markdown")
    assert "messages" not in items[0], items[0]

    # 加载完整
    r = client.get(f"/api/ai/conversations/{cid}", headers=h)
    assert r.status_code == 200 and len(r.json()["messages"]) == 2, r.text

    # 更新 messages（追答一轮）
    r = client.put(f"/api/ai/conversations/{cid}", json={
        "messages": [
            {"role": "user", "content": "如何用 Markdown 写表格？"},
            {"role": "assistant", "content": "用 | 分隔..."},
            {"role": "user", "content": "再举个例子"},
            {"role": "assistant", "content": "好的"},
        ]
    }, headers=h)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/ai/conversations/{cid}", headers=h).json()["msg_count"] == 4

    # 不存在 -> 404
    assert client.get("/api/ai/conversations/nope", headers=h).status_code == 404

    # 删除
    assert client.delete(f"/api/ai/conversations/{cid}", headers=h).status_code == 200
    assert client.get("/api/ai/conversations", headers=h).json()["items"] == []

    # 隔离：第二个用户看不到第一个
    client.post("/api/auth/register", json={"username": "convu2", "password": "p@ssw0rd"})
    t2 = client.post("/api/auth/login", json={"username": "convu2", "password": "p@ssw0rd"}).json()["token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert client.get("/api/ai/conversations", headers=h2).json()["items"] == []

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
