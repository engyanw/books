# -*- coding: utf-8 -*-
"""E5 回归：断链检测（结构化链接图）。
覆盖：GET /api/docs/{id}/links 实时校验（命中=非断链，缺失=断链）；
GET /api/admin/links/broken 全局断链报告；非管理员 403。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="linkcheck_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    # 管理员
    import sqlite3 as _s
    _db = _s.connect(os.path.join(TMP, "registry.db"))
    _db.execute("UPDATE users SET is_admin=1 WHERE username=?", ("owner",))
    _db.commit(); _db.close()
    # 普通用户
    ct = c.post("/api/auth/register", json={"username": "u2", "password": "p@ssw0rd"}).json()["token"]
    hn = {"Authorization": f"Bearer {ct}"}

    # 目标文档（存在）
    tgt = c.post("/api/docs", headers=h, json={"title": "target", "content": "T"}).json()["doc_id"]
    # 源文档：包含一个有效 wikilink + 一个断链（指向不存在的 doc_id）
    src = c.post("/api/docs", headers=h, json={"title": "src", "content": f"see [[{tgt}]] and [[MISSING-DOC]]"}).json()["doc_id"]

    # /links：应标记 tgt 非断链、MISSING-DOC 断链
    r = c.get(f"/api/docs/{src}/links", headers=h).json()
    items = {i["target_ref"]: i for i in r["items"]}
    assert tgt in items and items[tgt]["broken"] is False, r
    assert "MISSING-DOC" in items and items["MISSING-DOC"]["broken"] is True, r
    assert items[tgt]["target_doc_id"] == tgt, r

    # 修复断链后重新校验
    c.put(f"/api/docs/{src}", headers=h, json={"content": f"only [[{tgt}]]", "title": "src"})
    r2 = c.get(f"/api/docs/{src}/links", headers=h).json()["items"]
    assert all(not i["broken"] for i in r2) and len(r2) == 1, r2

    # 再次制造断链用于全局报告
    c.put(f"/api/docs/{src}", headers=h, json={"content": f"[[{tgt}]] [[ANOTHER-BROKEN]]", "title": "src"})

    # 非管理员 → 403
    assert c.get("/api/admin/links/broken", headers=hn).status_code == 403
    # 全局断链报告
    rep = c.get("/api/admin/links/broken", headers=h).json()
    assert rep["broken_count"] == 1, rep
    assert rep["items"][0]["target_ref"] == "ANOTHER-BROKEN", rep
    assert rep["items"][0]["username"] == "owner", rep

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
