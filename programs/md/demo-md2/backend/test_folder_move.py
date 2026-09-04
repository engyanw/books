# -*- coding: utf-8 -*-
"""文件夹移动端点回归（个人 + 团队）。

回归点：文件夹可像文件一样拖放到其他目录/子目录下，后端级联更新所有后代
 path 前缀，并阻止成环（移到自身或自身后代下）与目标位置重名。

path 语义：节点的 path = 其父文件夹的完整路径。故文件夹 A(full="A") 移到
 B 下后 A.path="B"、A.full="B/A"，其内文档 path 由 "A" 级联为 "B/A"。
"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="folder_move_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

def reg(client, u, p):
    client.post("/api/auth/register", json={"username": u, "password": p})
    return client.post("/api/auth/login", json={"username": u, "password": p}).json()["token"]

def folder_path(c, fid, headers, team=None):
    # 文件夹与文档共用 documents 表，GET /api/docs/{id}（或团队）返回 path
    url = f"/api/teams/{team}/docs/{fid}" if team else f"/api/docs/{fid}"
    return c.get(url, headers=headers).json()["path"]

with TestClient(main.app) as c:
    ta = reg(c, "alice", "p@ssw0rd")
    ha = {"Authorization": f"Bearer {ta}"}

    # 建两级文件夹 A、B，A 下建子文件夹 C 与文档 doc.md / C 下文档 inC.md
    a = c.post("/api/folders", json={"name": "A", "path": ""}, headers=ha).json()["doc_id"]
    b = c.post("/api/folders", json={"name": "B", "path": ""}, headers=ha).json()["doc_id"]
    sub = c.post("/api/folders", json={"name": "C", "path": "A"}, headers=ha).json()["doc_id"]
    doc = c.post("/api/docs", json={"title": "doc.md", "content": "x", "path": "A"}, headers=ha).json()["doc_id"]
    doc2 = c.post("/api/docs", json={"title": "inC.md", "content": "x", "path": "A/C"}, headers=ha).json()["doc_id"]

    # 1) 把 A 移到 B 下 → A.path="B"（A.full=B/A）；后代 C: A→B/A；doc: A→B/A；doc2: A/C→B/A/C
    r = c.post(f"/api/folders/{a}/move", json={"parent_path": "B"}, headers=ha)
    assert r.status_code == 200, r.text
    assert c.get(f"/api/docs/{doc}", headers=ha).json()["path"] == "B/A"
    assert c.get(f"/api/docs/{sub}", headers=ha).json()["path"] == "B/A"
    assert c.get(f"/api/docs/{doc2}", headers=ha).json()["path"] == "B/A/C"

    # 2) 同父目录再次移动 → 无需移动（200，幂等）
    assert c.post(f"/api/folders/{a}/move", json={"parent_path": "B"}, headers=ha).status_code == 200

    # 3) 把 A 移回根 → A.path="" → 后代 C: B/A→A；doc: B/A→A；doc2: B/A/C→A/C
    r = c.post(f"/api/folders/{a}/move", json={"parent_path": ""}, headers=ha)
    assert r.status_code == 200, r.text
    assert c.get(f"/api/docs/{doc}", headers=ha).json()["path"] == "A"
    assert c.get(f"/api/docs/{sub}", headers=ha).json()["path"] == "A"
    assert c.get(f"/api/docs/{doc2}", headers=ha).json()["path"] == "A/C"

    # 4) 成环：把 A 移到 A/C 下（C 是 A 的后代）→ 400；移到自身 A → 400
    assert c.post(f"/api/folders/{a}/move", json={"parent_path": "A/C"}, headers=ha).status_code == 400
    assert c.post(f"/api/folders/{a}/move", json={"parent_path": "A"}, headers=ha).status_code == 400

    # 5) 目标位置重名：A 下已有 C，把根下新建的 D 重命名为 C 后移入 A → 409
    d = c.post("/api/folders", json={"name": "D", "path": ""}, headers=ha).json()["doc_id"]
    c.put(f"/api/folders/{d}", json={"name": "C"}, headers=ha)
    r = c.post(f"/api/folders/{d}/move", json={"parent_path": "A"}, headers=ha)
    assert r.status_code == 409, r.text
    # 正常移动（D 改回原名后移入 B）→ 200
    c.put(f"/api/folders/{d}", json={"name": "D"}, headers=ha)
    assert c.post(f"/api/folders/{d}/move", json={"parent_path": "B"}, headers=ha).status_code == 200

    # 6) 移动不存在的文件夹 → 404
    assert c.post("/api/folders/nope/move", json={"parent_path": ""}, headers=ha).status_code == 404

    # ---- 团队库 ----
    tb = reg(c, "bob", "p@ssw0rd")
    hb = {"Authorization": f"Bearer {tb}"}
    tid = c.post("/api/teams", json={"name": "T2"}, headers=hb).json()["team_id"]
    ta2 = c.post(f"/api/teams/{tid}/folders", json={"name": "TA", "path": ""}, headers=hb).json()["doc_id"]
    tb2 = c.post(f"/api/teams/{tid}/folders", json={"name": "TB", "path": ""}, headers=hb).json()["doc_id"]
    tsub = c.post(f"/api/teams/{tid}/folders", json={"name": "TC", "path": "TA"}, headers=hb).json()["doc_id"]
    tdoc = c.post(f"/api/teams/{tid}/docs", json={"title": "td.md", "content": "x", "path": "TA"}, headers=hb).json()["doc_id"]

    # 团队文件夹移动 + 后代级联：TA→TB 下，TA.path=TB；tdoc: TA→TB/TA；tsub: TA→TB/TA
    r = c.post(f"/api/teams/{tid}/folders/{ta2}/move", json={"parent_path": "TB"}, headers=hb)
    assert r.status_code == 200, r.text
    assert c.get(f"/api/teams/{tid}/docs/{tdoc}", headers=hb).json()["path"] == "TB/TA"
    assert c.get(f"/api/teams/{tid}/docs/{tsub}", headers=hb).json()["path"] == "TB/TA"
    # 成环：TB 移到 TB/TA 下 → 400
    assert c.post(f"/api/teams/{tid}/folders/{tb2}/move", json={"parent_path": "TB/TA"}, headers=hb).status_code == 400
    # 审计
    aud = c.get(f"/api/audit?team_id={tid}&limit=50", headers=hb).json()["items"]
    assert any("folder move" in a.get("detail", "") for a in aud), [a.get("detail") for a in aud]

print("ALL PASSED")
