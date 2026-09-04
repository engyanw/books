# -*- coding: utf-8 -*-
"""P1-E1：KMS/Vault 密钥提供者。

验证：
- env provider（默认）：resolve_current 返回 AI_ENC_KEY，向后兼容
- http provider：从 mock HTTP 端点取主密钥，带缓存 TTL
- 通过 KMS 取回的密钥可用于 Fernet 加解密（_ai_encrypt/_ai_decrypt 端到端可用）
- /api/admin/kms/status 端点（仅管理员，不泄露明文）
"""
import os, tempfile, shutil, threading, json
from http.server import BaseHTTPRequestHandler, HTTPServer
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="kms_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 用一个固定主密钥，便于断言派生可用
os.environ["AI_ENC_KEY"] = "kms-master-secret-0"

import main  # noqa: E402
import kms  # noqa: E402


def _make_admin(c):
    c.post("/api/auth/register", json={"username": "admin_e1", "password": "pw123456"})
    # 置为管理员
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin_e1'")
    conn.commit(); conn.close()
    return c.post("/api/auth/login", json={"username": "admin_e1", "password": "pw123456"}).json()["token"]


# 1) env provider 向后兼容
kms.clear_cache()
os.environ["KMS_PROVIDER"] = "env"
assert kms.resolve_current() == "kms-master-secret-0", kms.resolve_current()
assert kms.status()["provider"] == "env" and kms.status()["has_current"] is True

# 2) 加解密端到端可用（KMS 提供的密钥经 HKDF 派生 Fernet）
main._ai_ciphers = []  # 强制重建
tok = main._ai_encrypt("sk-test-123")
assert tok and main._ai_decrypt(tok) == "sk-test-123", "KMS 密钥应能加解密"

# 3) http provider：起一个本地 mock HTTP 端点返回密钥
MOCK_KEY = "http-provider-master-9"
_server = {}

class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"secret": {"value": MOCK_KEY}}).encode())
    def log_message(self, *a):
        pass

srv = HTTPServer(("127.0.0.1", 0), _H)
port = srv.server_address[1]
th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()

os.environ["KMS_PROVIDER"] = "http"
os.environ["KMS_URL"] = f"http://127.0.0.1:{port}/secret"
os.environ["KMS_TOKEN"] = "tok"
os.environ["KMS_JSON_KEY"] = "secret.value"
kms.clear_cache()
got = kms.resolve_current()
assert got == MOCK_KEY, f"http provider 应取回 mock 密钥，实际 {got!r}"
srv.shutdown()

# 4) status 端点（管理员可见，非管理员 403，不泄露明文）
with TestClient(main.app) as c:
    admin_tok = _make_admin(c)
    ha = {"Authorization": f"Bearer {admin_tok}"}
    r = c.get("/api/admin/kms/status", headers=ha)
    assert r.status_code == 200, r.text
    st = r.json()
    assert "provider" in st and MOCK_KEY not in json.dumps(st), st  # 不泄露明文
    # 非管理员 403
    c.post("/api/auth/register", json={"username": "plain_e1", "password": "pw123456"})
    pt = c.post("/api/auth/login", json={"username": "plain_e1", "password": "pw123456"}).json()["token"]
    r2 = c.get("/api/admin/kms/status", headers={"Authorization": f"Bearer {pt}"})
    assert r2.status_code == 403, r2.text

shutil.rmtree(TMP, ignore_errors=True)
print("ALL PASSED")
