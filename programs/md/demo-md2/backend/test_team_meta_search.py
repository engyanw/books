# -*- coding: utf-8 -*-
"""团队文档元数据(/meta) + 团队搜索(/search)回归。

回归点：前端在团队空间收藏/打标/仅看收藏仍走个人 /api/docs/.../meta 与
/api/docs/search → 团队文档不在个人库 → 404 或返回个人结果（串台）。补团队版
 /api/teams/{tid}/docs/{doc_id}/meta 与 /api/teams/{tid}/docs/search，并验证：
  - 团队收藏 on/off、tags、classification 落团队库且可经列表/search 读回；
  - doc.edit 权限（viewer 403）、404；
  - 团队 search 支持 starred/q 过滤、不泄漏个人库文档；
  - viewer 调团队 search 返回 200（仅 published，无发布则空）。
"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="team_meta_search_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

def reg(client, u, p):
    client.post("/api/auth/register", json={"username": u, "password": p})
    return client.post("/api/auth/login", json={"username": u, "password": p}).json()["token"]

fails = 0
def check(name, cond, got):
    global fails
    if cond: print("  ok -", name)
    else: print("  FAIL -", name, "=>", got); fails += 1

with TestClient(main.app) as c:
    ta = reg(c, "alice", "p@ssw0rd")
    tb = reg(c, "bob", "p@ssw0rd")
    tc = reg(c, "carol", "p@ssw0rd")
    ha, hb, hc = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}, {"Authorization": f"Bearer {tc}"}

    tid = c.post("/api/teams", json={"name": "Platform"}, headers=ha).json()["team_id"]
    c.post(f"/api/teams/{tid}/members", json={"username": "bob", "role": "member"}, headers=ha)
    c.post(f"/api/teams/{tid}/members", json={"username": "carol", "role": "viewer"}, headers=ha)

    # bob 建团队文档（draft）
    did = c.post(f"/api/teams/{tid}/docs", json={"title": "spec.md", "content": "v1 spec", "path": ""}, headers=hb).json()["doc_id"]
    did2 = c.post(f"/api/teams/{tid}/docs", json={"title": "design.md", "content": "design notes", "path": ""}, headers=hb).json()["doc_id"]

    # ---- /meta：收藏 on/off ----
    r = c.put(f"/api/teams/{tid}/docs/{did}/meta", json={"starred": True}, headers=hb)
    check("member star team doc -> 200", r.status_code == 200, r.status_code)
    check("member star -> updated true", r.json().get("updated") is True, r.text)
    # 读回：列表含 starred
    items = c.get(f"/api/teams/{tid}/docs", headers=hb).json()["items"]
    star_map = {it["doc_id"]: it["starred"] for it in items}
    check("list reflects starred=true", star_map.get(did) is True, star_map)

    r = c.put(f"/api/teams/{tid}/docs/{did}/meta", json={"starred": False}, headers=hb)
    check("member unstar -> 200", r.status_code == 200, r.status_code)
    items = c.get(f"/api/teams/{tid}/docs", headers=hb).json()["items"]
    star_map = {it["doc_id"]: it["starred"] for it in items}
    check("list reflects starred=false", star_map.get(did) is False, star_map)

    # ---- /meta：tags ----
    c.put(f"/api/teams/{tid}/docs/{did}/meta", json={"tags": "a,b"}, headers=hb)
    items = c.get(f"/api/teams/{tid}/docs", headers=hb).json()["items"]
    tag_map = {it["doc_id"]: it.get("tags", "") for it in items}
    check("list reflects tags", tag_map.get(did) == "a,b", tag_map.get(did))

    # ---- /meta：classification ----
    r = c.put(f"/api/teams/{tid}/docs/{did}/meta", json={"classification": "confidential"}, headers=hb)
    check("member set classification confidential -> 200", r.status_code == 200, r.status_code)

    # ---- /meta：权限（viewer 403）+ 404 ----
    r = c.put(f"/api/teams/{tid}/docs/{did}/meta", json={"starred": True}, headers=hc)
    check("viewer meta -> 403", r.status_code == 403, r.status_code)
    r = c.put(f"/api/teams/{tid}/docs/nope_xxx/meta", json={"starred": True}, headers=hb)
    check("meta nonexistent -> 404", r.status_code == 404, r.status_code)

    # ---- /search：starred 过滤 ----
    c.put(f"/api/teams/{tid}/docs/{did}/meta", json={"starred": True}, headers=hb)  # star did
    res = c.get(f"/api/teams/{tid}/docs/search?starred=1", headers=hb).json()["items"]
    ids = {it["doc_id"] for it in res}
    check("search starred=1 includes starred doc", did in ids, ids)
    check("search starred=1 excludes unstarred doc", did2 not in ids, ids)

    # ---- /search：q 过滤 ----
    res = c.get(f"/api/teams/{tid}/docs/search?q=spec", headers=hb).json()["items"]
    ids = {it["doc_id"] for it in res}
    check("search q=spec includes spec.md", did in ids, ids)
    check("search q=spec excludes design.md", did2 not in ids, ids)

    # ---- /search：不泄漏个人库 ----
    # alice 建个人文档 spec.md 并收藏
    pdid = c.post("/api/docs", json={"title": "spec.md", "content": "personal"}, headers=ha).json()["doc_id"]
    c.put(f"/api/docs/{pdid}/meta", json={"starred": True}, headers=ha)
    res = c.get(f"/api/teams/{tid}/docs/search?starred=1", headers=hb).json()["items"]
    ids = {it["doc_id"] for it in res}
    check("team search does not leak personal doc", pdid not in ids, ids)
    check("team search still has team starred doc", did in ids, ids)

    # ---- /search：viewer 200（仅 published，无发布→空）----
    r = c.get(f"/api/teams/{tid}/docs/search", headers=hc)
    check("viewer team search -> 200", r.status_code == 200, r.status_code)
    check("viewer sees no draft docs (none published)", r.json()["items"] == [], r.json()["items"])

    # ---- 取消收藏后 starred 过滤即时移除 ----
    c.put(f"/api/teams/{tid}/docs/{did}/meta", json={"starred": False}, headers=hb)
    res = c.get(f"/api/teams/{tid}/docs/search?starred=1", headers=hb).json()["items"]
    ids = {it["doc_id"] for it in res}
    check("after unstar, search starred=1 removes it", did not in ids, ids)

if fails:
    print(f"\n{fails} FAILED"); raise SystemExit(1)
print("\nALL PASSED")
