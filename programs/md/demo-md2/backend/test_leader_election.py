# -*- coding: utf-8 -*-
"""⑮后台任务 leader 选举。
- 启用后：本实例续租成功 → _am_leader True；admin/leader 显示 leader==自身。
- 两个进程（同注册库）竞争：先到者持租约；过期后被抢占。
- 未启用（默认）→ _am_leader 恒 True（向后兼容）。
"""
import os, tempfile, asyncio, sqlite3, time

TMP = tempfile.mkdtemp(prefix="leader_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["LEADER_ELECTION_ENABLED"] = "true"
os.environ["LEADER_LEASE_TTL_SECONDS"] = "2"   # 短 TTL 便于测过期抢占
os.environ["LEADER_RENEW_INTERVAL_SECONDS"] = "1"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'"); conn.commit(); conn.close()
    ta = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}

    # 本实例续租 → 是 leader
    assert asyncio.run(main._renew_leader_lease()) is True
    st = c.get("/api/admin/leader", headers=ha).json()
    assert st["enabled"] is True, st
    assert st["is_leader"] is True, st
    assert st["leader"] == main._INSTANCE_ID, st
    me = main._INSTANCE_ID

    # 模拟另一实例：篡改租约持有者为别的 id + 未过期 → 本实例续租失败（不是 leader）
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE leader_lease SET holder='other-instance', expires_at=? WHERE id=1",
                 (str(int(time.time()) + 10),))
    conn.commit(); conn.close()
    assert asyncio.run(main._renew_leader_lease()) is False, "租约被他人持有时应非 leader"
    st2 = c.get("/api/admin/leader", headers=ha).json()
    assert st2["leader"] == "other-instance" and st2["is_leader"] is False, st2

    # 租约过期后 → 本实例抢占成功
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE leader_lease SET expires_at=? WHERE id=1", (str(int(time.time()) - 1),))
    conn.commit(); conn.close()
    assert asyncio.run(main._renew_leader_lease()) is True, "过期后应抢占成功"
    st3 = c.get("/api/admin/leader", headers=ha).json()
    assert st3["leader"] == me and st3["is_leader"] is True, st3

    # 非管理员 403
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    tu = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    assert c.get("/api/admin/leader", headers={"Authorization": f"Bearer {tu}"}).status_code == 403

print("ALL PASSED")
