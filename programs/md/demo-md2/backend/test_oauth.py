# -*- coding: utf-8 -*-
"""P2-F：OAuth2 开放 API + SDK。

验证完整授权码流：
- 注册客户端（client_id/secret，明文 secret 仅一次）
- /oauth/authorize：用户登录态授权 → 302 回调带 code
- /oauth/token：code+secret 换 access_token
- access_token 可访问 /api/docs（docs:read 命中）
- scope 不足时写接口 403（docs:write 缺失）
- PAT/会话令牌不受 scope 限制（仍可写）
- /api/v1/openapi 发现端点列出路由与 scope
- SDK（sdk.mde_client.MDEClient）端到端可用
"""
import os, tempfile, shutil
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="oauth_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def reg(c, u):
    c.post("/api/auth/register", json={"username": u, "password": "pw123456"})
    return c.post("/api/auth/login", json={"username": u, "password": "pw123456"}).json()["token"]


with TestClient(main.app) as c:
    alice_tok = reg(c, "alice")
    ha = {"Authorization": f"Bearer {alice_tok}"}
    REDIRECT = "http://localhost:8080/cb"

    # 1) 注册客户端（只读 scope）
    r = c.post("/api/oauth/clients", json={
        "name": "reader-app", "redirect_uris": [REDIRECT], "scopes": ["docs:read"],
    }, headers=ha)
    assert r.status_code == 201, r.text
    client = r.json()
    cid = client["client_id"]; csecret = client["client_secret"]
    assert cid and csecret

    # 2) authorize（不跟随重定向，取 code）
    r = c.get("/oauth/authorize", params={
        "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT,
        "scope": "docs:read", "state": "xyz", "user_token": alice_tok,
    }, follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    loc = r.headers["location"]
    assert "code=oc_" in loc and "state=xyz" in loc, loc
    code = loc.split("code=")[1].split("&")[0]

    # 3) code 换 token
    r = c.post("/oauth/token", data={
        "grant_type": "authorization_code", "client_id": cid, "client_secret": csecret,
        "code": code, "redirect_uri": REDIRECT,
    })
    assert r.status_code == 200, r.text
    at = r.json()["access_token"]
    assert at.startswith("pat_")
    hat = {"Authorization": f"Bearer {at}"}

    # 4) access_token 可读 /api/docs（docs:read 命中）
    r = c.get("/api/docs", headers=hat)
    assert r.status_code == 200, r.text
    # 5) 写接口因缺 docs:write → 403
    r = c.post("/api/docs", json={"title": "x", "content": "y"}, headers=hat)
    assert r.status_code == 403, r.text

    # 6) 同一 code 不能重复用 → 400
    r = c.post("/oauth/token", data={
        "grant_type": "authorization_code", "client_id": cid, "client_secret": csecret,
        "code": code, "redirect_uri": REDIRECT,
    })
    assert r.status_code == 400, r.text

    # 7) 客户端凭据错误 → 401
    r = c.post("/oauth/token", data={
        "grant_type": "authorization_code", "client_id": cid, "client_secret": "wrong",
        "code": "oc_dummy", "redirect_uri": REDIRECT,
    })
    assert r.status_code == 401, r.text

    # 8) PAT/会话令牌不受 scope 限制（alice 自身可写）
    r = c.post("/api/docs", json={"title": "by-alice", "content": "# ok"}, headers=ha)
    assert r.status_code == 201, r.text

# 9) SDK 端到端（用可写 scope 客户端，SDK 经 shim 走 TestClient）
import httpx as _httpx  # noqa: E402
from sdk.mde_client import MDEClient  # noqa: E402


class _ShimHTTP:
    """把 SDK 的 http 调用桥接到 TestClient（同进程 ASGI）。"""
    def __init__(self, client): self._c = client
    def post(self, url, **kw):
        return self._c.post(url.split("://testserver", 1)[1], **kw)
    def get(self, url, **kw):
        return self._c.get(url.split("://testserver", 1)[1], **kw)
    def put(self, url, **kw):
        return self._c.put(url.split("://testserver", 1)[1], **kw)


with TestClient(main.app) as c2:
    tok = reg(c2, "bob")
    hb = {"Authorization": f"Bearer {tok}"}
    r = c2.post("/api/oauth/clients", json={
        "name": "rw-app", "redirect_uris": [REDIRECT], "scopes": ["docs:read", "docs:write"],
    }, headers=hb)
    cl = r.json()
    base_url = "http://testserver"
    sdk = MDEClient(base_url, cl["client_id"], cl["client_secret"], REDIRECT, http=_ShimHTTP(c2))

    # authorize 取 code
    r = c2.get("/oauth/authorize", params={
        "response_type": "code", "client_id": cl["client_id"], "redirect_uri": REDIRECT,
        "scope": "docs:read docs:write", "user_token": tok,
    }, follow_redirects=False)
    code = r.headers["location"].split("code=")[1].split("&")[0]

    # SDK 用注入的 shim 完成 token 交换 + 写 + 读 + 搜索
    at2 = sdk.exchange_code(code)
    assert at2.startswith("pat_")
    created = sdk.create_doc(title="sdk-doc", content="# via sdk")
    assert "doc_id" in created, created
    assert isinstance(sdk.list_docs(), list)
    res = sdk.search("sdk")
    assert any(d.get("title") == "sdk-doc" for d in res), res

# 10) 发现端点
r = c2.get("/api/v1/openapi")
assert r.status_code == 200
disc = r.json()
assert disc["auth"] == "OAuth2 Bearer" and "/oauth/token" in disc["token"], disc
assert any(rt["scope"] == "docs:read" for rt in disc["routes"])

shutil.rmtree(TMP, ignore_errors=True)
print("ALL PASSED")
