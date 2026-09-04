# -*- coding: utf-8 -*-
"""P1-7 企业导出格式：单文档 md/html/confluence + 批量 zip（含 manifest）。
验证：md 为原文下载；html 含渲染后的 <h1>/<ul>/<pre>；confluence 为 XHTML；zip 解压含每文档 .md + manifest.json。
"""
import os, tempfile, io, zipfile, json

TMP = tempfile.mkdtemp(prefix="exp_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

MD = "# 标题一\n\n这是 **粗体** 与 `code` 和 [链接](https://x.com)。\n\n- 项 A\n- 项 B\n\n```\ncode block\n```"

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "exp", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "exp", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    did = c.post("/api/docs", headers=h, json={"title": "导出测试", "content": MD}).json()["doc_id"]

    # md 导出 = 原文
    r = c.get(f"/api/docs/{did}/export?fmt=md", headers=h)
    assert r.status_code == 200, r.status_code
    assert "text/markdown" in r.headers.get("content-type", ""), r.headers
    assert "粗体" in r.text and "标题一" in r.text, r.text

    # html 导出：含 <h1>/<ul>/<pre>/<strong>/<a>
    r2 = c.get(f"/api/docs/{did}/export?fmt=html", headers=h)
    body = r2.text
    assert "<h1>标题一</h1>" in body, body
    assert "<ul>" in body and "<li>项 A</li>" in body, body
    assert "<strong>粗体</strong>" in body, body
    assert '<a href="https://x.com">链接</a>' in body, body
    assert "<pre><code" in body and "code block" in body, body
    assert "javascript:" not in body  # 转义安全

    # confluence：XHTML 根
    r3 = c.get(f"/api/docs/{did}/export?fmt=confluence", headers=h)
    assert "<html>" in r3.text and "<h1>导出测试</h1>" in r3.text, r3.text
    assert "application/xhtml+xml" in r3.headers.get("content-type", "")

    # zip 批量
    z = c.get("/api/docs/bulk-export.zip", headers=h)
    assert z.status_code == 200 and "application/zip" in z.headers.get("content-type", ""), z.headers
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    names = zf.namelist()
    assert "manifest.json" in names, names
    md_files = [n for n in names if n.endswith(".md")]
    assert len(md_files) >= 1, names
    man = json.loads(zf.read("manifest.json"))
    assert man["count"] >= 1 and any(m["doc_id"] == did for m in man["items"]), man
    assert "标题一" in zf.read(md_files[0]).decode("utf-8")

print("ALL PASSED")
