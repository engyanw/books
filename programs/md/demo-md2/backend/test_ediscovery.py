# -*- coding: utf-8 -*-
"""⑭eDiscovery 合规导出。
- 管理员按 user/team/global 范围导出 zip：manifest + documents.json + versions.json + audit.json + 各 .md。
- 含软删文档（include_deleted=true 默认）。
- 非管理员 403；范围缺失 400。
"""
import os, tempfile, io, zipfile, json

TMP = tempfile.mkdtemp(prefix="edis_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "u1", "password": "p@ssw0rd"})
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'"); conn.commit(); conn.close()
    ta = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    t1 = c.post("/api/auth/login", json={"username": "u1", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    h1 = {"Authorization": f"Bearer {t1}"}
    u1_id = c.get("/api/auth/me", headers=h1).json()["user_id"]

    # u1 建文档（含软删一篇）
    d1 = c.post("/api/docs", headers=h1, json={"title": "保留", "content": "正文A"}).json()["doc_id"]
    d2 = c.post("/api/docs", headers=h1, json={"title": "将删", "content": "正文B"}).json()["doc_id"]
    c.put(f"/api/docs/{d1}", headers=h1, json={"content": "正文A改"})  # 产生版本
    c.delete(f"/api/docs/{d2}", headers=h1)  # 软删

    # 非管理员 403
    assert c.post("/api/admin/ediscovery/export", headers=h1, json={"scope": "user", "scope_id": u1_id}).status_code == 403
    # 范围缺失 400
    assert c.post("/api/admin/ediscovery/export", headers=ha, json={"scope": "user", "scope_id": ""}).status_code == 400

    # 用户范围导出
    r = c.post("/api/admin/ediscovery/export", headers=ha, json={"scope": "user", "scope_id": u1_id})
    assert r.status_code == 200, r.text
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "manifest.json" in names and "documents.json" in names and "versions.json" in names and "audit.json" in names, names
    man = json.loads(zf.read("manifest.json"))
    assert man["scope"] == "user" and man["scope_id"] == u1_id, man
    docs = json.loads(zf.read("documents.json"))
    doc_ids = {d["doc_id"] for d in docs}
    assert d1 in doc_ids and d2 in doc_ids, "含软删文档"  # include_deleted 默认 True
    assert any(d.get("deleted_at") for d in docs if d["doc_id"] == d2), "软删文档应带 deleted_at"
    assert any(d.get("content_plain") == "正文A改" for d in docs if d["doc_id"] == d1), "明文已解密"
    versions = json.loads(zf.read("versions.json"))
    assert len(versions) >= 1, "版本快照"
    audit = json.loads(zf.read("audit.json"))
    assert len(audit) >= 1, "审计日志"
    # .md 文件存在
    assert any(n.startswith("docs/") and n.endswith(".md") for n in names), names

    # include_deleted=false → 不含软删
    r2 = c.post("/api/admin/ediscovery/export", headers=ha,
                json={"scope": "user", "scope_id": u1_id, "include_deleted": False})
    docs2 = json.loads(zipfile.ZipFile(io.BytesIO(r2.content)).read("documents.json"))
    assert d2 not in {d["doc_id"] for d in docs2}, "不含软删"

    # global 范围（仅审计）
    rg = c.post("/api/admin/ediscovery/export", headers=ha, json={"scope": "global"})
    zg = zipfile.ZipFile(io.BytesIO(rg.content))
    assert "audit.json" in zg.namelist(), zg.namelist()

print("ALL PASSED")
