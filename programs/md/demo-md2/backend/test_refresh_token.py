# -*- coding: utf-8 -*-
"""B1 回归：Refresh Token 轮换 + access/refresh 分离。
覆盖：
  - 登录返回 access + refresh；
  - access 可调 API，refresh 不可调普通 API（401）；
  - /api/auth/refresh 轮换：旧 refresh 失效、新 access+refresh 可用；
  - 登出吊销 refresh。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="refresh_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 短 TTL 便于验证过期回退；refresh 长 TTL
os.environ["AUTH_ACCESS_TTL"] = "1"   # 1 秒
os.environ["AUTH_REFRESH_TTL"] = "3600"

import main  # noqa: E402

with TestClient(main.app) as c:
    # 注册 → 拿 access + refresh
    r = c.post("/api/auth/register", json={"username": "u1", "password": "p@ssw0rd"})
    assert r.status_code == 200, r.text
    data = r.json()
    access = data["access"]
    refresh = data["refresh"]
    assert access and refresh, data
    assert data["token"] == access  # 兼容字段
    h = {"Authorization": f"Bearer {access}"}

    # access 可调普通 API
    me = c.get("/api/auth/me", headers=h).json()
    assert me["username"] == "u1", me

    # refresh 不得用于普通 API 访问 → 401
    hr = {"Authorization": f"Bearer {refresh}"}
    assert c.get("/api/auth/me", headers=hr).status_code == 401

    # 用 refresh 换发新 access+refresh
    r2 = c.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    new_access = d2["access"]
    new_refresh = d2["refresh"]
    assert new_access and new_refresh
    assert new_access != access
    assert new_refresh != refresh

    # 旧 refresh 已轮换失效
    assert c.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    # 新 access 可用
    hn = {"Authorization": f"Bearer {new_access}"}
    assert c.get("/api/auth/me", headers=hn).json()["username"] == "u1"

    # 登出：吊销 refresh（带新 refresh）
    c.post("/api/auth/logout", json={"refresh_token": new_refresh}, headers=hn)
    # 登出后旧 access 仍在 TTL 内但应已登出（access 也被 revoke）
    # refresh 已失效
    assert c.post("/api/auth/refresh", json={"refresh_token": new_refresh}).status_code == 401

    # 非法 refresh → 401
    assert c.post("/api/auth/refresh", json={"refresh_token": "garbage"}).status_code == 401
    # 缺 refresh → 400
    assert c.post("/api/auth/refresh", json={}).status_code == 400

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
