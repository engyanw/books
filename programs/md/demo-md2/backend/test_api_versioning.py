# -*- coding: utf-8 -*-
"""P2-b API 版本化回归。
覆盖：
- GET /api/version 清单（公开）
- /api/v1/* 透明重写为 /api/*（复用端点）+ X-API-Version: v1 头
- 未版本化 /api/* 仍可用且无版本头
- 版本化别名走鉴权（未登录 401/403 一致）
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="apiver_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    # 清单
    r = c.get("/api/version")
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["current"] == "v1"
    assert "v1" in m["supported"]
    assert m["versioned_prefix"] == "/api/v1"
    assert m["unversioned_prefix"] == "/api"

    # 版本化别名 → 复用 /api/languages（公开未鉴权端点）
    r2 = c.get("/api/v1/languages")
    assert r2.status_code == 200, r2.text
    assert r2.headers.get("x-api-version") == "v1", dict(r2.headers)

    # 未版本化仍可用，无版本头
    r3 = c.get("/api/languages")
    assert r3.status_code == 200
    assert "x-api-version" not in {k.lower() for k in r3.headers}

    # 版本化别名走鉴权链路：/api/v1/docs 未登录 → 与未版本化一致（401/403）
    rv = c.get("/api/v1/docs")
    ru = c.get("/api/docs")
    assert rv.status_code == ru.status_code, (rv.status_code, ru.status_code)
    assert rv.status_code in (401, 403)

    # 版本化别名完成鉴权流程：注册→登录→列文档
    u = "ver_" + os.urandom(4).hex()
    rr = c.post("/api/v1/auth/register", json={"username": u, "password": "p@ssw0rd"})
    assert rr.status_code == 200, rr.text
    assert rr.headers.get("x-api-version") == "v1"
    tok = c.post("/api/v1/auth/login", json={"username": u, "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    rl = c.get("/api/v1/docs", headers=h)
    assert rl.status_code == 200, rl.text
    assert rl.headers.get("x-api-version") == "v1"
    assert isinstance(rl.json().get("items", rl.json()), list) or "items" in rl.json()

print("ALL PASSED")
