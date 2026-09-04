# -*- coding: utf-8 -*-
"""P1：批量操作（个人 + 团队文档）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="batch_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "bu", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "bu", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 建 5 篇文档
    ids = []
    for i in range(5):
        ids.append(c.post("/api/docs", json={"title": f"b-{i}.md", "content": f"content {i}"}, headers=h).json()["doc_id"])

    # 批量加标签
    r = c.post("/api/docs/batch", json={"doc_ids": ids[:3], "action": "tag", "value": "important"}, headers=h)
    assert r.status_code == 200 and r.json()["affected"] == 3, r.text
    # 验证标签生效
    docs = c.get("/api/docs", headers=h).json()["items"]
    tagged = [d for d in docs if "important" in (d.get("tags") or "")]
    assert len(tagged) == 3, tagged

    # 批量收藏
    r = c.post("/api/docs/batch", json={"doc_ids": ids[:2], "action": "star"}, headers=h)
    assert r.json()["affected"] == 2
    docs2 = c.get("/api/docs", headers=h).json()["items"]
    starred = [d for d in docs2 if d.get("starred")]
    assert len(starred) == 2

    # 批量删除
    r = c.post("/api/docs/batch", json={"doc_ids": ids[3:], "action": "delete"}, headers=h)
    assert r.json()["affected"] == 2
    # 验证被删的不在列表里（注册时还播种了 examples，所以只验证被删的不在）
    remaining = c.get("/api/docs", headers=h).json()["items"]
    remaining_ids = {d["doc_id"] for d in remaining}
    assert ids[3] not in remaining_ids and ids[4] not in remaining_ids, "deleted docs should be gone"

    # 不支持的操作
    assert c.post("/api/docs/batch", json={"doc_ids": ids[:1], "action": "explode"}, headers=h).status_code == 400

    # 团队批量
    tid = c.post("/api/teams", json={"name": "BT"}, headers=h).json()["team_id"]
    tids = [c.post(f"/api/teams/{tid}/docs", json={"title": f"t-{i}.md", "content": "x"}, headers=h).json()["doc_id"] for i in range(3)]
    r = c.post(f"/api/teams/{tid}/docs/batch", json={"doc_ids": tids[:2], "action": "tag", "value": "team-tag"}, headers=h)
    assert r.json()["affected"] == 2, r.text

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
