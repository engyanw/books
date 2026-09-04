# -*- coding: utf-8 -*-
"""P2：批量导入导出 + 图片上传 + 内容变更建议。"""
import os, shutil, tempfile, io
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="p2_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "p2u", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "p2u", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # ===== P2-8 批量导入导出 =====
    docs_to_import = [{"title": f"batch-{i}.md", "content": f"# Doc {i}\n\ncontent {i}", "path": ""} for i in range(5)]
    r = c.post("/api/docs/bulk-import", json=docs_to_import, headers=h)
    assert r.status_code == 200 and r.json()["imported"] == 5, r.text
    # 导出
    exported = c.get("/api/docs/bulk-export", headers=h).json()["items"]
    assert len(exported) >= 5, exported
    titles = [e["title"] for e in exported]
    assert "batch-0.md" in titles and "batch-4.md" in titles, titles

    # ===== P2-9 图片上传 =====
    # 创建 1x1 PNG
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63000100000005000100a3f5078a0000000049454e44ae426082")
    r = c.post("/api/upload", files={"file": ("test.png", io.BytesIO(png), "image/png")}, headers=h)
    assert r.status_code == 200 and "/uploads/" in r.json()["url"], r.text
    url = r.json()["url"]
    # GET 返回图片
    r2 = c.get(url)
    assert r2.status_code == 200 and r2.headers["content-type"].startswith("image/"), r2.headers
    # 不支持的扩展名
    assert c.post("/api/upload", files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")}, headers=h).status_code == 400

    # ===== P2-10 内容变更建议 =====
    did = c.post("/api/docs", json={"title": "suggest.md", "content": "原文内容"}, headers=h).json()["doc_id"]
    # 提建议
    r = c.post(f"/api/docs/{did}/suggestions", json={"original_text": "原文内容", "proposed_text": "修改后内容", "comment": "建议改写"}, headers=h)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    # 列表
    sugs = c.get(f"/api/docs/{did}/suggestions", headers=h).json()["items"]
    assert len(sugs) == 1 and sugs[0]["status"] == "pending", sugs
    # 接受
    r = c.put(f"/api/docs/{did}/suggestions/{sid}?status=accepted", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "accepted", r.text
    # 文档内容已被追加 proposed_text
    doc = c.get(f"/api/docs/{did}", headers=h).json()
    assert "修改后内容" in doc["content"], doc["content"]
    # 重复处理 409
    assert c.put(f"/api/docs/{did}/suggestions/{sid}?status=rejected", headers=h).status_code == 409

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
