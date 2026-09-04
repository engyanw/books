# -*- coding: utf-8 -*-
"""P1-8 生命周期门禁 + 电子签名（严格模式 LIFECYCLE_REQUIRE_SIGNATURE=1）。
- 自由 /status 直接转 approved/published 被拒（409）。
- /sign?intent=approve 由 in_review→approved（留签名+内容哈希）。
- /sign?intent=publish 由 approved→published。
- 内容事后被改 → content_matches=False（防篡改可见）。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="sig_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["LIFECYCLE_REQUIRE_SIGNATURE"] = "1"  # 严格模式

from fastapi.testclient import TestClient
import main  # noqa: E402


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "sig", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "sig", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    did = c.post("/api/docs", headers=h, json={"title": "S", "content": "v1 body"}).json()["doc_id"]

    # draft → in_review（自由流转仍允许，非签名门禁态）
    assert c.put(f"/api/docs/{did}/status?status=in_review", headers=h).status_code == 200

    # 严格模式：in_review → approved 必须经签名，自由 /status 被拒
    r = c.put(f"/api/docs/{did}/status?status=approved", headers=h)
    assert r.status_code == 409, r.text

    # 签名 approve → approved
    sa = c.post(f"/api/docs/{did}/sign?intent=approve", headers=h).json()
    assert sa["status"] == "approved" and sa["content_hash"], sa
    # approved → published 自由被拒
    assert c.put(f"/api/docs/{did}/status?status=published", headers=h).status_code == 409
    # 签名 publish → published
    sp = c.post(f"/api/docs/{did}/sign?intent=publish", headers=h).json()
    assert sp["status"] == "published", sp

    # 读取签名：签署时内容哈希应匹配（content_matches=True）
    sigs = c.get(f"/api/docs/{did}/signatures", headers=h).json()["items"]
    assert len(sigs) == 2, sigs
    assert all(s["content_matches"] for s in sigs), sigs

    # 改内容 → 旧签名 content_matches 变 False（防篡改可见）
    c.put(f"/api/docs/{did}", headers=h, json={"content": "tampered v2", "title": "S"})
    sigs2 = c.get(f"/api/docs/{did}/signatures", headers=h).json()["items"]
    assert all(not s["content_matches"] for s in sigs2), sigs2

    # review intent 不流转状态（published 仍可留签）
    sr = c.post(f"/api/docs/{did}/sign?intent=review", headers=h).json()
    assert sr["status"] == "published", sr

print("ALL PASSED")
