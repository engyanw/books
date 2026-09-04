# -*- coding: utf-8 -*-
"""P0-1：并行会签（多人同时审，全部通过才推进）。"""
import os, shutil, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="par_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "pa", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "pb", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "pc", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "pa", "password": "p@ssw0rd"}).json()["token"]
    tb = c.post("/api/auth/login", json={"username": "pb", "password": "p@ssw0rd"}).json()["token"]
    tc = c.post("/api/auth/login", json={"username": "pc", "password": "p@ssw0rd"}).json()["token"]
    ha, hb, hc = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}, {"Authorization": f"Bearer {tc}"}

    did = c.post("/api/docs", json={"title": "par.md", "content": "v1"}, headers=ha).json()["doc_id"]

    # 并行会签：pb + pc 同时审，需全部通过
    r = c.post(f"/api/docs/{did}/review", json={"reviewers": ["pb", "pc"], "mode": "parallel", "comment": "会签"}, headers=ha)
    assert r.status_code == 201, r.text
    assert r.json()["mode"] == "parallel", r.json()
    rid = r.json()["id"]

    # pb 通过 → 不应推进到下一步（pc 还没审）
    r = c.put(f"/api/reviews/{rid}", json={"status": "approved"}, headers=hb)
    assert r.status_code == 200, r.text
    # review 仍为 pending（pc 未审完）
    import sqlite3 as _s
    conn = _s.connect(os.path.join(TMP, "registry.db"))
    st = conn.execute("SELECT status FROM reviews WHERE id=?", (rid,)).fetchone()[0]
    conn.close()
    assert st == "pending", f"并行模式下一人通过不应整体完成: {st}"

    # pc 也通过 → 全部通过 → approved
    r = c.put(f"/api/reviews/{rid}", json={"status": "approved"}, headers=hc)
    assert r.status_code == 200, r.text
    conn = _s.connect(os.path.join(TMP, "registry.db"))
    st2 = conn.execute("SELECT status FROM reviews WHERE id=?", (rid,)).fetchone()[0]
    conn.close()
    assert st2 == "approved", f"两人都通过后应 approved: {st2}"

    # 并行驳回测试
    did2 = c.post("/api/docs", json={"title": "par2.md", "content": "v2"}, headers=ha).json()["doc_id"]
    r = c.post(f"/api/docs/{did2}/review", json={"reviewers": ["pb", "pc"], "mode": "parallel"}, headers=ha)
    rid2 = r.json()["id"]
    # pb 驳回 → 整个关闭
    r = c.put(f"/api/reviews/{rid2}", json={"status": "rejected"}, headers=hb)
    assert r.status_code == 200 and r.json()["status"] == "rejected", r.text
    # pc 再审 → 403
    assert c.put(f"/api/reviews/{rid2}", json={"status": "approved"}, headers=hc).status_code == 403

    # 串行模式不受影响
    did3 = c.post("/api/docs", json={"title": "ser.md", "content": "v3"}, headers=ha).json()["doc_id"]
    r = c.post(f"/api/docs/{did3}/review", json={"reviewers": ["pb", "pc"], "mode": "serial"}, headers=ha)
    rid3 = r.json()["id"]
    # pb 审（串行第一步）→ 推进到 pc
    r = c.put(f"/api/reviews/{rid3}", json={"status": "approved"}, headers=hb)
    assert r.status_code == 200, r.text
    # pc 审 → approved
    r = c.put(f"/api/reviews/{rid3}", json={"status": "approved"}, headers=hc)
    assert r.status_code == 200, r.text

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
