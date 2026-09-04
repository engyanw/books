# -*- coding: utf-8 -*-
"""P2-7/C5: 依赖图可视化 —— 基于结构化 wikilink 解析的节点+边数据。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="dep_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "du", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "du", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # A 引用 B，B 引用 C（结构化 wikilink）
    did_a = c.post("/api/docs", json={"title": "A.md", "content": "doc A"}, headers=h).json()["doc_id"]
    did_b = c.post("/api/docs", json={"title": "B.md", "content": f"see [[{did_a}]]"}, headers=h).json()["doc_id"]
    did_c = c.post("/api/docs", json={"title": "C.md", "content": f"see [[{did_b}]]"}, headers=h).json()["doc_id"]
    # A 引用 C
    c.put(f"/api/docs/{did_a}", json={"content": f"doc A\nsee [[{did_c}]]", "version": 1}, headers=h)

    # A 的依赖图：应有 3 个节点 + 1 出边(A→C) + 1 入边(B→A)
    r = c.get(f"/api/docs/{did_a}/dependency-graph", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    node_ids = {n["id"] for n in data["nodes"]}
    assert did_a in node_ids and did_b in node_ids and did_c in node_ids, node_ids
    # A→C 出边
    assert any(e["from"] == did_a and e["to"] == did_c for e in data["edges"]), data["edges"]
    # B→A 入边
    assert any(e["from"] == did_b and e["to"] == did_a for e in data["edges"]), data["edges"]
    # 当前节点标记
    assert any(n["id"] == did_a and n["is_current"] for n in data["nodes"]), data["nodes"]

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
