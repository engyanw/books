# -*- coding: utf-8 -*-
"""#1 OAuth scope 收紧回归。
此前：OAuth docs:read 令牌可触达删除/管理员等未声明路由（_require_user 不校验 scope）。
现：OAuth 令牌（有 scope 行）被限制在 OPEN_API_ROUTES 开放面；PAT/会话令牌全权限不变。
"""
import os, tempfile, shutil
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="scope_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def reg(c, u):
    c.post("/api/auth/register", json={"username": u, "password": "pw123456"})
    return c.post("/api/auth/login", json={"username": u, "password": "pw123456"}).json()["token"]


def oauth_token(c, owner_tok, scope):
    """走授权码流拿到指定 scope 的 OAuth access_token。"""
    ha = {"Authorization": f"Bearer {owner_tok}"}
    REDIRECT = "http://localhost:8080/cb"
    r = c.post("/api/oauth/clients", json={
        "name": f"app-{scope}", "redirect_uris": [REDIRECT], "scopes": [scope],
    }, headers=ha)
    assert r.status_code == 201, r.text
    client = r.json()
    cid, csecret = client["client_id"], client["client_secret"]
    r = c.get("/oauth/authorize", params={
        "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT,
        "scope": scope, "state": "st", "user_token": owner_tok,
    }, follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    code = r.headers["location"].split("code=")[1].split("&")[0]
    r = c.post("/oauth/token", data={
        "grant_type": "authorization_code", "client_id": cid, "client_secret": csecret,
        "code": code, "redirect_uri": REDIRECT,
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


with TestClient(main.app) as c:
    owner = reg(c, "owner_scope")
    ha = {"Authorization": f"Bearer {owner}"}

    # 预置一篇文档（用会话令牌，全权限）供后续 DELETE/PUT 测试
    did = c.post("/api/docs", json={"title": "t", "content": "# body"}, headers=ha).json()["doc_id"]

    # OAuth docs:read 令牌
    ro = oauth_token(c, owner, "docs:read")
    hro = {"Authorization": f"Bearer {ro}"}

    # 1) 在开放面 + scope 命中 → 200
    assert c.get("/api/docs", headers=hro).status_code == 200

    # 2) 在开放面但 scope 不足（POST 需 docs:write）→ 403
    assert c.post("/api/docs", json={"title": "x", "content": "y"}, headers=hro).status_code == 403

    # 3) 不在开放面 → 403（无论 scope）：删除文档
    assert c.delete(f"/api/docs/{did}", headers=hro).status_code == 403

    # 4) 不在开放面 → 403：管理员接口
    assert c.get("/api/admin/metrics", headers=hro).status_code == 403

    # 5) 不在开放面 → 403：文档子资源（scan-secrets）
    assert c.post(f"/api/docs/{did}/scan-secrets", headers=hro).status_code == 403

    # 6) OAuth docs:write 令牌：在开放面 + scope 命中 → 可写；但仍不可删除（不在开放面）
    rw = oauth_token(c, owner, "docs:write")
    hrw = {"Authorization": f"Bearer {rw}"}
    assert c.put(f"/api/docs/{did}", json={"content": "# updated"}, headers=hrw).status_code == 200
    assert c.delete(f"/api/docs/{did}", headers=hrw).status_code == 403  # 写令牌也不得删除

    # 7) PAT（控制台签发，无 scope 行）→ 全权限，可删除（不受开放面限制）
    pat = c.post("/api/tokens", json={"name": "auto"}, headers=ha).json()["token"]
    hpat = {"Authorization": f"Bearer {pat}"}
    # PAT 能读、能删（证明仅 OAuth 三方令牌被收紧）
    assert c.get("/api/docs", headers=hpat).status_code == 200
    assert c.delete(f"/api/docs/{did}", headers=hpat).status_code == 200

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
