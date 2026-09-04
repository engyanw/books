# -*- coding: utf-8 -*-
"""C2 回归：行锚点评论 + 线程。
覆盖：创建（带锚点）、列表按线程聚合、回复、解决/重开、删除、@mention 通知。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="comments_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    doc = c.post("/api/docs", headers=h, json={"title": "d", "content": "line1\nline2"}).json()
    did = doc["doc_id"]

    # 创建主评论（行锚点）
    r = c.post(f"/api/docs/{did}/comments", headers=h, json={"body": "look here", "anchor_type": "line", "anchor_start": 2, "anchor_end": 2})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["anchor_start"] == 2

    # 回复（线程）
    r2 = c.post(f"/api/docs/{did}/comments", headers=h, json={"body": "agreed", "parent_id": cid})
    assert r2.status_code == 201
    rid = r2.json()["id"]
    assert r2.json()["parent_id"] == cid

    # 列表
    lst = c.get(f"/api/docs/{did}/comments", headers=h).json()["items"]
    assert len(lst) == 2, lst
    # 顺序：主评论在前，回复在后
    assert lst[0]["id"] == cid and lst[1]["parent_id"] == cid

    # 解决
    upd = c.put(f"/api/docs/{did}/comments/{cid}?resolve=true", headers=h)
    assert upd.status_code == 200, upd.text
    assert upd.json()["status"] == "resolved"
    assert upd.json()["resolved_at"] is not None

    # 重开
    upd2 = c.put(f"/api/docs/{did}/comments/{cid}?resolve=false", headers=h)
    assert upd2.json()["status"] == "open"
    assert upd2.json()["resolved_at"] is None

    # 编辑正文（仅作者）
    e = c.put(f"/api/docs/{did}/comments/{cid}?body=edited", headers=h)
    assert e.status_code == 200
    assert e.json()["body"] == "edited"

    # 删除回复
    assert c.delete(f"/api/docs/{did}/comments/{rid}", headers=h).status_code == 200
    lst2 = c.get(f"/api/docs/{did}/comments", headers=h).json()["items"]
    assert len(lst2) == 1

    # @mention 通知：另注册 commenter，owner 评论 @commenter
    ct = c.post("/api/auth/register", json={"username": "commenter", "password": "p@ssw0rd"}).json()["token"]
    c.post(f"/api/docs/{did}/comments", headers=h, json={"body": "hi @commenter", "anchor_type": "line"})
    notif = c.get("/api/notifications", headers={"Authorization": f"Bearer {ct}"}).json()
    assert any(n["type"] == "mention" for n in notif.get("items", [])), notif

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
