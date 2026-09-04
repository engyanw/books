# -*- coding: utf-8 -*-
"""P2 集成连接器：配置 Slack/Teams webhook 后，关键事件自动推送。
用本地 HTTP server 捕获 POST，验证：
- 配置 INTEGRATION_SLACK/TEAMS_WEBHOOK_URL → @mention 触发推送（payload.text 含事件与详情）。
- 未配置 → 无推送（_integration_notify 早退，不报错）。
"""
import os, tempfile, threading, json
from http.server import BaseHTTPRequestHandler, HTTPServer

TMP = tempfile.mkdtemp(prefix="integ_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

captured = []  # [(path, json_body)]


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(n)
        try:
            captured.append((self.path, json.loads(body)))
        except Exception:
            captured.append((self.path, {"raw": body.decode("utf-8", "replace")}))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):  # 静默
        pass


srv = HTTPServer(("127.0.0.1", 0), _Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

os.environ["INTEGRATION_SLACK_WEBHOOK_URL"] = f"http://127.0.0.1:{port}/slack"
os.environ["INTEGRATION_TEAMS_WEBHOOK_URL"] = f"http://127.0.0.1:{port}/teams"
os.environ["INTEGRATION_NOTIFY_EVENTS"] = "mention"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "alice", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "bob", "password": "p@ssw0rd"})  # 被 @ 的目标用户
    ta = c.post("/api/auth/login", json={"username": "alice", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    # 提及 bob（_parse_mentions → 查 username → _notify(bob, mention) → _integration_notify）
    did = c.post("/api/docs", headers=ha, json={"title": "t", "content": "hey @bob 看一下"}).json()["doc_id"]
    c.put(f"/api/docs/{did}", headers=ha, json={"title": "t", "content": "ping @bob again"})

# 等待异步 httpx 推送落盘
import time
deadline = time.time() + 5
while time.time() < deadline and not captured:
    time.sleep(0.1)
srv.shutdown()

assert captured, "应至少捕获一次 Slack/Teams 推送"
slack = [b for p, b in captured if p == "/slack"]
teams = [b for p, b in captured if p == "/teams"]
assert slack, f"Slack 应收到推送：{captured}"
assert teams, f"Teams 应收到推送：{captured}"
assert all("text" in b and "mention" in b["text"] for b in slack), slack
assert all("text" in b and "mention" in b["text"] for b in teams), teams
print("ALL PASSED")
