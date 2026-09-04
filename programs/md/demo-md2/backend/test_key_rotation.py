# -*- coding: utf-8 -*-
"""密钥管理与轮换：多版本密钥解密 + admin 重加密接口。"""
import os, tempfile, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="kr_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["AI_ENC_KEY"] = "current-secret-key-v2"

import main  # noqa: E402


def reload_ciphers():
    main._ai_ciphers = []  # 清缓存强制按当前 env 重建


def user_db_path(uid):
    return os.path.join(TMP, "users", uid, "docs.db")


def read_enc_key(uid, cid):
    c = sqlite3.connect(user_db_path(uid))
    row = c.execute("SELECT enc_key FROM ai_configs WHERE id=?", (cid,)).fetchone()
    c.close()
    return row[0] if row else None


# 1) 加密-解密往返 + kid 标注
enc = main._ai_encrypt("sk-my-api-key-12345")
assert ":" in enc and main._ai_decrypt(enc) == "sk-my-api-key-12345"

# 2) 轮换：当前=v2 密文，降 v2 为旧，换 v3
# 注意：AI_ENC_KEY 是 config 导入时常量，需改 main.AI_ENC_KEY 本身（改 env 无效）
old_enc = enc
main.AI_ENC_KEY = "new-secret-key-v3"
os.environ["AI_ENC_KEY_PREVIOUS"] = "current-secret-key-v2"
reload_ciphers()
assert main._ai_decrypt(old_enc) == "sk-my-api-key-12345", "旧密钥应能解旧密文"
new_enc = main._ai_encrypt("sk-my-api-key-12345")
assert new_enc != old_enc
assert main._ai_decrypt(new_enc) == "sk-my-api-key-12345"

with TestClient(main.app) as c:
    # 建管理员
    c.post("/api/auth/register", json={"username": "root", "password": "pw123456"})
    conn0 = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn0.execute("UPDATE users SET is_admin=1 WHERE username='root'")
    conn0.commit()
    root_uid = conn0.execute("SELECT user_id FROM users WHERE username='root'").fetchone()[0]
    conn0.close()
    tok = c.post("/api/auth/login", json={"username": "root", "password": "pw123456"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}

    # 建 AI 配置（用 v3 加密落库）
    cfg = c.post("/api/ai/configs", json={"name": "m", "api_url": "http://x", "model": "gpt", "api_key": "sk-xyz"}, headers=h).json()
    cid = cfg["id"]
    assert read_enc_key(root_uid, cid) is not None

    # 再轮换：当前=v4，旧=v3,v2
    main.AI_ENC_KEY = "newest-v4"
os.environ["AI_ENC_KEY_PREVIOUS"] = "new-secret-key-v3,current-secret-key-v2"
reload_ciphers()
# 旧密文（v3）仍可解密（多版本回退）
assert main._ai_decrypt(read_enc_key(root_uid, cid)) == "sk-xyz", "多版本密钥应能解 v3 密文"

with TestClient(main.app) as c2:
    h2 = {"Authorization": f"Bearer {tok}"}
    # admin 重加密 → 全部用 v4 重写
    res = c2.post("/api/admin/rotate-ai-keys", headers=h2).json()
    assert res["reencrypted"] >= 1, res
    enc_after = read_enc_key(root_uid, cid)
    v4_kid = main._kid_of("newest-v4")
    assert enc_after.startswith(v4_kid + ":"), f"重加密后应为 v4 kid: {enc_after}"
    assert main._ai_decrypt(enc_after) == "sk-xyz", "重加密后应仍可解密"

# 3) 旧密钥下线后：重加密后的 v4 密文仍可解
main.AI_ENC_KEY = "newest-v4"
os.environ["AI_ENC_KEY_PREVIOUS"] = ""  # 下线旧密钥
reload_ciphers()
assert main._ai_decrypt(enc_after) == "sk-xyz"

print("ALL PASSED")
