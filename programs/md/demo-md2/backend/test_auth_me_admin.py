# -*- coding: utf-8 -*-
"""前端集成回归：/api/auth/me 须返回 is_admin，供前端门控管理面板按钮。"""
import os, shutil, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="me_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "u1", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "u1", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 普通用户：is_admin 字段存在且为 False
    me = c.get("/api/auth/me", headers=h).json()
    assert "is_admin" in me, f"/api/auth/me 缺少 is_admin 字段: {me}"
    assert me["is_admin"] is False, me
    assert me["username"] == "u1"

    # 非管理员访问 admin 端点 → 403
    assert c.get("/api/admin/kms/status", headers=h).status_code == 403
    assert c.get("/api/admin/deps", headers=h).status_code == 403

    # 提升为管理员后：is_admin 变 True，admin 端点放行
    conn = sqlite3.connect(os.path.join(TMP, "registry.db"))
    conn.execute("UPDATE users SET is_admin=1 WHERE username='u1'")
    conn.commit(); conn.close()
    me2 = c.get("/api/auth/me", headers=h).json()
    assert me2["is_admin"] is True, me2
    assert c.get("/api/admin/kms/status", headers=h).status_code == 200
    assert c.get("/api/admin/deps", headers=h).status_code == 200

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
