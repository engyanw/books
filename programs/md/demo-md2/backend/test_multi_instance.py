# -*- coding: utf-8 -*-
"""P1-3 多实例一致性约束。
- 默认（SQLite 单实例）→ storage-mode.request_path_consistent=True。
- MULTI_INSTANCE_HA=true + SQLite + 非共享 → unsafe=True、recommendation=pg。
- 叠加 DOC_DATA_DIR_SHARED=true → unsafe=False、recommendation=shared_fs。
- 非管理员 403。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="mi_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["MULTI_INSTANCE_HA"] = "true"  # 声明多实例，但非共享 FS

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'"); conn.commit(); conn.close()
    ta = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}

    # 多实例 + SQLite + 非共享 → 不安全，建议 PG
    st = c.get("/api/admin/storage-mode", headers=ha).json()
    assert st["backend"] == "sqlite_per_user", st
    assert st["multi_instance"] is True, st
    assert st["data_dir_shared"] is False, st
    assert st["unsafe"] is True, st
    assert st["request_path_consistent"] is False, st
    assert st["recommendation"] == "pg", st

    # 非管理员 403
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    tu = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    assert c.get("/api/admin/storage-mode", headers={"Authorization": f"Bearer {tu}"}).status_code == 403

# 叠加共享 FS → 安全（降级）
os.environ["DOC_DATA_DIR_SHARED"] = "true"
import importlib, sys
for _m in list(sys.modules):
    if _m == "main" or _m == "config" or _m.startswith("config."):
        del sys.modules[_m]
import main as main2  # noqa: E402
with TestClient(main2.app) as c2:
    c2.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'"); conn.commit(); conn.close()
    ta2 = c2.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    st2 = c2.get("/api/admin/storage-mode", headers={"Authorization": f"Bearer {ta2}"}).json()
    assert st2["unsafe"] is False, st2
    assert st2["recommendation"] == "shared_fs", st2

# 单实例默认（关掉多实例声明）→ 一致
os.environ["MULTI_INSTANCE_HA"] = "false"
os.environ["DOC_DATA_DIR_SHARED"] = "false"
for _m in list(sys.modules):
    if _m == "main" or _m == "config" or _m.startswith("config."):
        del sys.modules[_m]
import main as main3  # noqa: E402
with TestClient(main3.app) as c3:
    c3.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'"); conn.commit(); conn.close()
    ta3 = c3.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    st3 = c3.get("/api/admin/storage-mode", headers={"Authorization": f"Bearer {ta3}"}).json()
    assert st3["multi_instance"] is False, st3
    assert st3["unsafe"] is False, st3
    assert st3["request_path_consistent"] is True, st3

print("ALL PASSED")
