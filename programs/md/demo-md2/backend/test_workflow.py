# -*- coding: utf-8 -*-
"""通用工作流引擎：多阶段可配置审批链。"""
import os, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="wf_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def reg_login(c, name):
    c.post("/api/auth/register", json={"username": name, "password": "pw123456"})
    return c.post("/api/auth/login", json={"username": name, "password": "pw123456"}).json()["token"]


with TestClient(main.app) as c:
    tok = reg_login(c, "alice")
    h = {"Authorization": f"Bearer {tok}"}
    reg_login(c, "bob")
    reg_login(c, "carol")
    reg_login(c, "dave")

    # 建文档
    did = c.post("/api/docs", json={"title": "wfdoc", "content": "# hi"}, headers=h).json()["doc_id"]

    # 创建工作流：2 阶段（阶段1 并行 bob+carol 会签，阶段2 串行 dave）
    wfd = c.post("/api/workflows", json={
        "name": "双阶段审批",
        "definition": {"steps": [
            {"reviewers": ["bob", "carol"], "mode": "parallel"},
            {"reviewers": ["dave"], "mode": "serial"},
        ]},
    }, headers=h).json()
    wfd_id = wfd["id"]
    assert wfd["definition"]["steps"][0]["mode"] == "parallel"

    # 列表
    lst = c.get("/api/workflows", headers=h).json()["items"]
    assert any(w["id"] == wfd_id for w in lst)

    # 非法 definition（无 steps）→ 400
    assert c.post("/api/workflows", json={"name": "bad", "definition": {}}, headers=h).status_code == 400

    # 启动工作流
    st = c.post(f"/api/docs/{did}/workflow/{wfd_id}/start", headers=h).json()
    assert st["stages"] == 2 and st["status"] == "running"
    rid = st["review_id"]

    # 阶段1 并行：bob + carol 都需通过
    bob_tok = c.post("/api/auth/login", json={"username": "bob", "password": "pw123456"}).json()["token"]
    carol_tok = c.post("/api/auth/login", json={"username": "carol", "password": "pw123456"}).json()["token"]
    dave_tok = c.post("/api/auth/login", json={"username": "dave", "password": "pw123456"}).json()["token"]

    # bob 通过 → 阶段1 未完（carol 还没决定）
    r = c.put(f"/api/reviews/{rid}", json={"status": "approved"}, headers={"Authorization": f"Bearer {bob_tok}"})
    assert r.status_code == 200, r.text
    # dave 还不能决定（阶段1 未完成）→ 403/已跳过
    r2 = c.put(f"/api/reviews/{rid}", json={"status": "approved"}, headers={"Authorization": f"Bearer {dave_tok}"})
    assert r2.status_code in (403, 404), r2.text  # dave 的 step 还 pending 但阶段1 未到

    # carol 通过 → 阶段1 完成，推进到阶段2（dave）
    r3 = c.put(f"/api/reviews/{rid}", json={"status": "approved"}, headers={"Authorization": f"Bearer {carol_tok}"})
    assert r3.status_code == 200, r3.text

    # dave 通过 → 整个流程完成
    r4 = c.put(f"/api/reviews/{rid}", json={"status": "approved"}, headers={"Authorization": f"Bearer {dave_tok}"})
    assert r4.status_code == 200, r4.text
    # 检查 review 状态应为 approved（全部通过）
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    status = conn.execute("SELECT status FROM reviews WHERE id=?", (rid,)).fetchone()[0]
    conn.close()
    assert status == "approved", f"流程全部通过应 approved，实际 {status}"

print("ALL PASSED")
