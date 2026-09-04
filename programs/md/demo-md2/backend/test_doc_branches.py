# -*- coding: utf-8 -*-
"""E2 回归：并行草稿（branch-like drafts）+ 合并。
覆盖：开分支、列表、读取、编辑 head、合并（快进无冲突 / 冲突标记）。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="branches_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    doc = c.post("/api/docs", headers=h, json={"title": "d", "content": "line1\nline2\nline3"}).json()
    did = doc["doc_id"]

    # 开分支
    br = c.post(f"/api/docs/{did}/branches", headers=h).json()
    bid = br["branch_id"]
    assert br["base_version"] == 1, br

    # 列表
    lst = c.get(f"/api/docs/{did}/branches", headers=h).json()["items"]
    assert len(lst) == 1 and lst[0]["branch_id"] == bid and lst[0]["status"] == "open"

    # 读取
    g = c.get(f"/api/docs/{did}/branches/{bid}", headers=h).json()
    assert g["head_content"] == "line1\nline2\nline3", g

    # 编辑分支 head
    c.put(f"/api/docs/{did}/branches/{bid}", headers=h, json={"head_content": "line1\nBRANCHED\nline3"})
    assert c.get(f"/api/docs/{did}/branches/{bid}", headers=h).json()["head_content"] == "line1\nBRANCHED\nline3"

    # 场景 A：主干未变 → 快进合并无冲突
    m = c.post(f"/api/docs/{did}/branches/{bid}/merge", headers=h).json()
    assert m["merged"] is True and m["conflict"] is False and m["status"] == "merged", m
    cur = c.get(f"/api/docs/{did}", headers=h).json()
    assert cur["content"] == "line1\nBRANCHED\nline3", cur["content"]
    assert cur["version"] == 2, cur

    # 场景 B：新文档，主干与分支从同一基线各自改同一行 → 冲突
    doc2 = c.post("/api/docs", headers=h, json={"title": "d2", "content": "X\nY\nZ"}).json()
    did2 = doc2["doc_id"]
    # 基线 = X\nY\nZ；开分支（base 即基线）
    br2 = c.post(f"/api/docs/{did2}/branches", headers=h).json()["branch_id"]
    # 主干改第二行
    c.put(f"/api/docs/{did2}", headers=h, json={"content": "X\nMAIN\nZ", "title": "d2"})
    # 分支改第二行（与主干冲突）
    c.put(f"/api/docs/{did2}/branches/{br2}", headers=h, json={"head_content": "X\nBRANCH\nZ"})
    m2 = c.post(f"/api/docs/{did2}/branches/{br2}/merge", headers=h).json()
    assert m2["conflict"] is True and m2["status"] == "conflict", m2
    cur2 = c.get(f"/api/docs/{did2}", headers=h).json()
    assert "<<<<<<< branch" in cur2["content"] and "=======" in cur2["content"] and ">>>>>>> main" in cur2["content"], cur2["content"]

    # 已合并分支不可再合并 → 409
    assert c.post(f"/api/docs/{did}/branches/{bid}/merge", headers=h).status_code == 409
    # 冲突分支不可编辑 → 409
    assert c.put(f"/api/docs/{did2}/branches/{br2}", headers=h, json={"head_content": "x"}).status_code == 409

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
