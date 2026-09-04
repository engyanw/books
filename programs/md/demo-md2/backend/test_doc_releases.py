# -*- coding: utf-8 -*-
"""E3 回归：文档集 release（打包版本快照 + 冻结）。
覆盖：创建 release（快照多文档当前版本/内容）、列表、详情取内容、冻结。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="release_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    # 另一用户用于冻结权限测试
    ct = c.post("/api/auth/register", json={"username": "u2", "password": "p@ssw0rd"}).json()["token"]
    hn = {"Authorization": f"Bearer {ct}"}

    d1 = c.post("/api/docs", headers=h, json={"title": "a", "content": "AAA"}).json()["doc_id"]
    d2 = c.post("/api/docs", headers=h, json={"title": "b", "content": "BBB"}).json()["doc_id"]

    # 创建 release
    r = c.post("/api/releases", headers=h, json={"name": "v1.0", "version": "1.0", "doc_ids": [d1, d2]}).json()
    rid = r["release_id"]
    assert r["doc_count"] == 2, r

    # 修改源文档（release 快照应不受影响）
    c.put(f"/api/docs/{d1}", headers=h, json={"content": "CHANGED", "title": "a"})

    # 列表
    lst = c.get("/api/releases", headers=h).json()["items"]
    assert len(lst) == 1 and lst[0]["release_id"] == rid and lst[0]["doc_count"] == 2, lst

    # 详情：内容为快照（AAA 未变）
    det = c.get(f"/api/releases/{rid}", headers=h).json()
    mf = {m["doc_id"]: m for m in det["manifest"]}
    assert mf[d1]["content"] == "AAA", mf[d1]
    assert mf[d2]["content"] == "BBB", mf[d2]
    assert mf[d1]["version"] == 1, mf[d1]
    assert det["frozen"] is False

    # 非创建者不可冻结 → 403
    assert c.post(f"/api/releases/{rid}/freeze", headers=hn).status_code == 403
    # 创建者冻结
    f = c.post(f"/api/releases/{rid}/freeze", headers=h).json()
    assert f["frozen"] is True
    assert c.get(f"/api/releases/{rid}", headers=h).json()["frozen"] is True

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
