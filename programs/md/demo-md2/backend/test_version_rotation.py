# -*- coding: utf-8 -*-
"""C4 回归：版本快照轮转上限。
覆盖：MAX_VERSIONS_PER_DOC 生效后，多次编辑只保留最近 N 条快照；
旧的被删除；当前文档版本号不受影响。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="vrotate_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["MAX_VERSIONS_PER_DOC"] = "5"  # 保留最近 5 条

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    doc = c.post("/api/docs", headers=h, json={"title": "d", "content": "v0"}).json()
    did = doc["doc_id"]

    # 生成 12 次编辑 → 每次都会插一条快照
    for i in range(1, 13):
        c.put(f"/api/docs/{did}", headers=h, json={"content": f"v{i}", "title": "d"})

    vers = c.get(f"/api/docs/{did}/versions?limit=200", headers=h).json()["items"]
    assert len(vers) == 5, f"期望 5 条快照，实际 {len(vers)}：{vers}"

    # 当前文档版本号应继续递增（=13），不受轮转影响
    d = c.get(f"/api/docs/{did}", headers=h).json()
    assert d["version"] == 13, d
    assert d["content"] == "v12", d

    # 最新快照为编辑前的版本（即 v11 内容）
    assert vers[0]["preview"].startswith("v11"), vers

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
