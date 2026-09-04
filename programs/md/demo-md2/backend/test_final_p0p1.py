# -*- coding: utf-8 -*-
"""P0-2/3 + P1-4: 保存搜索触发 + 定时发布调度 + AI 对话分支。"""
import os, shutil, tempfile, json
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="fin_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "a", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "b", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "a", "password": "p@ssw0rd"}).json()["token"]
    tb = c.post("/api/auth/login", json={"username": "b", "password": "p@ssw0rd"}).json()["token"]
    ha, hb = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}

    # ===== 保存搜索→通知触发 =====
    c.post("/api/saved-searches", json={"name": "K8s", "query": "kubernetes"}, headers=hb)
    # a 创建含 "kubernetes" 的文档 → b 应收到 search.match 通知
    c.post("/api/docs", json={"title": "k8s-guide.md", "content": "# Kubernetes 部署指南"}, headers=ha)
    notifs = c.get("/api/notifications", headers=hb).json()["items"]
    assert any(n["type"] == "search.match" for n in notifs), f"b 应收到 search.match 通知: {notifs}"
    # a 创建不含关键词的文档 → 不通知
    c.post("/api/docs", json={"title": "other.md", "content": "hello"}, headers=ha)
    notifs2 = c.get("/api/notifications", headers=hb).json()["items"]
    search_notifs = [n for n in notifs2 if n["type"] == "search.match"]
    assert len(search_notifs) == 1, f"不应有新通知: {search_notifs}"

    # ===== AI 对话分支 =====
    msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}, {"role": "user", "content": "bye"}]
    r = c.post("/api/ai/conversations", json={"messages": msgs}, headers=ha)
    cid = r.json()["id"]
    # 从第 2 条消息分叉（截取前 2 条）
    r = c.post(f"/api/ai/conversations/{cid}/fork?fork_at=2", headers=ha)
    assert r.status_code == 201, r.text
    fork = r.json()
    assert fork["parent_id"] == cid and fork["fork_at"] == 2, fork
    # 加载分叉对话，应有 2 条消息
    loaded = c.get(f"/api/ai/conversations/{fork['id']}", headers=ha).json()
    assert len(loaded["messages"]) == 2, loaded

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
