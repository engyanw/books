# -*- coding: utf-8 -*-
"""P2-13 DR 深度：恢复演练真跑通 + RTO/RPO 量化 + PITR 基线查找 + 跨区副本。

覆盖：
1. create_backup 产出备份点 + manifest；list_backups 可见。
2. drill 真跑通：恢复到临时目录、sha256 校验、文件数匹配；返回 rto_seconds/rpo_seconds。
3. 篡改归档 sha256 → drill 失败（ok=False, reason 含 sha256）。
4. PITR find_restore_point：给定 target_epoch 返回不晚于它的最近点；越界返回 {}。
5. 跨区副本 replicate_latest：投递到 REPLICA_DIR，replica_status lag=0、count 一致。
6. HTTP 端点：/api/admin/backup/drill（管理员）、/replica/ship、/replica/status、/backup/pitr。
7. 普通用户(非管理员) 调用受 403 拦截。
"""
import os, tempfile, time, shutil

TMP = tempfile.mkdtemp(prefix="dr_")
DATA = os.path.join(TMP, "data")
REPLICA = os.path.join(TMP, "replica")
os.makedirs(DATA, exist_ok=True)
# 写一些数据文件
with open(os.path.join(DATA, "registry.db"), "w") as f:
    f.write("REGDATA-" + "x" * 1024)
os.makedirs(os.path.join(DATA, "users", "u1"), exist_ok=True)
with open(os.path.join(DATA, "users", "u1", "docs.db"), "w") as f:
    f.write("USERDATA")

os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_DIR"] = os.path.join(TMP, "_backups")
os.environ["BACKUP_KEEP"] = "5"
os.environ["REPLICA_DIR"] = REPLICA
os.environ["DR_RPO_ALERT_SECONDS"] = "3"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import backup as bk  # noqa: E402

# ---- 直接调 backup 模块（核心 DR 能力） ----
BU = os.environ["BACKUP_DIR"]
arc = bk.create_backup(DATA, BU, 5)
assert arc.exists(), arc
points = bk.list_backups(BU)
assert len(points) == 1, points
latest = points[0]
assert latest["sha256"] and latest["file_count"] > 0, latest

# drill 真跑通 + RTO/RPO
rep = bk.drill(BU, DATA)
assert rep["ok"] is True, rep
assert "rto_seconds" in rep and rep["rto_seconds"] >= 0, rep
assert "rpo_seconds" in rep and rep["rpo_seconds"] >= 0, rep
assert rep["restored_files"] == latest["file_count"], rep
print(f"  drill: rto={rep['rto_seconds']}s rpo={rep['rpo_seconds']}s files={rep['restored_files']}")

# 篡改归档 → drill 失败（sha256 不匹配）
import hashlib
arc_path = Path(BU) / latest["archive"]
with open(arc_path, "ab") as f:
    f.write(b"TAMPER")
rep2 = bk.drill(BU, DATA)
assert rep2["ok"] is False and "sha256" in rep2["reason"], rep2
# 恢复归档（重新备份以继续后续测试）
shutil.rmtree(BU); os.makedirs(BU, exist_ok=True)
bk.create_backup(DATA, BU, 5)

# PITR 基线查找
pts = bk.list_backups(BU)
ep = pts[0]["created_at_epoch"]
future = bk.find_restore_point(BU, ep + 10000)
assert future and future["archive"] == pts[0]["archive"], future  # 最近基线
before = bk.find_restore_point(BU, ep - 10000)
assert before == {}, before  # 早于最早备份 → 无

# 跨区副本
ship = bk.replicate_latest(BU, REPLICA)
assert ship["ok"] and ship["lag_seconds"] == 0, ship
status = bk.replica_status(BU, REPLICA)
assert status["enabled"] and status["lag_seconds"] == 0, status
assert status["replica_count"] == status["local_count"], status
print(f"  replica: local={status['local_count']} replica={status['replica_count']} lag={status['lag_seconds']}s")

# ---- HTTP 端点 ----
from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "dradmin", "password": "p@ssw0rd"})
    # 提升为管理员
    import sqlite3 as _s
    conn = _s.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='dradmin'")
    conn.commit(); conn.close()
    c.post("/api/auth/register", json={"username": "druser", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "dradmin", "password": "p@ssw0rd"}).json()["token"]
    tu = c.post("/api/auth/login", json={"username": "druser", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    hu = {"Authorization": f"Bearer {tu}"}

    # 普通用户 403
    assert c.post("/api/admin/backup/drill", headers=hu).status_code == 403
    assert c.get("/api/admin/replica/status", headers=hu).status_code == 403

    # 触发 HTTP 备份
    r = c.post("/api/admin/backup", headers=ha)
    assert r.status_code == 200, r.text
    # drill 端点
    d = c.post("/api/admin/backup/drill", headers=ha)
    assert d.status_code == 200, d.text
    dj = d.json()
    assert dj["ok"] is True and "rto_seconds" in dj and "rpo_seconds" in dj, dj

    # PITR 端点
    pts2 = c.get("/api/admin/backup", headers=ha).json()["items"]
    ep2 = pts2[0]["created_at_epoch"]
    p = c.get(f"/api/admin/backup/pitr?target_epoch={ep2 + 100000}", headers=ha)
    assert p.status_code == 200 and p.json()["point"]["archive"] == pts2[0]["archive"], p.text
    assert c.get(f"/api/admin/backup/pitr?target_epoch={ep2 - 1000000}", headers=ha).status_code == 404

    # 跨区副本投递 + 状态
    s = c.post("/api/admin/replica/ship", headers=ha)
    assert s.status_code == 200 and s.json()["ok"], s.text
    st = c.get("/api/admin/replica/status", headers=ha).json()
    assert st["enabled"] and st["lag_seconds"] == 0, st

print("ALL PASSED")
