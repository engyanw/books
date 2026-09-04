# -*- coding: utf-8 -*-
"""P1-6 多区域 active-active 边界回归。
覆盖：
- /api/admin/storage-mode 暴露 region/pg_role/residency/multi_region_* 字段
- 默认：region=default、pg_role=standalone(SQLite)、active_active=False、边界=single_region_write
- DEPLOY_REGION/PG_REPLICA_ROLE 环境覆盖（独立进程）
- 非管理员 403
- active-active 写路径不支持：MULTI_REGION_ACTIVE_ACTIVE=true 仍标记边界为不支持
"""
import os, tempfile, subprocess, sys, textwrap

TMP = tempfile.mkdtemp(prefix="mreg_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["DEPLOY_REGION"] = "cn-east-1"
# PG_REPLICA_ROLE 不设 → SQLite 下应为 "standalone"

from fastapi.testclient import TestClient
import main  # noqa: E402


def _make_admin(c):
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username=?", ("admin",))
    conn.commit(); conn.close()
    return c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]


with TestClient(main.app) as c:
    tok = _make_admin(c)
    h = {"Authorization": f"Bearer {tok}"}
    # 普通用户
    ct = c.post("/api/auth/register", json={"username": "u2", "password": "p@ssw0rd"}).json()["token"]
    hn = {"Authorization": f"Bearer {ct}"}

    # 非管理员 → 403
    assert c.get("/api/admin/storage-mode", headers=hn).status_code == 403

    r = c.get("/api/admin/storage-mode", headers=h)
    assert r.status_code == 200, r.text
    info = r.json()
    # 新增多区域字段齐备
    for k in ("region", "pg_role", "residency_enabled", "residency_regions",
              "multi_region_active_active", "multi_region_boundary", "multi_region_supported_via"):
        assert k in info, (k, info)
    # 默认 SQLite 单区
    assert info["region"] == "cn-east-1", info["region"]
    assert info["pg_role"] == "standalone", info["pg_role"]
    assert info["multi_region_active_active"] is False
    assert info["multi_region_boundary"] == "single_region_write", info["multi_region_boundary"]
    assert info["multi_region_supported_via"] == "none"  # SQLite 无副本
    assert info["residency_enabled"] is False
    assert isinstance(info["residency_regions"], list)

print("ALL PASSED")

# 独立进程：PG_REPLICA_ROLE=replica + MULTI_REGION_ACTIVE_ACTIVE=true
# → pg_role=replica；即便声明 active-active，边界仍标 active_active_write_unsupported
_sub = textwrap.dedent(
    """
    import os, tempfile
    os.environ["DOC_DATA_DIR"] = tempfile.mkdtemp(prefix="mreg2_")
    os.environ["REGISTRY_DB_PATH"] = os.path.join(os.environ["DOC_DATA_DIR"], "registry.db")
    os.environ["AUTH_ALLOW_REGISTER"] = "true"
    os.environ["DEPLOY_REGION"] = "eu-west-1"
    os.environ["PG_REPLICA_ROLE"] = "replica"
    os.environ["MULTI_REGION_ACTIVE_ACTIVE"] = "true"
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
        import sqlite3 as _s
        _r = _s.connect(os.environ["REGISTRY_DB_PATH"])
        _r.execute("UPDATE users SET is_admin=1 WHERE username=?", ("admin",))
        _r.commit(); _r.close()
        t = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
        h = {"Authorization": f"Bearer {t}"}
        info = c.get("/api/admin/storage-mode", headers=h).json()
        assert info["region"] == "eu-west-1", info
        assert info["pg_role"] == "replica", info
        assert info["multi_region_active_active"] is True
        # 写路径边界仍标不支持（active-active 写不在此版本）
        assert info["multi_region_boundary"] == "active_active_write_unsupported", info
    print("REPLICA PASSED")
    """
)
_env = dict(os.environ)
_env.pop("PG_REPLICA_ROLE", None)
out = subprocess.run([sys.executable, "-c", _sub], capture_output=True, text=True,
                     timeout=120, env=_env)
print(out.stdout)
if out.returncode != 0:
    print(out.stderr)
    raise SystemExit("replica-role case failed")
