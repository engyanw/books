# -*- coding: utf-8 -*-
"""登出 + SLO：吊销本地 token（立即失效）+ SSO 全局登出 URL。"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="slo_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    # 注册并登录
    c.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})
    r = c.post("/api/auth/login", json={"username": "alice", "password": "pw123456"})
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # 登出前 token 可用
    assert c.get("/api/auth/me", headers=h).status_code == 200

    # 登出：吊销
    out = c.post("/api/auth/logout", headers=h).json()
    assert out["logged_out"] is True, out
    # 未配 SSO → sso_logout_url 为空
    assert out["sso_logout_url"] == "", out

    # 登出后 token 立即失效（401）
    r2 = c.get("/api/auth/me", headers=h)
    assert r2.status_code == 401, r2.text

    # 重复登出同一 token 仍 401（吊销名单持久）
    assert c.get("/api/auth/me", headers=h).status_code == 401

    # 重新登录获得新 token 仍可用
    r3 = c.post("/api/auth/login", json={"username": "alice", "password": "pw123456"})
    new_token = r3.json()["token"]
    assert new_token != token
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200

print("ALL PASSED")
