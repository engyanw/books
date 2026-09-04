# -*- coding: utf-8 -*-
"""D1 回归：备份导出/导入 API（仅管理员）。
覆盖：list/create/download/restore；非管理员 403；路径穿越校验；force 确认。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="backup_api_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
# 备份目录须在数据目录之外（恢复时会整体移动数据目录）
os.environ["BACKUP_DIR"] = tempfile.mkdtemp(prefix="backup_out_")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    # 管理员账号
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    # 直接置管理员位
    import sqlite3 as _s
    _db = _s.connect(os.path.join(TMP, "registry.db"))
    _db.execute("UPDATE users SET is_admin=1 WHERE username=?", ("admin",))
    _db.commit(); _db.close()
    t = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    # 普通用户
    ct = c.post("/api/auth/register", json={"username": "u2", "password": "p@ssw0rd"}).json()["token"]
    hn = {"Authorization": f"Bearer {ct}"}

    # 非管理员 → 403
    assert c.get("/api/admin/backup", headers=hn).status_code == 403
    assert c.post("/api/admin/backup", headers=hn).status_code == 403

    # list（空）
    r = c.get("/api/admin/backup", headers=h)
    assert r.status_code == 200
    assert r.json()["items"] == []

    # create
    r = c.post("/api/admin/backup", headers=h)
    assert r.status_code == 200, r.text
    point = r.json()["point"]
    assert point and point["archive"].endswith(".tar.gz")
    arc = point["archive"]

    # list 含新建备份
    items = c.get("/api/admin/backup", headers=h).json()["items"]
    assert any(i["archive"] == arc for i in items)

    # download
    d = c.get(f"/api/admin/backup/{arc}/download", headers=h)
    assert d.status_code == 200
    assert len(d.content) > 0
    assert d.headers["content-type"] == "application/gzip"

    # 路径穿越 → 400
    bad = c.get("/api/admin/backup/..%2f..%2fetc%2fpasswd/download", headers=h)
    assert bad.status_code in (400, 404), bad.text

    # restore 无 force → 409
    r2 = c.post("/api/admin/backup/restore", headers=h, json={"archive": arc})
    assert r2.status_code == 409, r2.text

    # restore 非法归档名 → 400
    r3 = c.post("/api/admin/backup/restore", headers=h, json={"archive": "../x.tar.gz", "force": True})
    assert r3.status_code == 400, r3.text

    # restore 合法 + force → 200
    r4 = c.post("/api/admin/backup/restore", headers=h, json={"archive": arc, "force": True})
    assert r4.status_code == 200, r4.text
    assert r4.json()["ok"] is True

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
