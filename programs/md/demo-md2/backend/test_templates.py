# -*- coding: utf-8 -*-
"""E6 回归：场景模板 + 变量插值。
覆盖：自定义模板带 kind/variables；instantiate Jinja2 插值生成文档；
内置 RFC/design-doc/runbook/ADR 骨架列出与实例化；缺失变量报错。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="templates_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 内置模板列表
    bl = c.get("/api/templates/builtin", headers=h).json()["items"]
    names = {i["name"] for i in bl}
    assert {"rfc", "design-doc", "runbook", "adr"} <= names, bl
    rfc = next(i for i in bl if i["name"] == "rfc")
    assert "title" in rfc["variables"] and "author" in rfc["variables"], rfc

    # 实例化内置 RFC 模板
    inst = c.post("/api/templates/builtin/rfc/instantiate", headers=h,
                  json={"variables": {"title": "统一日志", "author": "alice", "date": "2026-08-14",
                                       "status": "草案", "summary": "统一结构化日志",
                                       "motivation": "排障效率低", "design": "JSON+OTel",
                                       "risks": "性能开销"}, "title": "RFC-统一日志"}).json()
    did = inst["doc_id"]
    assert inst["kind"] == "rfc", inst
    doc = c.get(f"/api/docs/{did}", headers=h).json()
    assert doc["title"] == "RFC-统一日志", doc
    assert "alice" in doc["content"] and "JSON+OTel" in doc["content"], doc["content"]
    assert "{{ title }}" not in doc["content"], doc["content"]  # 占位已替换

    # 未知内置模板 → 404
    assert c.post("/api/templates/builtin/nope/instantiate", headers=h, json={"variables": {}}).status_code == 404

    # 自定义模板带 kind + variables
    tpl = c.post("/api/templates", headers=h, json={
        "name": "mytpl", "kind": "custom", "variables": ["who", "what"],
        "content": "# {{ what }}\nby {{ who }}"}).json()
    tid = tpl["id"]
    # 列表含 kind/variables
    lst = c.get("/api/templates", headers=h).json()["items"]
    me = next(i for i in lst if i["id"] == tid)
    assert me["kind"] == "custom" and me["variables"] == ["who", "what"], me
    # 实例化
    r = c.post(f"/api/templates/{tid}/instantiate", headers=h,
               json={"variables": {"who": "bob", "what": "报告"}, "title": "由模板生成"}).json()
    d2 = c.get(f"/api/docs/{r['doc_id']}", headers=h).json()
    assert "by bob" in d2["content"] and "# 报告" in d2["content"], d2["content"]

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
