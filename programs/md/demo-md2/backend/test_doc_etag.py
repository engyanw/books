# -*- coding: utf-8 -*-
"""②文档级乐观锁 ETag/If-Match。
- GET /api/docs/{id} 返回 etag。
- PUT 携带正确 If-Match → 200；新 etag 与旧不同。
- PUT 携带过时 If-Match（他人已改） → 409。
- 无 If-Match 仍可写（向后兼容）。
- 团队文档同样支持 etag + If-Match。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="etag_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    did = c.post("/api/docs", headers=h, json={"title": "D", "content": "v1"}).json()["doc_id"]
    g1 = c.get(f"/api/docs/{did}", headers=h).json()
    etag1 = g1["etag"]
    assert etag1, g1

    # 正确 If-Match → 200，新 etag 变化
    r = c.put(f"/api/docs/{did}", headers={**h, "If-Match": etag1}, json={"title": "D", "content": "v2"})
    assert r.status_code == 200, r.text
    etag2 = r.json()["etag"]
    assert etag2 and etag2 != etag1, (etag1, etag2)

    # 过时 If-Match（用旧 etag1） → 409
    r2 = c.put(f"/api/docs/{did}", headers={**h, "If-Match": etag1}, json={"title": "D", "content": "clobber"})
    assert r2.status_code == 409, r2.text

    # GET 仍是 v2（未被覆盖）
    g2 = c.get(f"/api/docs/{did}", headers=h).json()
    assert "v2" in g2["content"] and "clobber" not in g2["content"], g2["content"]

    # 无 If-Match → 200（向后兼容）
    assert c.put(f"/api/docs/{did}", headers=h, json={"title": "D", "content": "v3"}).status_code == 200

    # 团队文档 etag
    c.post("/api/auth/register", json={"username": "o", "password": "p@ssw0rd"})
    to = c.post("/api/auth/login", json={"username": "o", "password": "p@ssw0rd"}).json()["token"]
    ho = {"Authorization": f"Bearer {to}"}
    tid = c.post("/api/teams", headers=ho, json={"name": "T"}).json()["team_id"]
    tdid = c.post(f"/api/teams/{tid}/docs", headers=ho, json={"title": "TD", "content": "t1"}).json()["doc_id"]
    te1 = c.get(f"/api/teams/{tid}/docs/{tdid}", headers=ho).json()["etag"]
    assert te1
    assert c.put(f"/api/teams/{tid}/docs/{tdid}", headers={**ho, "If-Match": te1}, json={"content": "t2"}).status_code == 200
    assert c.put(f"/api/teams/{tid}/docs/{tdid}", headers={**ho, "If-Match": te1}, json={"content": "clobber"}).status_code == 409

print("ALL PASSED")
