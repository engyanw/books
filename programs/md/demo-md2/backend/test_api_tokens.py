# -*- coding: utf-8 -*-
"""T6：API Token（REST 自动化，双 Bearer 认证）+ 管理后台指标。"""
import os, shutil, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="t6_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "auto", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "auto", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 1) 创建 API token（明文仅返回一次）
    r = c.post("/api/tokens", json={"name": "ci-bot"}, headers=h)
    assert r.status_code == 201, r.text
    pat = r.json()["token"]
    assert pat.startswith("pat_")
    tid = r.json()["id"]
    assert "token" not in c.get("/api/tokens", headers=h).json()["items"][0]  # 列表无明文

    # 2) 用 API token 访问需鉴权接口（POST /api/docs）—— Bearer 头带 API token
    pat_h = {"Authorization": f"Bearer {pat}"}
    r = c.post("/api/docs", json={"title": "via-api.md", "content": "auto"}, headers=pat_h)
    assert r.status_code == 201, r.text  # API token 鉴权通过

    # 3) last_used 更新
    lst = c.get("/api/tokens", headers=h).json()["items"][0]
    assert lst["last_used"] is not None, lst

    # 4) 错误 token 401
    bad = {"Authorization": "Bearer pat_invalid_xxx"}
    assert c.get("/api/docs", headers=bad).status_code == 401

    # 5) 删除 token
    assert c.delete(f"/api/tokens/{tid}", headers=h).status_code == 200
    # 删除后该 token 失效
    assert c.post("/api/docs", json={"title": "x"}, headers=pat_h).status_code == 401

    # 6) 指标端点：非 admin 403
    assert c.get("/api/admin/metrics", headers=h).status_code == 403
    # 设为 admin
    conn = sqlite3.connect(os.path.join(TMP, "registry.db")); conn.execute("UPDATE users SET is_admin=1 WHERE username='auto'"); conn.commit(); conn.close()
    m = c.get("/api/admin/metrics", headers=h).json()
    assert m["users"] == 1 and m["docs"] >= 1 and "ai_calls_total" in m, m
    print("metrics:", m)

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
