# -*- coding: utf-8 -*-
"""P1-7：文档分析（贡献统计）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="analytics_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "au", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "au", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 建文档 v1（3 行）
    did = c.post("/api/docs", json={"title": "analytics.md", "content": "line1\nline2\nline3"}, headers=h).json()["doc_id"]
    # 更新 v2（5 行，+2 行）
    c.put(f"/api/docs/{did}", json={"content": "line1\nline2\nline3\nline4\nline5", "version": 1}, headers=h)
    # 更新 v3（4 行，-1 行）
    c.put(f"/api/docs/{did}", json={"content": "line1\nline2\nline3\nline4", "version": 2}, headers=h)

    # 查贡献统计
    r = c.get(f"/api/docs/{did}/analytics", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    print("analytics:", data)
    assert data["total_edits"] >= 2, data  # 2 次更新
    assert data["contributor_count"] >= 1, data
    assert data["contributors"][0]["edits"] >= 2, data
    assert data["total_lines"] == 4, data  # 当前 4 行

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
