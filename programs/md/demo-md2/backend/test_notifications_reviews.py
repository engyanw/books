# -*- coding: utf-8 -*-
"""T5：站内通知（分享被访问触发）+ 文档评审流（请求/列表/裁决）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="t5_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "author", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "reviewer", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "visitor", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "author", "password": "p@ssw0rd"}).json()["token"]
    tr = c.post("/api/auth/login", json={"username": "reviewer", "password": "p@ssw0rd"}).json()["token"]
    tv = c.post("/api/auth/login", json={"username": "visitor", "password": "p@ssw0rd"}).json()["token"]
    ha, hr, hv = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tr}"}, {"Authorization": f"Bearer {tv}"}

    # author 建文档 + 分享
    did = c.post("/api/docs", json={"title": "spec.md", "content": "draft"}, headers=ha).json()["doc_id"]
    code = c.post(f"/api/docs/{did}/share", json={"mode": "readonly"}, headers=ha).json()["share_code"]

    # visitor 访问分享 -> author 应收到通知
    c.get(f"/api/share/{code}")
    notifs = c.get("/api/notifications", headers=ha).json()
    assert notifs["unread"] >= 1
    assert any(n["type"] == "share.access" for n in notifs["items"]), notifs

    # 标记已读
    nid = notifs["items"][0]["id"]
    assert c.put(f"/api/notifications/{nid}/read", headers=ha).status_code == 200
    assert c.get("/api/notifications?unread_only=1", headers=ha).json()["unread"] == 0

    # author 请求 reviewer 评审
    r = c.post(f"/api/docs/{did}/review", json={"reviewer_username": "reviewer", "comment": "请看第一章"}, headers=ha)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    # reviewer 收到通知 + 在 incoming 列表
    rnotif = c.get("/api/notifications", headers=hr).json()
    assert any(n["type"] == "review.request" for n in rnotif["items"]), rnotif
    inc = c.get("/api/reviews/incoming", headers=hr).json()["items"]
    assert len(inc) == 1 and inc[0]["status"] == "pending", inc

    # reviewer 裁决 approved
    r = c.put(f"/api/reviews/{rid}", json={"status": "approved", "comment": "通过"}, headers=hr)
    assert r.status_code == 200 and r.json()["status"] == "approved", r.text
    # 重复裁决 403（多步审批：已无待审步骤）
    assert c.put(f"/api/reviews/{rid}", json={"status": "rejected"}, headers=hr).status_code == 403
    # author 收到裁决通知
    anot = c.get("/api/notifications?unread_only=1", headers=ha).json()["items"]
    assert any(n["type"] == "review.decided" for n in anot), anot

    # 不能评审自己的文档
    assert c.post(f"/api/docs/{did}/review", json={"reviewer_username": "author"}, headers=ha).status_code == 400

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
