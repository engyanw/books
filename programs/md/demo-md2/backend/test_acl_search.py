# -*- coding: utf-8 -*-
"""P1-5 跨组织 ACL 感知搜索：被授予 doc_acl 的文档应出现在被授权方的全局搜索结果中，
撤销授权后即不再出现。同时验证个人库搜索不跨用户泄露（PG 共享库 user_id 收敛）。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="aclsearch_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

NEEDLE = "ACLGrantedNeedleXYZ"


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "alice", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "bob", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "alice", "password": "p@ssw0rd"}).json()["token"]
    tb = c.post("/api/auth/login", json={"username": "bob", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    hb = {"Authorization": f"Bearer {tb}"}

    # alice 创建含独特 needle 的文档
    did = c.post("/api/docs", headers=ha, json={"title": "GrantedDoc", "content": f"see {NEEDLE} here"}).json()["doc_id"]

    # 授权前：bob 搜不到
    r0 = c.get(f"/api/search?q={NEEDLE}", headers=hb).json()
    assert not any(i["doc_id"] == did for i in r0["items"]), r0

    # alice 授予 bob read
    g = c.put(f"/api/docs/{did}/acl?target_username=bob&permission=read", headers=ha).json()
    assert g["ok"], g

    # 授权后：bob 应搜到（scope=granted）
    r1 = c.get(f"/api/search?q={NEEDLE}", headers=hb).json()
    hit = next((i for i in r1["items"] if i["doc_id"] == did), None)
    assert hit is not None, r1
    assert hit["scope"] == "granted", hit

    # 个人库搜索不泄露：bob 的个人库结果不应包含 alice 的文档
    assert not any(i.get("scope") == "personal" and i["doc_id"] == did for i in r1["items"]), r1

    # 撤销授权
    c.delete(f"/api/docs/{did}/acl/{g['user_id']}", headers=ha)
    r2 = c.get(f"/api/search?q={NEEDLE}", headers=hb).json()
    assert not any(i["doc_id"] == did for i in r2["items"]), r2

print("ALL PASSED")
