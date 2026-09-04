# -*- coding: utf-8 -*-
"""C3 回归：建议接受改为 in-place 原地替换。
覆盖：原文命中→替换且版本号+1；未命中→回退追加；驳回不动内容；重复处理 409。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="suggestions_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    doc = c.post("/api/docs", headers=h, json={"title": "d", "content": "alpha\nbeta\ngamma"}).json()
    did = doc["doc_id"]

    # 1) 命中原文：beta -> BETA
    r = c.post(f"/api/docs/{did}/suggestions", headers=h,
               json={"original_text": "beta", "proposed_text": "BETA", "comment": "fix"}).json()
    sid = r["id"]
    dec = c.put(f"/api/docs/{did}/suggestions/{sid}?status=accepted", headers=h).json()
    assert dec["status"] == "accepted"
    assert dec["replaced"] is True, dec

    d = c.get(f"/api/docs/{did}", headers=h).json()
    assert d["content"] == "alpha\nBETA\ngamma", d["content"]
    assert "beta" not in d["content"]
    # 版本号递增（初始版本 1 -> 2）
    assert d["version"] == 2, d

    # 2) 未命中原文：回退追加
    r2 = c.post(f"/api/docs/{did}/suggestions", headers=h,
                json={"original_text": "nope-not-here", "proposed_text": "TAIL"}).json()
    sid2 = r2["id"]
    dec2 = c.put(f"/api/docs/{did}/suggestions/{sid2}?status=accepted", headers=h).json()
    assert dec2["replaced"] is False, dec2
    d2 = c.get(f"/api/docs/{did}", headers=h).json()
    assert d2["content"].endswith("TAIL"), d2["content"]

    # 3) 驳回：内容不变
    r3 = c.post(f"/api/docs/{did}/suggestions", headers=h,
                json={"original_text": "alpha", "proposed_text": "ALPHA"}).json()
    sid3 = r3["id"]
    before = c.get(f"/api/docs/{did}", headers=h).json()["content"]
    c.put(f"/api/docs/{did}/suggestions/{sid3}?status=rejected", headers=h)
    after = c.get(f"/api/docs/{did}", headers=h).json()["content"]
    assert before == after

    # 4) 重复处理已接受的建议 → 409
    dup = c.put(f"/api/docs/{did}/suggestions/{sid}?status=accepted", headers=h)
    assert dup.status_code == 409, dup.text

    # 5) 版本快照保留替换前内容（列表返回 preview）
    vers = c.get(f"/api/docs/{did}/versions?limit=10", headers=h).json()["items"]
    assert len(vers) >= 1, vers
    # 第一个被接受建议的快照应为版本 1（替换前），preview 仍含小写 beta
    assert any(v["version"] == 1 and "beta" in v["preview"] for v in vers), vers

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
