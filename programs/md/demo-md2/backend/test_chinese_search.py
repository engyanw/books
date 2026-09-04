# -*- coding: utf-8 -*-
"""P1-C2：中文分词全文检索。

验证：
- tokenizer 把 CJK 切成 bigram（"项目管理流程" 含 "项目"、"管理"）
- 搜索 2 字中文词"项目"能命中标题为"项目管理流程规范"的文档（unicode61 默认会漏召回）
- 搜索 3+ 字命中
- 英文仍正常分词（小写化）
"""
import os, tempfile, shutil
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="cjk_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402
from search_tokenizer import tokenize, build_match_query  # noqa: E402

# 1) tokenizer 行为
t = tokenize("项目管理流程")
assert "项目" in t.split(), t
assert "管理" in t.split(), t
# 英文小写化、与中文混合
t2 = tokenize("FastAPI 项目 Project")
assert "fastapi" in t2.split() and "project" in t2.split(), t2
# 查询串构造：每 token 加引号
q = build_match_query("项目 管理")
assert '"项目"' in q and '"管理"' in q, q


def reg(c, u):
    c.post("/api/auth/register", json={"username": u, "password": "pw123456"})
    return c.post("/api/auth/login", json={"username": u, "password": "pw123456"}).json()["token"]


with TestClient(main.app) as c:
    tok = reg(c, "alice")
    ha = {"Authorization": f"Bearer {tok}"}

    # 创建含中文长词的文档
    c.post("/api/docs", json={"title": "项目管理流程规范", "content": "本项目描述了敏捷开发与持续集成的实践"}, headers=ha)
    c.post("/api/docs", json={"title": "无关文档", "content": "hello world 完全不同内容"}, headers=ha)

    # 2) 2 字词"项目"应命中"项目管理流程规范"
    r = c.get("/api/search", params={"q": "项目"}, headers=ha).json()
    titles = [x["title"] for x in r["items"]]
    assert "项目管理流程规范" in titles, titles

    # 3) 3 字词"管理流程"命中
    r = c.get("/api/search", params={"q": "管理流程"}, headers=ha).json()
    titles = [x["title"] for x in r["items"]]
    assert "项目管理流程规范" in titles, titles

    # 4) 正文内容词"持续集成"命中
    r = c.get("/api/search", params={"q": "持续集成"}, headers=ha).json()
    titles = [x["title"] for x in r["items"]]
    assert "项目管理流程规范" in titles, titles

    # 5) 英文搜索仍工作
    r = c.get("/api/search", params={"q": "hello"}, headers=ha).json()
    titles = [x["title"] for x in r["items"]]
    assert "无关文档" in titles, titles

    # 6) 不相关中文不应命中
    r = c.get("/api/search", params={"q": "量子物理"}, headers=ha).json()
    titles = [x["title"] for x in r["items"]]
    assert "项目管理流程规范" not in titles, titles

shutil.rmtree(TMP, ignore_errors=True)
print("ALL PASSED")
