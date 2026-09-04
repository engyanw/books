# -*- coding: utf-8 -*-
"""P1/C5：文档 Backlinks —— 结构化 wikilink/doc:link 精确匹配。
覆盖：[[target]] 与 [text](doc:target) 均计为引用；裸 doc_id 文本不再误报为反向链接。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="bl_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "blu", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "blu", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # doc A（被引用）
    did_a = c.post("/api/docs", json={"title": "target.md", "content": "# Target doc\n\nI am the target."}, headers=h).json()["doc_id"]
    # doc B：用 doc:link 结构化引用 A
    c.post("/api/docs", json={"title": "referrer.md", "content": f"See [target](doc:{did_a}) for details."}, headers=h)
    # doc C：仅裸文本含 doc_id（无链接语法）→ 不应计为反向链接
    c.post("/api/docs", json={"title": "noise.md", "content": f"The id {did_a} appears here but not as a link."}, headers=h)
    # doc D：用 [[wikilink]] 引用 A（按 doc_id）
    c.post("/api/docs", json={"title": "wiki-ref.md", "content": f"Related: [[{did_a}]]"}, headers=h)

    # 查 A 的 backlinks → 应返回 B 与 D，不含 C
    r = c.get(f"/api/docs/{did_a}/backlinks", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    titles = sorted(i["title"] for i in items)
    assert titles == ["referrer.md", "wiki-ref.md"], items
    assert all(i["team_id"] is None for i in items)

    # 团队 backlinks（wikilink）
    tid = c.post("/api/teams", json={"name": "BT"}, headers=h).json()["team_id"]
    did_team_a = c.post(f"/api/teams/{tid}/docs", json={"title": "team-target.md", "content": "target"}, headers=h).json()["doc_id"]
    c.post(f"/api/teams/{tid}/docs", json={"title": "team-referrer.md", "content": f"Links to [[{did_team_a}]]"}, headers=h)
    r = c.get(f"/api/docs/{did_team_a}/backlinks", headers=h)
    items2 = r.json()["items"]
    assert len(items2) == 1 and items2[0]["title"] == "team-referrer.md" and items2[0]["team_name"] == "BT", items2

    # 无引用 → 空
    r = c.get("/api/docs/NO_SUCH_DOC/backlinks", headers=h)
    assert r.json()["items"] == []

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
