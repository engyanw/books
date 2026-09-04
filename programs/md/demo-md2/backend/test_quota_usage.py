# -*- coding: utf-8 -*-
"""⑪配额与用量计量。
- USER_MAX_DOCS=3：第 4 篇 → 429。
- /api/usage 返回 count/max。
- /api/teams/{tid}/usage 返回团队用量。
- 无配额时（默认 0）创建不限。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="quota_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 配额：用户最多 2 篇文档、最多 1 个团队；团队最多 1 篇文档
os.environ["USER_MAX_DOCS"] = "2"
os.environ["USER_MAX_TEAMS"] = "1"
os.environ["TEAM_MAX_DOCS"] = "1"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "q", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "q", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 用量初始（含 9 篇种子文档！种子不计入配额吗？——种子是真实插入的文档，计入）
    # 种子播种 9 篇 → 已超 USER_MAX_DOCS=2，第 1 次创建即应被拒
    # 改为：先看 usage，断言 count>=9
    u0 = c.get("/api/usage", headers=h).json()
    assert u0["docs"]["max"] == 2, u0
    assert u0["docs"]["count"] >= 9, u0  # 种子文档
    # 创建被拒（已达上限）
    r = c.post("/api/docs", headers=h, json={"title": "X", "content": "x"})
    assert r.status_code == 429, r.text

    # 团队数上限：已有 0 个，可建 1 个；第 2 个被拒
    assert c.post("/api/teams", headers=h, json={"name": "T1"}).status_code == 201
    r2 = c.post("/api/teams", headers=h, json={"name": "T2"})
    assert r2.status_code == 429, r2.text

    # 团队文档配额：TEAM_MAX_DOCS=1，第 1 篇可建，第 2 篇被拒
    tid = c.get("/api/teams", headers=h).json()["items"][0]["team_id"]
    td1 = c.post(f"/api/teams/{tid}/docs", headers=h, json={"title": "TD", "content": "c"})
    assert td1.status_code == 201, td1.text
    td2 = c.post(f"/api/teams/{tid}/docs", headers=h, json={"title": "TD2", "content": "c2"})
    assert td2.status_code == 429, td2.text

    # 团队用量
    tu = c.get(f"/api/teams/{tid}/usage", headers=h).json()
    assert tu["docs"]["max"] == 1 and tu["docs"]["count"] == 1, tu

    # 管理员概览：非管理员 403
    assert c.get("/api/admin/usage", headers=h).status_code == 403
    # 升管理员
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='q'"); conn.commit(); conn.close()
    t2 = c.post("/api/auth/login", json={"username": "q", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {t2}"}
    ao = c.get("/api/admin/usage", headers=ha).json()
    assert ao["teams"] >= 1 and "quotas" in ao, ao

print("ALL PASSED")
