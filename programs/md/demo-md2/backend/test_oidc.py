# -*- coding: utf-8 -*-
"""OIDC SSO 流程：login→IdP→callback→本地 token。用 mock IdP 验证。"""
import os, shutil, tempfile, threading, json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="oidc_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

# 配置 OIDC 指向 mock IdP（用显式端点覆盖 discovery）
MOCK_HOST = "127.0.0.1"
srv = HTTPServer((MOCK_HOST, 0), type("H", (BaseHTTPRequestHandler,), {
    "def do_GET(self):": None,
}) if False else BaseHTTPRequestHandler)
# 用闭包变量传递 state 校验
captured = {"state": None}

class MockIdP(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/.well-known/openid-configuration":
            self._json(200, {
                "authorization_endpoint": f"http://{MOCK_HOST}:{PORT}/auth",
                "token_endpoint": f"http://{MOCK_HOST}:{PORT}/token",
                "userinfo_endpoint": f"http://{MOCK_HOST}:{PORT}/userinfo",
            })
        elif u.path == "/auth":
            # IdP 授权端点应重定向回 redirect_uri?code=...&state=...
            q = parse_qs(u.query)
            captured["state"] = q.get("state", [""])[0]
            redir = q["redirect_uri"][0]
            from urllib.parse import urlencode
            self.send_response(302); self.send_header("Location", f"{redir}?{urlencode({'code':'mockcode','state':q['state'][0]})}"); self.end_headers()
        elif u.path == "/userinfo":
            self._json(200, {"sub": "oidc-sub-001", "preferred_username": "sso_alice", "email": "alice@ex.com"})
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/token":
            self._json(200, {"access_token": "mock-access", "token_type": "Bearer"})
        else:
            self.send_response(404); self.end_headers()
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

srv = HTTPServer((MOCK_HOST, 0), MockIdP)
PORT = srv.server_address[1]
MOCK_BASE = f"http://{MOCK_HOST}:{PORT}"
threading.Thread(target=srv.serve_forever, daemon=True).start()

os.environ["OIDC_ISSUER"] = MOCK_BASE
os.environ["OIDC_CLIENT_ID"] = "test-client"
os.environ["OIDC_CLIENT_SECRET"] = "test-secret"
os.environ["OIDC_REDIRECT_URI"] = "http://app.test/api/auth/oidc/callback"
os.environ["OIDC_FRONTEND_URL"] = "/done"

import main  # noqa: E402

with TestClient(main.app) as c:
    # 1) login：应 302 重定向到 mock IdP /auth
    r = c.get("/api/auth/oidc/login", follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    assert "/auth" in r.headers["location"], r.headers["location"]
    # state 应在 location 里
    loc = r.headers["location"]
    state = parse_qs(urlparse(loc).query)["state"][0]

    # 2) 模拟 IdP 已把 code+state 回调到应用（直接打 callback，绕过 IdP 302）
    r = c.get(f"/api/auth/oidc/callback?code=mockcode&state={state}", follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    loc2 = r.headers["location"]
    assert loc2.startswith("/done?"), loc2
    q = parse_qs(urlparse(loc2).query)
    token = q["token"][0]; uname = q["username"][0]
    assert uname == "sso_alice", uname
    assert token and "." in token, token

    # 3) 本地 token 可用（/api/auth/me）
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["username"] == "sso_alice", me

    # 4) 再次 SSO 登录同一 sub：复用已创建用户（不新建）
    r2 = c.get("/api/auth/oidc/login", follow_redirects=False); st2 = parse_qs(urlparse(r2.headers["location"]).query)["state"][0]
    r2 = c.get(f"/api/auth/oidc/callback?code=mockcode&state={st2}", follow_redirects=False)
    assert r2.status_code in (302, 307)
    # 用户表应只有 1 个 sso_alice
    import sqlite3
    conn = sqlite3.connect(os.path.join(TMP, "registry.db"))
    n = conn.execute("SELECT COUNT(*) FROM users WHERE username='sso_alice'").fetchone()[0]
    conn.close()
    assert n == 1, f"应复用用户，实际 {n}"

    # 5) state 重放/伪造被拒
    assert c.get("/api/auth/oidc/callback?code=mockcode&state=badstate", follow_redirects=False).status_code == 400
    assert c.get(f"/api/auth/oidc/callback?code=mockcode&state={state}", follow_redirects=False).status_code == 400  # 已消费

    srv.shutdown()
    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
