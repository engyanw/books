# -*- coding: utf-8 -*-
"""P0-4 审计完整性与防篡改：hash 链校验 + 篡改检测 + 留存 re-anchor。

覆盖：
1. 触发若干审计动作后，/api/audit/verify 报告链完整（intact=true, broken_count=0）。
2. 直改 registry 库中某行 record_hash → verify 报 broken（record_hash 类）。
3. 直改某行 prev_hash 字段 → verify 报 broken（prev_hash_link 类，本轮新增检查）。
4. 留存清理：插一条 2 天前的审计行，AUDIT_RETENTION_DAYS=1 触发 purge → 该行被删，
   且存活链经 re-anchor 后 verify 仍 intact（证明压缩不破坏可校验性）。
"""
import os, sqlite3, tempfile

TMP = tempfile.mkdtemp(prefix="audit_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["AUDIT_RETENTION_DAYS"] = "1"   # 留存 1 天

from fastapi.testclient import TestClient
import main  # noqa: E402
from main import REGISTRY_DB_PATH  # noqa: E402


def _reg_conn():
    con = sqlite3.connect(REGISTRY_DB_PATH)
    con.row_factory = sqlite3.Row
    return con


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "aud", "password": "p@ssw0rd"})
    # 提权为管理员（直改库）
    with _reg_conn() as con:
        con.execute("UPDATE users SET is_admin=1 WHERE username='aud'")
        con.commit()
    t = c.post("/api/auth/login", json={"username": "aud", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 1) 触发审计动作（建文档 + 建 token 各调 _audit）
    did = c.post("/api/docs", headers=h, json={"title": "T", "content": "x"}).json()["doc_id"]
    c.put(f"/api/docs/{did}", headers=h, json={"content": "y", "title": "T"})
    c.post("/api/tokens", headers=h, json={"name": "p"}).json()
    v = c.get("/api/audit/verify", headers=h).json()
    assert v["intact"] and v["broken_count"] == 0, v

    # 2) 篡改最新行 record_hash → verify 应报 record_hash 类 broken
    with _reg_conn() as con:
        row = con.execute("SELECT id, record_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        last_id, rh = row["id"], row["record_hash"]
        con.execute("UPDATE audit_log SET record_hash='TAMPEREDHASH' WHERE id=?", (last_id,))
        con.commit()
    v2 = c.get("/api/audit/verify", headers=h).json()
    assert not v2["intact"] and v2["broken_count"] >= 1, v2
    assert any(b.get("kind") == "record_hash" for b in v2["broken"]), v2
    # 还原
    with _reg_conn() as con:
        con.execute("UPDATE audit_log SET record_hash=? WHERE id=?", (rh, last_id))
        con.commit()

    # 3) 篡改某行 prev_hash 字段 → verify 应报 prev_hash_link 类 broken（新增检查）
    with _reg_conn() as con:
        row = con.execute("SELECT id, prev_hash FROM audit_log ORDER BY id ASC LIMIT 1 OFFSET 1").fetchone()
        mid_id, ph = row["id"], row["prev_hash"]
        con.execute("UPDATE audit_log SET prev_hash='TAMPEREDPREV' WHERE id=?", (mid_id,))
        con.commit()
    v3 = c.get("/api/audit/verify", headers=h).json()
    assert not v3["intact"], v3
    assert any(b.get("kind") == "prev_hash_link" for b in v3["broken"]), v3
    # 还原
    with _reg_conn() as con:
        con.execute("UPDATE audit_log SET prev_hash=? WHERE id=?", (ph, mid_id))
        con.commit()
    assert c.get("/api/audit/verify", headers=h).json()["intact"]

    # 4) 留存清理 + re-anchor：插一条 2 天前的旧行，purge 后链仍 intact
    with _reg_conn() as con:
        import datetime
        old_ts = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).isoformat()
        con.execute(
            "INSERT INTO audit_log (ts, user_id, action, target_id, detail, prev_hash, record_hash, org_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (old_ts, "u_legacy", "legacy.action", "x", "old", "GENESIS", "deadbeef", None),
        )
        con.commit()
    # purge 前先 verify（链可能因旧行 prev_hash=GENESIS 不衔接而 broken——可接受）
    purge = c.post("/api/admin/audit/retention", headers=h).json()
    assert purge["purged"] >= 1, purge
    # purge 后存活链 re-anchor，verify 应 intact
    v4 = c.get("/api/audit/verify", headers=h).json()
    assert v4["intact"], v4

print("ALL PASSED")
