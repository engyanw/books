# -*- coding: utf-8 -*-
"""E4 回归：Transclusion（!include 复用）。
覆盖：按 doc_id/标题包含全文；#section 片段提取；循环检测；深度上限；缺失目标注释。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="trans_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 目标文档（按 doc_id 与标题均可被引用）
    tgt = c.post("/api/docs", headers=h, json={"title": "target", "content": "TOP-BODY\n# S1\ns1 line\n# S2\ns2 line"}).json()["doc_id"]

    # 1) 按 doc_id 全文包含
    a = c.post("/api/docs", headers=h, json={"title": "a", "content": f"before\n!include[[{tgt}]]\nafter"}).json()["doc_id"]
    ra = c.get(f"/api/docs/{a}/resolved", headers=h).json()["content"]
    assert "TOP-BODY" in ra and "s1 line" in ra and "s2 line" in ra, ra
    assert "before" in ra and "after" in ra

    # 2) 按标题包含
    b = c.post("/api/docs", headers=h, json={"title": "b", "content": f"B:\n!include[doc:target]"}).json()["doc_id"]
    rb = c.get(f"/api/docs/{b}/resolved", headers=h).json()["content"]
    assert "TOP-BODY" in rb, rb

    # 3) #section 片段提取
    s = c.post("/api/docs", headers=h, json={"title": "sec", "content": f"!include[[{tgt}#S1]]"}).json()["doc_id"]
    rs = c.get(f"/api/docs/{s}/resolved", headers=h).json()["content"]
    assert "s1 line" in rs and "s2 line" not in rs, rs

    # 4) 循环检测：X↔Y 互相包含
    x = c.post("/api/docs", headers=h, json={"title": "x", "content": "x-start\n!include[[PLACEHOLDER]]\nx-end"}).json()["doc_id"]
    y = c.post("/api/docs", headers=h, json={"title": "y", "content": f"y-start\n!include[[{x}]]\ny-end"}).json()["doc_id"]
    # 修正 X 引用 Y
    c.put(f"/api/docs/{x}", headers=h, json={"content": f"x-start\n!include[[{y}]]\nx-end", "title": "x"})
    rx = c.get(f"/api/docs/{x}/resolved", headers=h).json()["content"]
    assert "循环引用" in rx, rx
    assert "y-start" in rx, rx  # Y 的内容被展开（到再次引用 X 时停）

    # 5) 缺失目标
    miss = c.post("/api/docs", headers=h, json={"title": "m", "content": "!include[[NOPE-NOT-EXIST]]"}).json()["doc_id"]
    rm = c.get(f"/api/docs/{miss}/resolved", headers=h).json()["content"]
    assert "未找到文档" in rm, rm

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
