# -*- coding: utf-8 -*-
"""T4：服务端版本历史（快照/列表/获取/恢复）+ DLP 数据分级（机密禁分享/禁提级）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="t4_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "vuser", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "vuser", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 建文档 v1
    did = c.post("/api/docs", json={"title": "doc", "content": "v1"}, headers=h).json()["doc_id"]
    # 更新到 v2、v3
    c.put(f"/api/docs/{did}", json={"content": "v2", "version": 1}, headers=h)
    c.put(f"/api/docs/{did}", json={"content": "v3", "version": 2}, headers=h)
    cur = c.get(f"/api/docs/{did}", headers=h).json()
    assert cur["content"] == "v3" and cur["version"] == 3, cur

    # 版本列表（应有 v1、v2 两份快照，最新在前）
    vers = c.get(f"/api/docs/{did}/versions", headers=h).json()["items"]
    assert len(vers) == 2, vers
    assert vers[0]["version"] == 2 and vers[1]["version"] == 1, vers

    # 获取某版本内容
    v1 = c.get(f"/api/docs/{did}/versions/{vers[1]['id']}", headers=h).json()
    assert v1["content"] == "v1", v1

    # 恢复 v1：当前变回 v1 内容，版本号 4
    r = c.post(f"/api/docs/{did}/versions/{vers[1]['id']}/restore", headers=h)
    assert r.status_code == 200 and r.json()["version"] == 4, r.text
    cur2 = c.get(f"/api/docs/{did}", headers=h).json()
    assert cur2["content"] == "v1" and cur2["version"] == 4, cur2

    # DLP：设为机密 -> 禁止公开分享
    r = c.put(f"/api/docs/{did}/meta", json={"classification": "confidential"}, headers=h)
    assert r.status_code == 200, r.text
    r = c.post(f"/api/docs/{did}/share", json={"mode": "readonly"}, headers=h)
    assert r.status_code == 403 and "机密" in r.json()["detail"], r.text
    # 降回 internal 后可分享
    c.put(f"/api/docs/{did}/meta", json={"classification": "internal"}, headers=h)
    r = c.post(f"/api/docs/{did}/share", json={"mode": "readonly"}, headers=h)
    assert r.status_code == 200, r.text
    # 正在分享时禁止提级为机密
    r = c.put(f"/api/docs/{did}/meta", json={"classification": "confidential"}, headers=h)
    assert r.status_code == 409 and "机密" in r.json()["detail"], r.text

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
