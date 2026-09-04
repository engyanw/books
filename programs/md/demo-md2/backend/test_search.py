# -*- coding: utf-8 -*-
"""P0-2：跨团队全文搜索（个人 + 团队库，权限过滤）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="search_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "searcher", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "searcher", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 个人文档含关键词
    c.post("/api/docs", json={"title": "pers.md", "content": "SPEC_KEYWORD_HERE personal doc"}, headers=h)
    # 团队 + 团队文档含关键词
    tid = c.post("/api/teams", json={"name": "TeamA"}, headers=h).json()["team_id"]
    c.post(f"/api/teams/{tid}/docs", json={"title": "team.md", "content": "SPEC_KEYWORD_HERE team doc"}, headers=h)

    # 第二个团队
    tid2 = c.post("/api/teams", json={"name": "TeamB"}, headers=h).json()["team_id"]
    c.post(f"/api/teams/{tid2}/docs", json={"title": "team2.md", "content": "OTHER_KEYWORD only"}, headers=h)

    # 搜索 SPEC_KEYWORD → 应返回 2 篇（1 个人 + 1 团队A）
    r = c.get("/api/search?q=SPEC_KEYWORD", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    print("search results:", [(it["title"], it["scope"], it.get("team_name")) for it in items])
    assert len(items) == 2, items
    scopes = [it["scope"] for it in items]
    assert "personal" in scopes and "team" in scopes, scopes
    team_item = [it for it in items if it["scope"] == "team"][0]
    assert team_item["team_name"] == "TeamA", team_item

    # 搜索 OTHER_KEYWORD → 只返回 1 篇（TeamB）
    items2 = c.get("/api/search?q=OTHER_KEYWORD", headers=h).json()["items"]
    assert len(items2) == 1 and items2[0]["team_name"] == "TeamB", items2

    # 无关键词 → 空
    assert c.get("/api/search", headers=h).json()["items"] == []

    # 非成员搜不到（注册新人，不在 TeamA）
    c.post("/api/auth/register", json={"username": "outsider", "password": "p@ssw0rd"})
    t2 = c.post("/api/auth/login", json={"username": "outsider", "password": "p@ssw0rd"}).json()["token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    items3 = c.get("/api/search?q=SPEC_KEYWORD", headers=h2).json()["items"]
    assert len(items3) == 0, items3  # outsider 不是任何团队成员，搜不到团队文档

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
