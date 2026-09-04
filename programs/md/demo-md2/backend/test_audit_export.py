# -*- coding: utf-8 -*-
"""审计日志留存与导出：CSV/JSON 导出 + 留存清理。"""
import os, tempfile, sqlite3, json
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="aud_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def make_admin(c):
    c.post("/api/auth/register", json={"username": "root", "password": "pw123456"})
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='root'")
    conn.commit(); conn.close()
    return c.post("/api/auth/login", json={"username": "root", "password": "pw123456"}).json()["token"]


with TestClient(main.app) as c:
    tok = make_admin(c)
    h = {"Authorization": f"Bearer {tok}"}
    # 直接造 5 条审计记录
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    import datetime as _dt
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
    for i in range(5):
        conn.execute("INSERT INTO audit_log (ts, user_id, action, target_type, target_id) VALUES (?,?,?,?,?)",
                     (now_iso, "root", f"test.event.{i}", "x", str(i)))
    # 插入一条旧记录（2 年前）测留存清理
    old_ts = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=730)).isoformat()
    conn.execute("INSERT INTO audit_log (ts, user_id, action, target_type, target_id) VALUES (?,?,?,?,?)",
                 (old_ts, "root", "test.old", "x", "1"))
    conn.commit()
    total_before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    assert total_before >= 6

    # 1) JSON 导出
    r = c.get("/api/admin/audit/export?fmt=json", headers=h)
    assert r.status_code == 200, r.text
    items = json.loads(r.text)
    assert isinstance(items, list) and len(items) >= 5
    assert all("action" in x for x in items)

    # 2) CSV 导出
    r2 = c.get("/api/admin/audit/export?fmt=csv", headers=h)
    assert r2.status_code == 200 and "text/csv" in r2.headers.get("content-type", "")
    assert "action" in r2.text  # header

    # 3) 非管理员 → 403
    c.post("/api/auth/register", json={"username": "plain", "password": "pw123456"})
    pt = c.post("/api/auth/login", json={"username": "plain", "password": "pw123456"}).json()["token"]
    assert c.get("/api/admin/audit/export?fmt=json", headers={"Authorization": f"Bearer {pt}"}).status_code == 403

    # 4) 留存清理：设 AUDIT_RETENTION_DAYS=30 → 清掉 2 年前的旧记录
    main.AUDIT_RETENTION_DAYS = 30
    res = c.post("/api/admin/audit/retention", headers=h).json()
    assert res["purged"] >= 1, res
    # 旧记录已删（留存策略生效）；导出/清理本身会新增审计，故不比总数
    conn2 = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    assert conn2.execute("SELECT COUNT(*) FROM audit_log WHERE action='test.old'").fetchone()[0] == 0
    conn2.close()

print("ALL PASSED")
