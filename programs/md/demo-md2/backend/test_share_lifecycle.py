# -*- coding: utf-8 -*-
"""验证分享生命周期管理：列表/取消/编辑(留空不改 password)/删除拦截 409/文件夹含分享拦截。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="share_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as client:
    client.post("/api/auth/register", json={"username": "sharu", "password": "p@ssw0rd"})
    token = client.post("/api/auth/login", json={"username": "sharu", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # 建两篇文档
    d1 = client.post("/api/docs", json={"title": "doc1.md", "content": "A"}, headers=h).json()["doc_id"]
    d2 = client.post("/api/docs", json={"title": "doc2.md", "content": "B"}, headers=h).json()["doc_id"]

    # 分享 d1（带密码+限访+可编辑）
    r = client.post(f"/api/docs/{d1}/share", json={"password": "pw1", "max_views": 5, "mode": "editable", "expires_days": 7}, headers=h)
    assert r.status_code == 200 and r.json()["has_password"] and r.json()["mode"] == "editable", r.text
    code1 = r.json()["share_code"]

    # 列表
    items = client.get("/api/shares", headers=h).json()["items"]
    assert len(items) == 1 and items[0]["doc_id"] == d1 and items[0]["has_password"], items
    assert "content" not in items[0], items  # 不回传正文

    # 编辑：留空 password（保留原密码），改 max_views/mode
    r = client.put(f"/api/docs/{d1}/share", json={"max_views": 10, "mode": "readonly"}, headers=h)
    assert r.status_code == 200 and r.json()["max_views"] == 10 and r.json()["mode"] == "readonly", r.text
    # password 保留：访客用原密码 pw1 仍能访问
    r = client.get(f"/api/share/{code1}?password=pw1")
    assert r.status_code == 200, r.text
    # 错误密码仍 401
    assert client.get(f"/api/share/{code1}?password=wrong").status_code == 401
    # 清除密码：password=""
    r = client.put(f"/api/docs/{d1}/share", json={"password": ""}, headers=h)
    assert r.status_code == 200 and r.json()["has_password"] is False, r.text
    # 现在无密码可访问
    assert client.get(f"/api/share/{code1}").status_code == 200

    # 删除拦截：正在分享的文档禁止删除 -> 409
    r = client.delete(f"/api/docs/{d1}", headers=h)
    assert r.status_code == 409 and "取消分享" in r.json()["detail"], r.text
    # 永久删除也拦截
    assert client.delete(f"/api/docs/{d1}?permanent=1", headers=h).status_code == 409
    # d2 未分享，可正常删除
    assert client.delete(f"/api/docs/{d2}", headers=h).status_code == 200

    # 文件夹含分享拦截
    fol = client.post("/api/folders", json={"name": "fld", "path": ""}, headers=h).json()["doc_id"]
    d3 = client.post("/api/docs", json={"title": "in_fld.md", "content": "C", "path": "fld"}, headers=h).json()["doc_id"]
    client.post(f"/api/docs/{d3}/share", json={"mode": "readonly"}, headers=h)
    r = client.delete(f"/api/folders/{fol}", headers=h)
    assert r.status_code == 409 and "取消分享" in r.json()["detail"], r.text

    # 取消分享 d1 -> d1 不在列表中（d3 仍在分享）
    r = client.delete(f"/api/docs/{d1}/share", headers=h)
    assert r.status_code == 200, r.text
    share_ids = [it["doc_id"] for it in client.get("/api/shares", headers=h).json()["items"]]
    assert d1 not in share_ids and d3 in share_ids, share_ids
    # 取消后链接失效
    assert client.get(f"/api/share/{code1}").status_code == 404
    # 取消后可删除
    assert client.delete(f"/api/docs/{d1}", headers=h).status_code == 200
    # 取消 d3 后文件夹可删
    client.delete(f"/api/docs/{d3}/share", headers=h)
    assert client.delete(f"/api/folders/{fol}", headers=h).status_code == 200

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
