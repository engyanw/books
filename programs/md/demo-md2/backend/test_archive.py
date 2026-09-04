# -*- coding: utf-8 -*-
"""文档归档（冷存储）：归档后只读、列表默认隐藏，可取消归档。"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="arc_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "archuser", "password": "pw123456"})
    tok = c.post("/api/auth/login", json={"username": "archuser", "password": "pw123456"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    did = c.post("/api/docs", json={"title": "cold", "content": "# archive me"}, headers=h).json()["doc_id"]

    # 列表默认应包含（未归档）
    items = c.get("/api/docs", headers=h).json()["items"]
    assert any(d["doc_id"] == did for d in items)

    # 归档
    r = c.post(f"/api/docs/{did}/archive", headers=h)
    assert r.status_code == 200 and r.json()["archived"] is True

    # 列表默认隐藏归档文档
    items = c.get("/api/docs", headers=h).json()["items"]
    assert not any(d["doc_id"] == did for d in items), "归档文档应默认隐藏"
    # include_archived=true 可见
    items2 = c.get("/api/docs?include_archived=true", headers=h).json()["items"]
    assert any(d["doc_id"] == did for d in items2), "include_archived 应返回归档文档"

    # 归档后修改 → 403 只读
    r2 = c.put(f"/api/docs/{did}", json={"content": "# changed"}, headers=h)
    assert r2.status_code == 403, r2.text
    # 读取仍可
    doc = c.get(f"/api/docs/{did}", headers=h).json()
    assert doc["title"] == "cold"

    # 取消归档 → 可编辑
    c.post(f"/api/docs/{did}/unarchive", headers=h)
    r3 = c.put(f"/api/docs/{did}", json={"content": "# changed"}, headers=h)
    assert r3.status_code == 200, r3.text
    # 列表重新可见
    items3 = c.get("/api/docs", headers=h).json()["items"]
    assert any(d["doc_id"] == did for d in items3)

print("ALL PASSED")
