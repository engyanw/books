# -*- coding: utf-8 -*-
"""P1-6 通知外部渠道：generic/slack/teams 三种 payload 格式 + HMAC 签名 + 团队 webhook 触发。
起一个本地 HTTP 接收器，注册不同渠道 webhook，触发通知后断言收到的 payload 形态。
"""
import os, tempfile, threading, json, hmac, hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer

TMP = tempfile.mkdtemp(prefix="wh_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

received = []  # [(path, headers, body)]


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(n)
        received.append((self.path, dict(self.headers), raw.decode("utf-8", "replace")))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a, **k):
        pass


srv = HTTPServer(("127.0.0.1", 0), _Handler)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

from fastapi.testclient import TestClient
import main  # noqa: E402


def _clear():
    received.clear()


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "wh", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "wh", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    uid = c.get("/api/auth/me", headers=h).json()["user_id"]
    base = f"http://127.0.0.1:{PORT}"

    # generic 渠道 + secret
    c.post("/api/webhooks", headers=h, json={"url": f"{base}/gen", "events": "test.*", "channel_type": "generic", "secret": "s3cr3t"}).json()
    # slack 渠道
    c.post("/api/webhooks", headers=h, json={"url": f"{base}/slack", "events": "mention", "channel_type": "slack"}).json()
    # teams 渠道
    c.post("/api/webhooks", headers=h, json={"url": f"{base}/teams", "events": "share.*", "channel_type": "teams"}).json()

    _clear()
    # 直接触发底层分发（不依赖具体业务事件路径）
    import asyncio
    asyncio.run(main._fire_webhooks(uid, "test.ping", {"detail": "hello", "link": "/x"}, team_id=None))
    # generic 应命中 test.* ；slack/teams events 不匹配
    gen = [r for r in received if r[0] == "/gen"]
    assert len(gen) == 1, received
    gbody = json.loads(gen[0][2])
    assert gbody["event"] == "test.ping" and gbody["detail"] == "hello", gbody
    # HMAC 签名校验
    sig = gen[0][1].get("X-Signature")
    expect = hmac.new(b"s3cr3t", json.dumps(gbody).encode("utf-8"), hashlib.sha256).hexdigest()
    assert sig == expect, (sig, expect)

    _clear()
    asyncio.run(main._fire_webhooks(uid, "mention", {"detail": "你被提及", "link": ""}, team_id=None))
    sl = [r for r in received if r[0] == "/slack"]
    assert len(sl) == 1, received
    sbody = json.loads(sl[0][2])
    assert sbody.get("text") and "你被提及" in sbody["text"], sbody

    _clear()
    asyncio.run(main._fire_webhooks(uid, "share.access", {"detail": "d1", "link": ""}, team_id=None))
    tm = [r for r in received if r[0] == "/teams"]
    assert len(tm) == 1, received
    tbody = json.loads(tm[0][2])
    assert tbody["type"] == "message" and tbody["attachments"], tbody

    # 无 secret 时不带 X-Signature
    assert "X-Signature" not in sl[0][1], sl[0][1]

srv.shutdown()
print("ALL PASSED")
