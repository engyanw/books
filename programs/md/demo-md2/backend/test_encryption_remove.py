# -*- coding: utf-8 -*-
"""验证：取消加密后重新打开不再提示密码（后端 is_encrypted 正确置 0 + 清空 enc 字段）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="enc_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as client:
    client.post("/api/auth/register", json={"username": "enc_user", "password": "p@ssw0rd"})
    token = client.post("/api/auth/login", json={"username": "enc_user", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # 1) 建一篇加密文档（带盐/IV）
    r = client.post("/api/docs", json={
        "title": "secret.md", "content": "ciphertext-blob",
        "is_encrypted": True, "enc_salt": "saltAAA", "enc_iv": "ivBBB", "enc_iters": 150000,
    }, headers=h)
    assert r.status_code == 201, r.text
    doc_id = r.json()["doc_id"]

    # 2) 打开：应判定为加密
    got = client.get(f"/api/docs/{doc_id}", headers=h).json()
    assert got["is_encrypted"] is True, got
    assert got["enc_salt"] == "saltAAA" and got["enc_iv"] == "ivBBB", got

    # 3) 取消加密：is_encrypted=False（前端 cloudSave 在 encryptMode=false 时发送此体）
    ver = got["version"]
    r = client.put(f"/api/docs/{doc_id}", json={
        "title": "secret.md", "content": "now plaintext",
        "is_encrypted": False, "enc_salt": None, "enc_iv": None, "enc_iters": None,
        "version": ver,
    }, headers=h)
    assert r.status_code == 200, r.text

    # 4) 重新打开：is_encrypted 必须为 False，且盐/IV 已清空（不再触发解密提示）
    got2 = client.get(f"/api/docs/{doc_id}", headers=h).json()
    print("reopen:", {k: got2[k] for k in ("is_encrypted", "enc_salt", "enc_iv", "content", "version")})
    assert got2["is_encrypted"] is False, f"取消加密后仍判定为加密: {got2}"
    assert got2["enc_salt"] is None and got2["enc_iv"] is None, f"enc 字段未清空: {got2}"
    assert got2["content"] == "now plaintext", got2

    # 5) 再加密（往返）——确保重新加密仍能正确置位
    r = client.put(f"/api/docs/{doc_id}", json={
        "title": "secret.md", "content": "cipher2",
        "is_encrypted": True, "enc_salt": "saltCCC", "enc_iv": "ivDDD", "enc_iters": 150000,
        "version": got2["version"],
    }, headers=h)
    assert r.status_code == 200, r.text
    got3 = client.get(f"/api/docs/{doc_id}", headers=h).json()
    assert got3["is_encrypted"] is True and got3["enc_salt"] == "saltCCC", got3

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
