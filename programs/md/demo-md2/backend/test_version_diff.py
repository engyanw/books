# -*- coding: utf-8 -*-
"""P1-D2：版本 diff 端点。

验证：两个版本内容差异 → 行级 diff（added/removed/modified/unified）；
v2=current 对比当前内容；不存在版本 404。
"""
import os, tempfile, shutil
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="vdiff_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def reg(c, u):
    c.post("/api/auth/register", json={"username": u, "password": "pw123456"})
    return c.post("/api/auth/login", json={"username": u, "password": "pw123456"}).json()["token"]


with TestClient(main.app) as c:
    tok = reg(c, "alice")
    ha = {"Authorization": f"Bearer {tok}"}

    # 创建文档 v1 内容
    did = c.post("/api/docs", json={
        "title": "diffdoc",
        "content": "line1\nline2\nline3\nline4",
    }, headers=ha).json()["doc_id"]
    # 第一次更新 → 产生版本快照（v1 旧内容）
    c.put(f"/api/docs/{did}", json={
        "title": "diffdoc", "content": "line1\nline2 modified\nline3\nline5",
    }, headers=ha)

    vers = c.get(f"/api/docs/{did}/versions", headers=ha).json()["items"]
    assert len(vers) >= 1, vers
    v1_id = vers[0]["id"]  # 旧版本快照（line1..line4）

    # 1) 版本 vs 版本（这里只有 1 个快照，用自身对比 → 无差异）
    d = c.get(f"/api/docs/{did}/versions/{v1_id}/diff/{v1_id}", headers=ha).json()
    assert d["diff"]["added_count"] == 0 and d["diff"]["removed_count"] == 0, d

    # 2) 快照 v1 → current（当前是修改后内容）
    d = c.get(f"/api/docs/{did}/versions/{v1_id}/diff/current", headers=ha).json()
    diff = d["diff"]
    # line2 被修改（删旧增新），line4 被删，line5 被增
    assert diff["added_count"] >= 1, diff
    assert diff["removed_count"] >= 1, diff
    assert any(a["content"] == "line5" for a in diff["added"]), diff["added"]
    assert any(r["content"] == "line4" for r in diff["removed"]), diff["removed"]
    # modified 配对（line2→line2 modified）
    assert any(m["old_content"] == "line2" and m["new_content"] == "line2 modified"
               for m in diff["modified"]), diff["modified"]
    # unified diff 文本包含标记
    assert "---" in diff["unified"] and "+++" in diff["unified"], diff["unified"]

    # 3) 不存在版本 → 404
    r = c.get(f"/api/docs/{did}/versions/999999/diff/current", headers=ha)
    assert r.status_code == 404, r.text

shutil.rmtree(TMP, ignore_errors=True)
print("ALL PASSED")
