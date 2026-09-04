# -*- coding: utf-8 -*-
"""#5 SQLite 搜索相关性排序 回归。

此前 /api/search 用 LIKE %q% + 按更新时间排序，无相关性：标题命中与正文命中、
多命中与少命中无差别。现：有查询词时走 FTS5 bm25()（标题权重 5×）排序，FTS 不可用回退 LIKE。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="srel_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"

import main  # noqa: E402

Q = "zzalphakey"  # 鲜见词，避免命中种子文档


def mkdoc(c, h, title, content):
    return c.post("/api/docs", headers=h, json={"title": title, "content": content}).json()["doc_id"]


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # A：标题命中 + 正文多次命中（最相关）
    a = mkdoc(c, h, f"{Q} 指南", f"{Q} {Q} {Q} 详解内容")
    # B：仅标题命中
    b = mkdoc(c, h, f"{Q} 标题", "完全无关的内容 here")
    # C：仅正文命中
    cc = mkdoc(c, h, "无关标题", f"正文里提到 {Q} 一次")
    # D：不命中（噪音）
    d = mkdoc(c, h, "噪音文档", "完全不相关的文字 content")

    res = c.get(f"/api/search?q={Q}&limit=50", headers=h).json()["items"]
    titles = [it["title"] for it in res]
    ids = [it["doc_id"] for it in res]

    # 1) 全部命中文档（A/B/C）返回，D 不出现
    assert d not in ids, ids
    assert set([a, b, cc]) == set(ids), ids
    assert len(res) == 3, res

    # 2) 相关性：标题命中（A、B）应排在仅正文命中（C）之前
    pos_c = ids.index(cc)
    pos_a = ids.index(a)
    pos_b = ids.index(b)
    assert pos_a < pos_c, (ids, "A 标题命中应在 C 正文命中前")
    assert pos_b < pos_c, (ids, "B 标题命中应在 C 正文命中前")

    # 3) 无查询词 → 空集（global_search 为查询型搜索，无词不列表）
    assert c.get("/api/search?limit=200", headers=h).json()["items"] == []

    # 4) 无效查询（仅标点，tokenize 为空）→ 回退 LIKE，仍正确返回命中集
    #    build_match_query 对 "!!!" 返回 "" → 跳过 FTS 走 LIKE
    res2 = c.get(f"/api/search?q={Q}!!!&limit=50", headers=h).json()["items"]
    ids2 = [it["doc_id"] for it in res2]
    assert set(ids2) == set([a, b, cc]), ids2  # LIKE 仍命中（!!! 不影响子串）

    # 5) 多词查询 AND 语义：标题同时含两词才命中
    res3 = c.get(f"/api/search?q={Q}+详解&limit=50", headers=h).json()["items"]
    ids3 = [it["doc_id"] for it in res3]
    assert a in ids3, ids3  # A 含两词
    assert b not in ids3, ids3  # B 不含"详解"

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
