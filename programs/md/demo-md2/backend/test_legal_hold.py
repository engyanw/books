# -*- coding: utf-8 -*-
"""⑬法务保留（legal hold）。
- 管理员建立 user 范围保留 → 用户个人文档删除 409；团队文档不受用户范围影响。
- 管理员建立 team 范围保留 → 该团队文档删除 409；其他团队不受影响。
- global 范围 → 全站删除阻断。
- 释放后可正常删除。
- 非管理员 403。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="lhold_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "u1", "password": "p@ssw0rd"})
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'"); conn.commit(); conn.close()
    ta = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    t1 = c.post("/api/auth/login", json={"username": "u1", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    h1 = {"Authorization": f"Bearer {t1}"}

    # u1 建个人文档 + 一个团队 + 团队文档
    did = c.post("/api/docs", headers=h1, json={"title": "P", "content": "p"}).json()["doc_id"]
    tid = c.post("/api/teams", headers=h1, json={"name": "T"}).json()["team_id"]
    tdid = c.post(f"/api/teams/{tid}/docs", headers=h1, json={"title": "TD", "content": "td"}).json()["doc_id"]
    u1_id = c.get("/api/auth/me", headers=h1).json().get("user_id") or c.get("/api/auth/me", headers=h1).json().get("id")

    # 非管理员建保留 → 403
    assert c.post("/api/admin/legal-holds", headers=h1, json={"scope": "global", "reason": "x"}).status_code == 403

    # 建用户范围保留（u1）
    r = c.post("/api/admin/legal-holds", headers=ha, json={"scope": "user", "scope_id": u1_id, "reason": "诉讼 2026"})
    assert r.status_code == 201, r.text
    hid = r.json()["id"]
    # 查文档保留状态
    st = c.get(f"/api/docs/{did}/legal-hold", headers=h1).json()
    assert st["held"] is True and "诉讼" in st["reason"], st

    # u1 删个人文档 → 409
    assert c.delete(f"/api/docs/{did}", headers=h1).status_code == 409
    # 用户范围不影响团队文档：团队文档仍可删（u1 是 owner）
    assert c.delete(f"/api/teams/{tid}/docs/{tdid}", headers=h1).status_code == 200

    # 建团队范围保留
    rh = c.post("/api/admin/legal-holds", headers=ha, json={"scope": "team", "scope_id": tid, "reason": "团队审计"})
    assert rh.status_code == 201, rh.text
    thid = rh.json()["id"]
    # 重建团队文档再删 → 409
    tdid2 = c.post(f"/api/teams/{tid}/docs", headers=h1, json={"title": "TD2", "content": "x"}).json()["doc_id"]
    assert c.delete(f"/api/teams/{tid}/docs/{tdid2}", headers=h1).status_code == 409

    # 列保留
    lst = c.get("/api/admin/legal-holds", headers=ha).json()
    assert len(lst["items"]) == 2, lst

    # 释放团队保留后可删
    assert c.post(f"/api/admin/legal-holds/{thid}/release", headers=ha).status_code == 200
    assert c.delete(f"/api/teams/{tid}/docs/{tdid2}", headers=h1).status_code == 200
    # 重复释放 → 409
    assert c.post(f"/api/admin/legal-holds/{thid}/release", headers=ha).status_code == 409

    # global 保留 → 个人文档删除也被阻断
    g = c.post("/api/admin/legal-holds", headers=ha, json={"scope": "global", "reason": "全站审计"})
    assert g.status_code == 201
    assert c.delete(f"/api/docs/{did}", headers=h1).status_code == 409
    # 释放用户保留 + 全局保留后可删
    gid = g.json()["id"]
    c.post(f"/api/admin/legal-holds/{hid}/release", headers=ha)
    c.post(f"/api/admin/legal-holds/{gid}/release", headers=ha)
    assert c.delete(f"/api/docs/{did}", headers=h1).status_code == 200

print("ALL PASSED")
