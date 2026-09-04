# -*- coding: utf-8 -*-
"""P1：密钥扫描。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="sec_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "secu", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "secu", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 干净文档
    did_clean = c.post("/api/docs", json={"title": "clean.md", "content": "# 安全文档\n\n正常内容，无密钥。"}, headers=h).json()["doc_id"]
    r = c.post(f"/api/docs/{did_clean}/scan-secrets", headers=h)
    assert r.status_code == 200 and r.json()["count"] == 0, r.text

    # 含密钥文档
    did_secret = c.post("/api/docs", json={"title": "leak.md", "content": "API key: sk-abc123def456ghi789jkl012mno345pqr678\nAWS: AKIAIOSFODNN7EXAMPLE\nGitHub: ghp_aBcDeFgHiJkLmNpQrStUvWxYz0123456789\npassword = 'supersecret12345678'"}, headers=h).json()["doc_id"]
    r = c.post(f"/api/docs/{did_secret}/scan-secrets", headers=h)
    assert r.status_code == 200
    findings = r.json()["findings"]
    print("findings:", findings)
    assert r.json()["count"] >= 3, findings  # at least OpenAI + AWS + GitHub
    types = [f["type"] for f in findings]
    assert "OpenAI API Key" in types and "AWS Access Key" in types, types

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
