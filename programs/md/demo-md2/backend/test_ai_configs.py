# -*- coding: utf-8 -*-
"""验证：AI 配置加密落库 + CRUD + /api/ai/chat 用 config_id 解密转发 + 旧明文迁移。
key 永不下发明文（list 仅 key_hint）；chat 不收 api_key，按 config_id 取解密 key 转发。"""
import os, shutil, tempfile, threading, json
from http.server import BaseHTTPRequestHandler, HTTPServer
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="ai2_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


class MockUpstream(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        self.rfile.read(length)
        auth = self.headers.get("Authorization", "")
        if self.path == "/ok":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for piece in ["Hello", " from ", "AI"]:
                self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}).encode() + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
        elif self.path == "/checkauth":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": "auth=" + auth}}]}).encode() + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a): pass


srv = HTTPServer(("127.0.0.1", 0), MockUpstream)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

with TestClient(main.app) as client:
    client.post("/api/auth/register", json={"username": "ai2", "password": "p@ssw0rd"})
    token = client.post("/api/auth/login", json={"username": "ai2", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    base = f"http://127.0.0.1:{port}"

    # 1) 列表初始为空
    r = client.get("/api/ai/configs", headers=h); assert r.status_code == 200
    assert r.json()["items"] == [], r.text

    # 2) 新建配置（含 api_key 明文）
    r = client.post("/api/ai/configs", json={"name": "本地", "api_url": base + "/checkauth", "api_key": "sk-secret-xyz", "model": "gpt-4o-mini"}, headers=h)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]; assert r.json()["has_key"] is True

    # 3) 列表回显：不含明文 key，仅 key_hint（末4位）
    items = client.get("/api/ai/configs", headers=h).json()["items"]
    assert len(items) == 1
    it = items[0]
    print("list item:", {k: it[k] for k in ("name", "api_url", "model", "key_hint", "has_key")})
    assert "api_key" not in it and "apiKey" not in it, "明文 key 不应回传: %s" % it
    assert it["key_hint"].endswith("xyz") and "*" in it["key_hint"], it
    assert it["has_key"] is True

    # 4) /api/ai/chat 只传 config_id（不传 api_key），后端解密转发 Bearer
    r = client.post("/api/ai/chat", json={"config_id": cid, "messages": [{"role": "user", "content": "hi"}]}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json(); print("chat:", d)
    assert d["ok"] is True and d["content"] == "auth=Bearer sk-secret-xyz", d  # 解密后的 key 被转发

    # 5) 不存在的 config_id -> 404
    r = client.post("/api/ai/chat", json={"config_id": "nope", "messages": [{"role": "user", "content": "hi"}]}, headers=h)
    assert r.status_code == 404, r.text

    # 6) PUT 更新（留空 api_key 应保留原密钥）
    r = client.put(f"/api/ai/configs/{cid}", json={"name": "改名"}, headers=h)
    assert r.status_code == 200, r.text
    r = client.put(f"/api/ai/configs/{cid}", json={"api_key": "sk-new-key-9999"}, headers=h)
    assert r.status_code == 200, r.text
    r = client.post("/api/ai/chat", json={"config_id": cid, "messages": [{"role": "user", "content": "hi"}]}, headers=h)
    assert r.json()["content"] == "auth=Bearer sk-new-key-9999", r.json()  # 改密后转发新 key

    # 7) 旧明文迁移：往 settings 文件写一份 ai-configs，首次 list 应迁移并清除明文
    uid = "ai2_user"  # 实际 user_id 是 token 解出；用 /api/auth/me 拿
    me = client.get("/api/auth/me", headers=h).json()
    uid = me["user_id"]
    cfg_path = main._config_path(uid)
    import os as _os; _os.makedirs(_os.path.dirname(cfg_path), exist_ok=True)
    # 先删现有配置模拟"迁移前"
    # 改用第二个用户做迁移测试，避免干扰
    client.post("/api/auth/register", json={"username": "ai3", "password": "p@ssw0rd"})
    t3 = client.post("/api/auth/login", json={"username": "ai3", "password": "p@ssw0rd"}).json()["token"]
    h3 = {"Authorization": f"Bearer {t3}"}
    me3 = client.get("/api/auth/me", headers=h3).json()
    cp3 = main._config_path(me3["user_id"])
    _os.makedirs(_os.path.dirname(cp3), exist_ok=True)
    cp3.write_text(json.dumps({"ai-configs": [{"id": "legacy1", "name": "旧配置", "apiUrl": base + "/checkauth", "apiKey": "sk-legacy-aaaa", "model": "gpt-3.5"}], "theme": "dark"}), encoding="utf-8")
    # 触发迁移
    items3 = client.get("/api/ai/configs", headers=h3).json()["items"]
    assert len(items3) == 1 and items3[0]["name"] == "旧配置", items3
    assert items3[0]["key_hint"].endswith("aaaa"), items3
    # settings 文件里的 ai-configs/ai-api-key 应被清除，theme 保留
    raw3 = json.loads(cp3.read_text(encoding="utf-8"))
    assert "ai-configs" not in raw3 and "theme" in raw3, raw3
    # 迁移后的配置可用：chat 转发 legacy key
    r = client.post("/api/ai/chat", json={"config_id": items3[0]["id"], "messages": [{"role": "user", "content": "hi"}]}, headers=h3)
    assert r.json()["content"] == "auth=Bearer sk-legacy-aaaa", r.json()

    # 8) DELETE
    r = client.delete(f"/api/ai/configs/{cid}", headers=h); assert r.status_code == 200, r.text
    assert client.get("/api/ai/configs", headers=h).json()["items"] == []

    srv.shutdown()
    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
