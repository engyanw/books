# -*- coding: utf-8 -*-
"""P1-5 at-rest 主密钥轮换回归。
覆盖：
- 创建文档 → documents/doc_versions 落 atrestv1 密文
- 旋转主密钥 → 全表重加密（reencrypted_rows≥2）+ kid 变更
- 旋转后文档正文仍可正确解密（GET 返回原文）
- 新密文用旧密钥解不开（证明确已重加密）
- 非管理员 403；new_key 过短 400；未启用加密 409（独立进程）
"""
import os, sqlite3, tempfile, subprocess, sys

TMP = tempfile.mkdtemp(prefix="kms_rot_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# at-rest 加密开启 + 测试主密钥（test-only）
os.environ["DOC_ATREST_ENCRYPTION"] = "1"
os.environ["DOC_ATREST_KEY"] = "test-atrest-key-please-rotate"

from fastapi.testclient import TestClient
import main  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: E402


def _fernet_for(key_material: str) -> Fernet:
    kdf = HKDF(algorithm=hashes.SHA256(), length=32,
               salt=b"md-editor-doc-atrest", info=b"doc-content-aes")
    import base64
    return Fernet(base64.urlsafe_b64encode(kdf.derive(key_material.encode("utf-8"))))


with TestClient(main.app) as c:
    # 管理员
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    _r = sqlite3.connect(os.path.join(TMP, "registry.db"))
    _r.execute("UPDATE users SET is_admin=1 WHERE username=?", ("admin",))
    _r.commit(); _r.close()
    reg = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()
    t = reg["token"]; h = {"Authorization": f"Bearer {t}"}
    uid = reg.get("user_id") or reg.get("id")
    # 普通用户（断言 403）
    ct = c.post("/api/auth/register", json={"username": "u2", "password": "p@ssw0rd"}).json()["token"]
    hn = {"Authorization": f"Bearer {ct}"}

    # 状态：当前 kid
    st0 = c.get("/api/admin/kms/atrest-status", headers=h).json()
    assert st0["atrest_enabled"] is True
    assert st0["current_kid"] is not None

    # 新建文档 → documents.content 落 atrestv1 密文；随后 PUT 更新 → doc_versions 落旧正文密文
    body1 = "机密内容 rotate-marker-001"
    body2 = "机密内容 rotate-marker-002 已更新"
    r = c.post("/api/docs", headers=h, json={"title": "t", "content": body1})
    assert r.status_code in (200, 201), r.text
    doc_id = r.json()["doc_id"]
    # PUT 更新正文（触发 doc_versions 快照存入旧正文密文）
    r = c.put(f"/api/docs/{doc_id}", headers=h, json={"content": body2})
    assert r.status_code in (200, 200), r.text

    # 原始密文（直接读用户库）
    udb = os.path.join(TMP, "users", uid, "docs.db")
    _d = sqlite3.connect(udb); _d.row_factory = sqlite3.Row
    old_ct_doc = _d.execute("SELECT content FROM documents WHERE doc_id=?", (doc_id,)).fetchone()["content"]
    assert old_ct_doc.startswith("atrestv1:"), old_ct_doc[:20]
    vrow = _d.execute("SELECT content FROM doc_versions WHERE doc_id=? ORDER BY id", (doc_id,)).fetchone()
    assert vrow is not None, "PUT 未生成版本快照"
    old_ct_ver = vrow["content"]
    assert old_ct_ver.startswith("atrestv1:"), old_ct_ver[:20]
    _d.close()

    # 非管理员 → 403
    assert c.post("/api/admin/kms/rotate-master", headers=hn,
                  json={"new_key": "rotated-master-key-aaaa-bbbb"}).status_code == 403
    # new_key 过短 → 400
    assert c.post("/api/admin/kms/rotate-master", headers=h,
                  json={"new_key": "short"}).status_code == 400
    # 缺 new_key → 400
    assert c.post("/api/admin/kms/rotate-master", headers=h, json={}).status_code == 400

    # 旋转
    NEW_KEY = "rotated-master-key-aaaa-bbbb-cccc"
    r = c.post("/api/admin/kms/rotate-master", headers=h, json={"new_key": NEW_KEY})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["rotated"] is True
    assert res["reencrypted_rows"] >= 2, res  # documents + doc_versions
    assert res["kid_new"] != st0["current_kid"]

    # 状态：kid 已变 + 历史密钥计数 ≥1
    st1 = c.get("/api/admin/kms/atrest-status", headers=h).json()
    assert st1["current_kid"] == res["kid_new"]
    assert st1["history_keys"] >= 1

    # 文档正文仍可解密（新密钥）→ 原文一致（PUT 后为 body2）
    g = c.get(f"/api/docs/{doc_id}", headers=h).json()
    assert g["content"] == body2, g["content"]

    # 新密文已变更（token 不同）但仍 atrestv1
    _d = sqlite3.connect(udb); _d.row_factory = sqlite3.Row
    new_ct_doc = _d.execute("SELECT content FROM documents WHERE doc_id=?", (doc_id,)).fetchone()["content"]
    assert new_ct_doc.startswith("atrestv1:")
    assert new_ct_doc != old_ct_doc
    _d.close()

    # 旧密钥解不开新密文 → 证明已用新密钥重加密
    old_cipher = _fernet_for("test-atrest-key-please-rotate")
    new_body = new_ct_doc[len("atrestv1:"):]
    try:
        old_cipher.decrypt(new_body.encode("ascii"))
        raise AssertionError("旧密钥不应能解开新密文")
    except Exception:
        pass  # 预期：InvalidToken
    # 新密钥能解开
    new_cipher = _fernet_for(NEW_KEY)
    assert new_cipher.decrypt(new_body.encode("ascii")).decode("utf-8") == body2

print("ALL PASSED")

# 独立进程：DOC_ATREST_ENCRYPTION 未启用 → 旋转应 409（无密文可轮换）
import textwrap as _tw  # noqa: E402
_sub = _tw.dedent(
    """
    import os, tempfile
    os.environ["DOC_DATA_DIR"] = tempfile.mkdtemp(prefix="kms_off_")
    os.environ["REGISTRY_DB_PATH"] = os.path.join(os.environ["DOC_DATA_DIR"], "registry.db")
    os.environ["AUTH_ALLOW_REGISTER"] = "true"
    # DOC_ATREST_ENCRYPTION 默认 0（不设）
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
        import sqlite3 as _s
        _r = _s.connect(os.environ["REGISTRY_DB_PATH"])
        _r.execute("UPDATE users SET is_admin=1 WHERE username=?", ("admin",))
        _r.commit(); _r.close()
        t = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
        h = {"Authorization": f"Bearer {t}"}
        r = c.post("/api/admin/kms/rotate-master", headers=h,
                   json={"new_key": "rotated-master-key-aaaa-bbbb-cccc"})
        assert r.status_code == 409, r.text
    print("OFF PASSED")
    """
)
_env = dict(os.environ)
_env["DOC_ATREST_ENCRYPTION"] = "0"  # 显式关闭，覆盖父进程继承的 1
_env.pop("DOC_ATREST_KEY", None)
out = subprocess.run([sys.executable, "-c", _sub], capture_output=True, text=True,
                     timeout=120, env=_env)
print(out.stdout)
if out.returncode != 0:
    print(out.stderr)
    raise SystemExit("encryption-off 409 case failed")

