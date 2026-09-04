# -*- coding: utf-8 -*-
"""GDPR：数据导出（zip）+ 账户删除（被遗忘权）。"""
import os, tempfile, io, zipfile, json
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="gdpr_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "gdpruser", "password": "pw123456"})
    tok = c.post("/api/auth/login", json={"username": "gdpruser", "password": "pw123456"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 写若干文档
    for i in range(3):
        c.post("/api/docs", json={"title": f"g{i}", "content": f"# doc {i}\n机密内容{i}"}, headers=h)
    # 写配置
    c.put("/api/settings", json={"theme": "dark"}, headers=h)

    # 1) 导出 zip
    r = c.get("/api/account/export", headers=h)
    assert r.status_code == 200, r.text
    assert "application/zip" in r.headers.get("content-type", "")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "manifest.json" in names
    assert "settings.json" in names
    assert any(n.startswith("docs/") and n.endswith(".md") for n in names), names
    man = json.loads(z.read("manifest.json"))
    assert man["doc_count"] >= 3
    assert "机密内容" in z.read([n for n in names if n.startswith("docs/")][0]).decode("utf-8")

    # 2) 注销：缺确认串 → 400
    assert c.request("DELETE", "/api/account", json={"password": "pw123456", "confirm": "no"}, headers=h).status_code == 400
    # 错密码 → 401
    assert c.request("DELETE", "/api/account", json={"password": "wrong", "confirm": "DELETE"}, headers=h).status_code == 401

    # 3) 正确注销
    r2 = c.request("DELETE", "/api/account", json={"password": "pw123456", "confirm": "DELETE"}, headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["deleted"] is True

    # 4) 注销后：token 失效，用户已不存在
    assert c.get("/api/auth/me", headers=h).status_code == 401
    # 重新登录应失败
    assert c.post("/api/auth/login", json={"username": "gdpruser", "password": "pw123456"}).status_code == 401
    # 用户库目录已删
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    n = conn.execute("SELECT COUNT(*) FROM users WHERE username='gdpruser'").fetchone()[0]
    conn.close()
    assert n == 0, "用户行应已删除"

    # ===== B4: 匿名化模式 =====
    import sqlite3
    c.post("/api/auth/register", json={"username": "anonuser", "password": "pw123456"})
    tok2 = c.post("/api/auth/login", json={"username": "anonuser", "password": "pw123456"}).json()["token"]
    h2 = {"Authorization": f"Bearer {tok2}"}
    c.post("/api/docs", json={"title": "keepme", "content": "保留内容"}, headers=h2)
    # 设 display_name（模拟有 PII）
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET display_name='Real Name', email='anon@example.com' WHERE username='anonuser'")
    conn.commit(); conn.close()

    # 匿名化
    r3 = c.request("DELETE", "/api/account?mode=anonymize", json={"password": "pw123456", "confirm": "DELETE"}, headers=h2)
    assert r3.status_code == 200, r3.text
    assert r3.json()["anonymized"] is True, r3.text

    # token 失效（已吊销）
    assert c.get("/api/auth/me", headers=h2).status_code == 401
    # 用户行仍在，但 PII 已清
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    row = conn.execute("SELECT username, password_hash, email, display_name, active FROM users WHERE username LIKE 'anon_%'").fetchone()
    conn.close()
    assert row, "匿名化后用户行应保留"
    assert row[0].startswith("anon_"), row
    assert row[1] == "", "password_hash 应清空"
    assert row[2] is None, "email 应为 NULL"
    assert row[3] is None, "display_name 应为 NULL"
    assert row[4] == 0, "active 应为 0（停用）"
    # 旧用户名登录失败
    assert c.post("/api/auth/login", json={"username": "anonuser", "password": "pw123456"}).status_code == 401
    # 文档仍在（用户库未删）
    import os as _os
    users_dir = _os.path.join(TMP, "users")
    assert _os.path.exists(users_dir), "用户库目录应保留（匿名化不删文档）"

print("ALL PASSED")
