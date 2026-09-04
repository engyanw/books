# -*- coding: utf-8 -*-
"""P1-D1：工作流 SLA 超时升级。

验证：阶段超时未决 → 提醒评审人 + 提交人；escalate_to 用户被加入当前阶段可审批；
重复扫描不二次升级。通过直接调用 _workflow_sla_scan_once() 避免等 60s。
"""
import os, tempfile, shutil, sqlite3, asyncio
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="sla_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def reg(c, u):
    c.post("/api/auth/register", json={"username": u, "password": "pw123456"})
    return c.post("/api/auth/login", json={"username": u, "password": "pw123456"}).json()["token"]


def _db():
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"]); conn.row_factory = sqlite3.Row
    return conn


with TestClient(main.app) as c:
    ta = reg(c, "alice"); ha = {"Authorization": f"Bearer {ta}"}
    reg(c, "bob"); reg(c, "carol"); reg(c, "eve")

    did = c.post("/api/docs", json={"title": "sladoc", "content": "# hi"}, headers=ha).json()["doc_id"]
    # 阶段1：bob 审，sla_hours=1，超时升级给 eve；阶段2：carol 审
    wfd = c.post("/api/workflows", json={
        "name": "sla-wf",
        "definition": {"steps": [
            {"reviewers": ["bob"], "mode": "serial", "sla_hours": 1, "escalate_to": "eve"},
            {"reviewers": ["carol"], "mode": "serial"},
        ]},
    }, headers=ha).json()
    st = c.post(f"/api/docs/{did}/workflow/{wfd['id']}/start", headers=ha).json()
    inst_id = st["instance_id"]; rid = st["review_id"]

    # 回填阶段1截止时间为过去（模拟超时）
    conn = _db()
    conn.execute("UPDATE workflow_sla SET deadline=? WHERE instance_id=?", ("2000-01-01T00:00:00+00:00", inst_id))
    conn.commit(); conn.close()

# 在独立事件循环跑单次扫描（registry DB 在磁盘上，跨循环可访问）
n = asyncio.run(main._workflow_sla_scan_once())
assert n == 1, f"应升级 1 个阶段，实际 {n}"

conn = _db()
# 阶段1 已标记 escalated
esc = conn.execute("SELECT escalated FROM workflow_sla WHERE instance_id=? AND stage=0", (inst_id,)).fetchone()
assert esc["escalated"] == 1, "阶段1 应标记已升级"
# eve 被加入当前阶段（stage 0）为并行待审
eve_row = conn.execute(
    "SELECT reviewer_user_id FROM review_steps WHERE review_id=? AND stage=0 AND status='pending' "
    "AND reviewer_user_id=(SELECT user_id FROM users WHERE username='eve')", (rid,)
).fetchone()
assert eve_row is not None, "eve 应被加入阶段0为待审"
# 重复扫描不应再次升级（幂等）
conn.close()
n2 = asyncio.run(main._workflow_sla_scan_once())
assert n2 == 0, f"已升级阶段不应重复升级，实际 {n2}"

# 升级后 eve 应能审批推进（验证 escalate_to 可决）
eve_tok = c2_login = None
with TestClient(main.app) as c2:
    eve_tok = c2.post("/api/auth/login", json={"username": "eve", "password": "pw123456"}).json()["token"]
    he = {"Authorization": f"Bearer {eve_tok}"}
    r = c2.put(f"/api/reviews/{rid}", json={"status": "approved"}, headers=he)
    assert r.status_code == 200, r.text

shutil.rmtree(TMP, ignore_errors=True)
print("ALL PASSED")
