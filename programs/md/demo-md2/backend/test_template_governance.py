# -*- coding: utf-8 -*-
"""P2-11 模板治理：组织级受管模板库、版本审批、继承。
覆盖：
1. 受管模板 draft→pending→approved 审批流；未审批禁止实例化(409)。
2. 废弃后禁止实例化(410)。
3. 版本治理：编辑 bump 版本 +1，旧版本入历史，受管模板编辑后回退 draft 需重审。
4. 继承：子模板 parent_id 指向父模板，实例化时父链渲染并拼接。
5. 个人非受管模板保持 active 可直接实例化（不回归）。
6. 普通成员不能审批受管模板（admin 才行）。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="tplgov_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "admin", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "mem", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "admin", "password": "p@ssw0rd"}).json()["token"]
    tm = c.post("/api/auth/login", json={"username": "mem", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    hm = {"Authorization": f"Bearer {tm}"}

    tid_team = c.post("/api/teams", headers=ha, json={"name": "Gov"}).json()["team_id"]
    c.post(f"/api/teams/{tid_team}/members", headers=ha, json={"username": "mem", "role": "member"})

    # --- 1. 基模板（非受管，团队 admin 建，供继承） ---
    base = c.post(f"/api/templates?team_id={tid_team}", headers=ha, json={
        "name": "基模板", "kind": "custom", "variables": ["who"],
        "content": "## 基础章节\n作者: {{ who }}"}).json()
    bid = base["id"]
    assert base["org_managed"] is False and base["status"] == "active", base

    # --- 2. 受管模板（继承基模板），起始 draft ---
    mgr = c.post(f"/api/templates?team_id={tid_team}", headers=ha, json={
        "name": "受管模板", "kind": "custom", "variables": ["who", "extra"],
        "content": "## 扩展章节\n{{ extra }}", "parent_id": bid, "org_managed": True}).json()
    mid = mgr["id"]
    assert mgr["org_managed"] is True and mgr["status"] == "draft", mgr

    # 未审批 → 实例化被拒(409)
    r = c.post(f"/api/templates/{mid}/instantiate", headers=ha, json={"variables": {"who": "bob", "extra": "x"}})
    assert r.status_code == 409, r.text

    # 普通成员不能提交/审批
    assert c.post(f"/api/templates/{mid}/submit", headers=hm).status_code == 403
    # admin 提交
    assert c.post(f"/api/templates/{mid}/submit", headers=ha).json()["status"] == "pending"
    # 重复提交被拒
    assert c.post(f"/api/templates/{mid}/submit", headers=ha).status_code == 409
    # 普通成员不能审批
    assert c.post(f"/api/templates/{mid}/approve", headers=hm).status_code == 403
    # admin 审批通过
    assert c.post(f"/api/templates/{mid}/approve", headers=ha).json()["status"] == "approved"

    # --- 3. 继承实例化：父链拼接 ---
    inst = c.post(f"/api/templates/{mid}/instantiate", headers=ha, json={
        "variables": {"who": "alice", "extra": "深入内容"}, "title": "继承产物"}).json()
    did = inst["doc_id"]
    doc = c.get(f"/api/docs/{did}", headers=ha).json()
    assert "作者: alice" in doc["content"], doc["content"]  # 来自父模板
    assert "深入内容" in doc["content"], doc["content"]   # 来自子模板
    assert "基础章节" in doc["content"] and "扩展章节" in doc["content"], doc["content"]

    # --- 4. 版本治理：编辑 bump + 旧版本历史 + 回退 draft 需重审 ---
    upd = c.put(f"/api/templates/{mid}", headers=ha, json={
        "name": "受管模板v2", "kind": "custom", "variables": ["who", "extra"],
        "content": "## 扩展章节 v2\n{{ extra }}", "parent_id": bid, "org_managed": True}).json()
    assert upd["version"] == 2 and upd["status"] == "draft", upd
    # 回退 draft 后实例化再次被拒
    assert c.post(f"/api/templates/{mid}/instantiate", headers=ha, json={"variables": {"who": "x", "extra": "y"}}).status_code == 409
    # 详情含版本历史
    detail = c.get(f"/api/templates/{mid}", headers=ha).json()
    assert detail["version"] == 2 and detail["status"] == "draft", detail
    assert any(v["version"] == 1 for v in detail["versions"]), detail["versions"]
    assert detail["parent_chain"] and detail["parent_chain"][0]["id"] == bid, detail["parent_chain"]

    # --- 5. 废弃后禁止实例化(410) ---
    c.post(f"/api/templates/{mid}/submit", headers=ha)
    c.post(f"/api/templates/{mid}/approve", headers=ha)
    c.post(f"/api/templates/{mid}/deprecate", headers=ha)
    assert c.post(f"/api/templates/{mid}/instantiate", headers=ha, json={"variables": {"who": "x", "extra": "y"}}).status_code == 410

    # --- 6. 非受管个人模板保持 active，可直接实例化（不回归） ---
    p = c.post("/api/templates", headers=ha, json={"name": "p", "content": "# {{ t }}", "variables": ["t"]}).json()
    assert p["status"] == "active", p
    assert c.post(f"/api/templates/{p['id']}/instantiate", headers=ha, json={"variables": {"t": "OK"}}).status_code == 201

    # --- 7. 删除模板清理版本历史 ---
    assert c.delete(f"/api/templates/{mid}", headers=ha).status_code == 200
    assert c.get(f"/api/templates/{mid}", headers=ha).status_code == 404

print("ALL PASSED")
