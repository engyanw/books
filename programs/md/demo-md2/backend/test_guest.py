# -*- coding: utf-8 -*-
"""P1：外部 Guest 协作者（创建 + 登录 + ACL 授权 + 访问文档）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="guest_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    # alice 注册 + 建文档
    c.post("/api/auth/register", json={"username": "alice", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "alice", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {ta}"}
    did = c.post("/api/docs", json={"title": "shared.md", "content": "secret content"}, headers=h).json()["doc_id"]

    # alice 创建 Guest 账号
    r = c.post("/api/guests", json={"username": "consultant", "password": "guest123", "name": "External Consultant"}, headers=h)
    assert r.status_code == 201, r.text
    guest_uid = r.json()["user_id"]
    assert r.json()["is_guest"] is True

    # Guest 不能重复创建
    assert c.post("/api/guests", json={"username": "consultant", "password": "guest456"}, headers=h).status_code == 409

    # alice 给 Guest 授予文档 read 权限
    r = c.put(f"/api/docs/{did}/acl?target_username=consultant&permission=read", headers=h)
    assert r.status_code == 200, r.text

    # Guest 登录
    tg = c.post("/api/auth/login", json={"username": "consultant", "password": "guest123"}).json()["token"]
    hg = {"Authorization": f"Bearer {tg}"}

    # Guest 列出可访问的文档
    r = c.get("/api/guest/docs", headers=hg)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["doc_id"] == did and items[0]["permission"] == "read", items

    # Guest 读取文档内容
    owner_uid = items[0]["owner_uid"]
    r = c.get(f"/api/guest/docs/{owner_uid}/{did}", headers=hg)
    assert r.status_code == 200 and r.json()["content"] == "secret content", r.text

    # Guest 不能访问未授权的文档
    did2 = c.post("/api/docs", json={"title": "private.md", "content": "no access"}, headers=h).json()["doc_id"]
    assert c.get(f"/api/guest/docs/{owner_uid}/{did2}", headers=hg).status_code == 403

    # 非 Guest 用户不能调 /api/guest/docs
    assert c.get("/api/guest/docs", headers=h).status_code == 403

    # alice 删除 Guest
    r = c.delete(f"/api/guests/{guest_uid}", headers=h)
    assert r.status_code == 200, r.text
    # Guest 删除后登录失败
    assert c.post("/api/auth/login", json={"username": "consultant", "password": "guest123"}).status_code == 401

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
