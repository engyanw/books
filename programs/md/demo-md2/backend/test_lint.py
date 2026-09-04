# -*- coding: utf-8 -*-
"""P0-1：内容 Lint（死链/死图/风格）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="lint_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "lintu", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "lintu", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 干净文档
    did_clean = c.post("/api/docs", json={"title": "clean.md", "content": "# Title\n\n![alt](https://example.com/img.png)\n\n```python\ncode\n```"}, headers=h).json()["doc_id"]
    r = c.post(f"/api/docs/{did_clean}/lint", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 0, r.json()

    # 有问题文档
    did = c.post("/api/docs", json={"title": "messy.md", "content": "# H1\n\n### H3 jumped\n\n![no-alt](https://example.com/img.png)\n\n```\nno lang\n```\n\n[dead](nonexistent-doc-id)\n"}, headers=h).json()["doc_id"]
    r = c.post(f"/api/docs/{did}/lint", headers=h)
    findings = r.json()["findings"]
    print("findings:", findings)
    types = [f["type"] for f in findings]
    assert "dead_link" in types, types  # nonexistent-doc-id 不存在
    assert "style" in types, types  # 图片无 alt + 代码块无语言
    # 标题跳跃 H1→H3
    heading_jumps = [f for f in findings if "跳跃" in f.get("message", "")]
    assert len(heading_jumps) >= 1, findings

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
