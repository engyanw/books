# -*- coding: utf-8 -*-
"""验证：从回收站还原与同目录现存文档重名时，不再静默成功——返回 409，且 overwrite/rename 模式可用。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="trash_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as client:
    client.post("/api/auth/register", json={"username": "trash_user", "password": "p@ssw0rd"})
    token = client.post("/api/auth/login", json={"username": "trash_user", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # 建一篇文档 A（同目录同名，现存）
    a = client.post("/api/docs", json={"title": "note.md", "content": "A 在位", "path": ""}, headers=h).json()
    # 建一篇文档 B（同名，删除进回收站）
    b = client.post("/api/docs", json={"title": "note.md", "content": "B 被删", "path": ""}, headers=h).json()
    client.delete(f"/api/docs/{b['doc_id']}", headers=h)  # 软删 -> 回收站

    # 1) auto 模式还原 B：与 A 重名 -> 409，含 suggested_title
    r = client.post(f"/api/trash/{b['doc_id']}/restore", headers=h)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    print("conflict detail:", detail)
    assert detail["conflict"] is True
    assert detail["existing_title"] == "note.md"
    assert detail["existing_doc_id"] == a["doc_id"]
    assert detail["suggested_title"].startswith("note.md") and "(" in detail["suggested_title"]

    # 2) rename 模式：用 suggested_title 还原，应成功（query 参传 title）
    r2 = client.post(f"/api/trash/{b['doc_id']}/restore?mode=rename&title={detail['suggested_title']}", headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["restored"] is True

    # 验证 A 仍在位、B 以新名还原（两篇都在，不重名）
    docs = {d["title"]: d for d in client.get("/api/docs", headers=h).json()["items"]}
    assert "note.md" in docs  # A
    assert detail["suggested_title"] in docs  # B 改名后
    print("after rename:", list(docs.keys()))

    # 3) overwrite 模式：再造一篇同名(note.md)文档 C，删进回收站，再 overwrite 还原——应把 A 移入回收站
    c = client.post("/api/docs", json={"title": "note.md", "content": "C 被删", "path": ""}, headers=h).json()
    client.delete(f"/api/docs/{c['doc_id']}", headers=h)
    r3 = client.post(f"/api/trash/{c['doc_id']}/restore?mode=overwrite", headers=h)
    assert r3.status_code == 200, r3.text
    trash_titles = [d["title"] for d in client.get("/api/trash", headers=h).json()["items"]]
    live_titles = [d["title"] for d in client.get("/api/docs", headers=h).json()["items"]]
    print("live:", live_titles, "| trash:", trash_titles)
    # note.md 仍在位（C 还原为 note.md），A 被移入回收站
    assert live_titles.count("note.md") == 1
    assert "note.md" in trash_titles
    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
