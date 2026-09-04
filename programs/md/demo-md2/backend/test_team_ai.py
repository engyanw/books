# -*- coding: utf-8 -*-
"""T3：团队 AI 配置治理 + 团队聊天 + 用量配额 + 模型白名单。mock 上游。"""
import os, shutil, tempfile, threading, json
from http.server import BaseHTTPRequestHandler, HTTPServer
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="tai_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

class MockUpstream(BaseHTTPRequestHandler):
    def do_POST(self):
        l = int(self.headers.get("content-length", "0")); self.rfile.read(l)
        auth = self.headers.get("Authorization", "")
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": "auth=" + auth}}]}).encode() + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
    def log_message(self, *a): pass

srv = HTTPServer(("127.0.0.1", 0), MockUpstream); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "ta", "password": "p@ssw0rd"})
    tok = c.post("/api/auth/login", json={"username": "ta", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 建团队
    tid = c.post("/api/teams", json={"name": "Eng"}, headers=h).json()["team_id"]

    # 1) 建团队 AI 配置（key 加密落库）
    r = c.post(f"/api/teams/{tid}/ai/configs", json={"name": "team-openai", "api_url": BASE, "api_key": "sk-team-secret", "model": "gpt-4o-mini"}, headers=h)
    assert r.status_code == 201, r.text
    cfgid = r.json()["id"]

    # 2) 列表：无明文 key，有 key_hint
    items = c.get(f"/api/teams/{tid}/ai/configs", headers=h).json()["items"]
    assert len(items) == 1 and items[0]["has_key"] and items[0]["key_hint"].endswith("cret")
    assert "api_key" not in str(items)

    # 3) 团队聊天：转发 Bearer sk-team-secret
    r = c.post(f"/api/teams/{tid}/ai/chat", json={"config_id": cfgid, "messages": [{"role": "user", "content": "hi"}]}, headers=h)
    assert r.status_code == 200 and r.json()["ok"] and r.json()["content"] == "auth=Bearer sk-team-secret", r.text

    # 4) 用量：团队用量=1；个人用量=0
    tu = c.get(f"/api/teams/{tid}/ai/usage", headers=h).json()
    assert tu["today_self"] == 1, tu
    pu = c.get("/api/ai/usage", headers=h).json()
    assert pu["today_personal"] == 0, pu  # 团队调用不计入个人配额

    # 5) 审计含 ai.chat
    aud = [a["action"] for a in c.get(f"/api/audit?team_id={tid}&limit=50", headers=h).json()["items"]]
    assert "ai.chat" in aud and "ai.config.create" in aud, aud

    # 6) 模型白名单：限制后该模型被拒
    main.AI_ALLOWED_MODELS = ["other-model"]
    r = c.post(f"/api/teams/{tid}/ai/chat", json={"config_id": cfgid, "messages": [{"role": "user", "content": "hi"}]}, headers=h)
    assert r.status_code == 400 and "不在允许列表" in r.json()["detail"], r.text
    main.AI_ALLOWED_MODELS = []  # 还原

    # 7) 配额：设团队每日=1（已用 1），再调应 429
    main.AI_TEAM_DAILY_QUOTA = 1
    r = c.post(f"/api/teams/{tid}/ai/chat", json={"config_id": cfgid, "messages": [{"role": "user", "content": "hi"}]}, headers=h)
    assert r.status_code == 429 and "配额" in r.json()["detail"], r.text
    main.AI_TEAM_DAILY_QUOTA = 0  # 还原

    # 8) 非成员不能调用团队 AI
    c.post("/api/auth/register", json={"username": "tb", "password": "p@ssw0rd"})
    t2 = c.post("/api/auth/login", json={"username": "tb", "password": "p@ssw0rd"}).json()["token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert c.post(f"/api/teams/{tid}/ai/chat", json={"config_id": cfgid, "messages": [{"role": "user", "content": "hi"}]}, headers=h2).status_code == 403

    srv.shutdown()
    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
