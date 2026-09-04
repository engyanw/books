# -*- coding: utf-8 -*-
"""P2-5: 邮件邀请 Guest（邀请令牌 + 接受设密码）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="ginv_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "host", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "host", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 生成邀请
    r = c.post("/api/guests/invite", json={"guest_username": "extern", "email": "extern@ex.com"}, headers=h)
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    invite_url = r.json()["invite_url"]
    assert "/api/guests/accept?token=" in invite_url, invite_url

    # 无密码 → 返回 pending
    r = c.get(f"/api/guests/accept?token={token}")
    assert r.status_code == 200 and r.json()["status"] == "pending", r.text

    # 带密码接受
    r = c.get(f"/api/guests/accept?token={token}&password=guestpw1")
    assert r.status_code == 200 and r.json()["status"] == "accepted", r.text
    assert r.json()["username"] == "extern", r.text

    # Guest 可登录
    r = c.post("/api/auth/login", json={"username": "extern", "password": "guestpw1"})
    assert r.status_code == 200 and "token" in r.json(), r.text

    # 令牌已用 → 404
    assert c.get(f"/api/guests/accept?token={token}&password=x").status_code == 404

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
