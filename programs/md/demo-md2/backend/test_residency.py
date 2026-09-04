# -*- coding: utf-8 -*-
"""⑯数据驻留分区。
- 启用后：新用户落默认 region 目录；GET /admin/residency 显示 region 配置与计数。
- assign 把用户迁到另一 region：DB 文件物理迁移，读取仍可用（连接池驱逐后新路径重建）。
- 非管理员 403；未知 region 400。
"""
import os, tempfile, json

TMP = tempfile.mkdtemp(prefix="resid_")
EU = os.path.join(TMP, "eu")
US = os.path.join(TMP, "us")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["DATA_RESIDENCY_ENABLED"] = "true"
os.environ["RESIDENCY_REGIONS"] = json.dumps({"eu": {"dir": EU}, "us": {"dir": US}})
os.environ["RESIDENCY_DEFAULT_REGION"] = "eu"

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
    u1_id = c.get("/api/auth/me", headers=h1).json()["user_id"]

    # u1 建文档 → DB 落在 EU 目录
    did = c.post("/api/docs", headers=h1, json={"title": "R", "content": "x"}).json()["doc_id"]
    eu_db = os.path.join(EU, "users", u1_id, "docs.db")
    assert os.path.exists(eu_db), f"用户库应落在 EU: {eu_db}"

    # 概览
    ov = c.get("/api/admin/residency", headers=ha).json()
    assert ov["enabled"] is True, ov
    assert ov["default_region"] == "eu", ov
    assert ov["users_by_region"].get("eu", 0) >= 1, ov
    assert "eu" in ov["regions"] and "us" in ov["regions"], ov

    # 非管理员 403
    assert c.get("/api/admin/residency", headers=h1).status_code == 403
    # 未知 region 400
    assert c.post("/api/admin/residency/assign", headers=ha,
                  json={"scope": "user", "scope_id": u1_id, "region": "apac"}).status_code == 400

    # 分配到 us → 迁移
    ra = c.post("/api/admin/residency/assign", headers=ha,
                json={"scope": "user", "scope_id": u1_id, "region": "us"}).json()
    assert ra["ok"] and ra["moved"] is True, ra
    us_db = os.path.join(US, "users", u1_id, "docs.db")
    assert os.path.exists(us_db), "迁移后库应在 US 目录"
    assert not os.path.exists(eu_db), "旧位置应清空"

    # 读取仍可用（连接池驱逐后从新路径重建）
    g = c.get(f"/api/docs/{did}", headers=h1).json()
    assert g["doc_id"] == did, "迁移后文档可读"

    # 概览计数更新
    ov2 = c.get("/api/admin/residency", headers=ha).json()
    assert ov2["users_by_region"].get("us", 0) >= 1, ov2

    # 解除 region（region=""）→ 回默认目录（DOC_DATA_DIR）
    rd = c.post("/api/admin/residency/assign", headers=ha,
                json={"scope": "user", "scope_id": u1_id, "region": ""}).json()
    assert rd["ok"], rd
    g2 = c.get(f"/api/docs/{did}", headers=h1).json()
    assert g2["doc_id"] == did, "解除驻留后仍可读"

print("ALL PASSED")
