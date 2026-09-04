# -*- coding: utf-8 -*-
"""P1-9 内容分析仪表盘：聚合个人库——状态/类型分布、14 天活跃、贡献榜、待审。"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="dash_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "dash", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "dash", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    # 建若干不同状态文档
    d1 = c.post("/api/docs", headers=h, json={"title": "a", "content": "x"}).json()["doc_id"]
    c.put(f"/api/docs/{d1}/status?status=in_review", headers=h)
    d2 = c.post("/api/docs", headers=h, json={"title": "b", "content": "y\ny"}).json()["doc_id"]
    # 合法流转：draft→in_review→approved→published
    c.put(f"/api/docs/{d2}/status?status=in_review", headers=h)
    c.put(f"/api/docs/{d2}/status?status=approved", headers=h)
    c.put(f"/api/docs/{d2}/status?status=published", headers=h)

    d = c.get("/api/analytics/dashboard", headers=h).json()
    assert d["total_docs"] >= 2, d
    assert d["status_counts"].get("in_review", 0) >= 1, d
    assert d["status_counts"].get("published", 0) >= 1, d
    assert "file" in d["kind_counts"], d
    assert isinstance(d["activity_14d"], list) and d["activity_14d"], d
    assert any(x["date"] and x["count"] > 0 for x in d["activity_14d"]), d
    assert d["pending_reviews"] == 0, d  # 无评审
    assert isinstance(d["contribution_leaders"], list), d

print("ALL PASSED")
