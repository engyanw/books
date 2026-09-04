# -*- coding: utf-8 -*-
"""P2 合规框架控制映射：SOC2 / ISO27001 / GDPR。
- GET /api/admin/compliance 返回三个框架，每个含控制项 + 证据点。
- ?format=csv 返回 CSV（含表头）。
- 非管理员 403。
"""
import os, tempfile, csv, io

TMP = tempfile.mkdtemp(prefix="comp_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'"); conn.commit(); conn.close()
    ta = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}

    data = c.get("/api/admin/compliance", headers=ha).json()
    assert {"SOC2", "ISO27001", "GDPR"} <= set(data.keys()), data
    # 每个框架有 controls 列表且非空
    for fk in ("SOC2", "ISO27001", "GDPR"):
        ctrls = data[fk]["controls"]
        assert isinstance(ctrls, list) and len(ctrls) >= 3, (fk, ctrls)
        assert "control" in ctrls[0] and "evidence" in ctrls[0], ctrls[0]
    # 证据点指向真实系统功能（抽样）
    soc2_controls = {c["control"]: c for c in data["SOC2"]["controls"]}
    assert any("/api/admin/backup" in e for c in data["SOC2"]["controls"] for e in c["evidence"]), "应有备份证据"
    assert any("DLP" in e or "_doc_egress_guard" in e for c in data["SOC2"]["controls"] for e in c["evidence"]), "应有 DLP 证据"

    # CSV 导出
    csv_resp = c.get("/api/admin/compliance?fmt=csv", headers=ha)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"], csv_resp.headers["content-type"]
    rows = list(csv.reader(io.StringIO(csv_resp.text)))
    assert [c.lstrip("﻿") for c in rows[0]] == ["framework", "control", "title", "evidence", "config"], rows[0]
    assert len(rows) > 5 and any(r[0] == "GDPR" for r in rows[1:]), rows

    # 非管理员 403
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    tu = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    assert c.get("/api/admin/compliance", headers={"Authorization": f"Bearer {tu}"}).status_code == 403

print("ALL PASSED")
