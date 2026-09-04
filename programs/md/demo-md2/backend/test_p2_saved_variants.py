# -*- coding: utf-8 -*-
"""P2-9/10/11: 保存搜索 + 多语言变体（批量测试）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="p2r_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "p2r", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "p2r", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # ===== 保存搜索 =====
    r = c.post("/api/saved-searches", json={"name": "K8s 文档", "query": "kubernetes"}, headers=h)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    items = c.get("/api/saved-searches", headers=h).json()["items"]
    assert len(items) == 1 and items[0]["name"] == "K8s 文档", items
    assert c.delete(f"/api/saved-searches/{sid}", headers=h).status_code == 200
    assert len(c.get("/api/saved-searches", headers=h).json()["items"]) == 0

    # ===== 多语言变体 =====
    did_zh = c.post("/api/docs", json={"title": "guide-zh.md", "content": "# 指南\n中文内容"}, headers=h).json()["doc_id"]
    did_en = c.post("/api/docs", json={"title": "guide-en.md", "content": "# Guide\nEnglish content"}, headers=h).json()["doc_id"]
    r = c.post(f"/api/docs/{did_zh}/link-variant", json={"target_doc_id": did_en, "target_lang": "en"}, headers=h)
    assert r.status_code == 200, r.text
    # 列出变体
    variants = c.get(f"/api/docs/{did_zh}/variants", headers=h).json()["items"]
    assert len(variants) == 1 and variants[0]["doc_id"] == did_en and variants[0]["lang"] == "en", variants
    # 反向查也能看到
    variants2 = c.get(f"/api/docs/{did_en}/variants", headers=h).json()["items"]
    assert len(variants2) == 1 and variants2[0]["doc_id"] == did_zh, variants2

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
