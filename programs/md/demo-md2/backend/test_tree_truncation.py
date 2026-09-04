# -*- coding: utf-8 -*-
"""目录树节点截断回归（个人 + 团队）。

回归点：GET /api/docs（与 /api/teams/{tid}/docs）默认 limit=100，按
starred DESC, updated_at DESC 排序。当账号节点数超过 limit 时，根/中间
文件夹可能被截断掉；前端 buildCloudTree 因找不到父文件夹的 full，整棵
子树"消失"（用户 bbb 的 知识 子树 88 个节点不展示即此因）。

修复：排序改为文件夹优先 (kind='folder') DESC，确保只要文件夹数 ≤ limit，
所有文件夹都被返回（目录树骨架完整），文件溢出 limit 仅丢文件不丢子树。
前端另请求 limit=500 尽量多拉文件。

本测试强制 limit=20 + 105 个填充文件 + 多个文件夹，断言：
  1) 所有文件夹都在返回结果里（即便 limit 远小于总节点数）；
  2) 用 buildCloudTree 同款逻辑检查：返回结果中不存在 orphan（path 指向
     不存在父文件夹 full 的节点）——即树可完整构建。
"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="tree_trunc_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402


def reg(client, u, p):
    client.post("/api/auth/register", json={"username": u, "password": p})
    return client.post("/api/auth/login", json={"username": u, "password": p}).json()["token"]


def seed_personal(c, headers):
    """知识 根文件夹 + 两级子文件夹 + 子文档；外加 105 个根填充文件。"""
    # 知识 根文件夹 + 子文件夹 + 子文档（模拟 bbb 结构）
    c.post("/api/folders", json={"name": "知识", "path": ""}, headers=headers)
    c.post("/api/folders", json={"name": "高中语文知识", "path": "知识"}, headers=headers)
    c.post("/api/folders", json={"name": "高中数学知识", "path": "知识"}, headers=headers)
    c.post("/api/docs", json={"title": "函数.md", "content": "x", "path": "知识"}, headers=headers)
    c.post("/api/docs", json={"title": "三角函数.md", "content": "x", "path": "知识"}, headers=headers)
    c.post("/api/docs", json={"title": "文言文.md", "content": "x", "path": "知识/高中语文知识"}, headers=headers)
    # 另一个根文件夹 资料（同样应不被截断）
    c.post("/api/folders", json={"name": "资料", "path": ""}, headers=headers)
    c.post("/api/docs", json={"title": "token.md", "content": "x", "path": "资料"}, headers=headers)
    # 105 个根填充文件，确保总节点数 > 100（旧默认）与 > 20（测试用 limit）
    for i in range(105):
        c.post("/api/docs", json={"title": f"fill_{i:03d}.md", "content": "x", "path": ""}, headers=headers)


def check_no_orphans(items):
    """复刻 buildCloudTree：folder.full = path?path+'/'+title:title；
    任一节点 path 必须为 '' 或等于某文件夹的 full，否则为 orphan。"""
    folder_fulls = set()
    for it in items:
        if it.get("kind") == "folder":
            p = it.get("path") or ""
            t = it.get("title") or ""
            folder_fulls.add(f"{p}/{t}" if p else t)
    orphans = []
    for it in items:
        p = it.get("path") or ""
        if p and p not in folder_fulls:
            orphans.append((it.get("kind"), it.get("path"), it.get("title")))
    return folder_fulls, orphans


def titles_of_kind(items, kind):
    return {it["title"] for it in items if it.get("kind") == kind}


with TestClient(main.app) as c:
    ta = reg(c, "alice", "p@ssw0rd")
    ha = {"Authorization": f"Bearer {ta}"}
    seed_personal(c, ha)

    fails = 0

    # 1) 默认 limit：知识/资料 根文件夹必须在；无 orphan
    items = c.get("/api/docs", headers=ha).json()["items"]
    folders = titles_of_kind(items, "folder")
    for must in ["知识", "高中语文知识", "高中数学知识", "资料"]:
        if must in folders:
            print(f"  ok - default limit returns folder {must!r}")
        else:
            print(f"  FAIL - default limit missing folder {must!r}"); fails += 1
    _, orphans = check_no_orphans(items)
    if not orphans:
        print("  ok - default limit: no orphan nodes")
    else:
        print(f"  FAIL - default limit orphans: {orphans[:3]}"); fails += 1

    # 2) 强制 limit=20（远小于总节点数）：文件夹仍须全部返回、无 orphan
    items20 = c.get("/api/docs?limit=20", headers=ha).json()["items"]
    folders20 = titles_of_kind(items20, "folder")
    expected_folders = {"知识", "高中语文知识", "高中数学知识", "资料"}
    if expected_folders.issubset(folders20):
        print(f"  ok - limit=20 returns all {len(expected_folders)} folders (folder-first)")
    else:
        print(f"  FAIL - limit=20 missing folders: {expected_folders - folders20}"); fails += 1
    if len(items20) <= 20:
        print(f"  ok - limit=20 caps total rows ({len(items20)} <= 20)")
    else:
        print(f"  FAIL - limit=20 returned {len(items20)} > 20"); fails += 1
    _, orphans20 = check_no_orphans(items20)
    if not orphans20:
        print("  ok - limit=20: no orphan nodes (tree skeleton complete)")
    else:
        print(f"  FAIL - limit=20 orphans: {orphans20[:3]}"); fails += 1
    # 文件夹应排在结果最前
    first_kinds = [it.get("kind") for it in items20[:len(expected_folders)]]
    if all(k == "folder" for k in first_kinds):
        print("  ok - folders ordered before files")
    else:
        print(f"  FAIL - folders not first: {first_kinds}"); fails += 1

    # 3) 团队空间同样回归
    team = c.post("/api/teams", json={"name": "T1"}, headers=ha).json()["team_id"]
    th = ha
    c.post(f"/api/teams/{team}/folders", json={"name": "知识", "path": ""}, headers=th)
    c.post(f"/api/teams/{team}/folders", json={"name": "高中语文知识", "path": "知识"}, headers=th)
    c.post(f"/api/teams/{team}/docs", json={"title": "文言文.md", "content": "x", "path": "知识/高中语文知识"}, headers=th)
    c.post(f"/api/teams/{team}/folders", json={"name": "资料", "path": ""}, headers=th)
    for i in range(105):
        c.post(f"/api/teams/{team}/docs", json={"title": f"tfill_{i:03d}.md", "content": "x", "path": ""}, headers=th)
    titems = c.get(f"/api/teams/{team}/docs?limit=20", headers=th).json()["items"]
    tfolders = titles_of_kind(titems, "folder")
    if {"知识", "高中语文知识", "资料"}.issubset(tfolders):
        print("  ok - team limit=20 returns all folders")
    else:
        print(f"  FAIL - team limit=20 missing: {{知识,高中语文知识,资料}} - {tfolders}"); fails += 1
    _, torphans = check_no_orphans(titems)
    if not torphans:
        print("  ok - team limit=20: no orphan nodes")
    else:
        print(f"  FAIL - team limit=20 orphans: {torphans[:3]}"); fails += 1

    if fails:
        print(f"\n{fails} FAILED")
        raise SystemExit(1)
    print("\nALL PASSED")
