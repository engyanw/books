# -*- coding: utf-8 -*-
"""⑤静态站点构建。
- POST /api/docs/site/build：选定的 doc_ids 或全部文档 → zip（各 .html + index.html + manifest.json）。
- 中文标题→安全 slug；同名去重。
- 站内链接 [[doc_id]] / [text](doc:doc_id) 重写为相对 .html 链接。
- 团队站点：成员可读、ACL 拒绝者被剔除；非成员 403。
"""
import os, tempfile, io, zipfile, json

TMP = tempfile.mkdtemp(prefix="site_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "author", "password": "p@ssw0rd"})
    c.post("/api/auth/register", json={"username": "outsider", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "author", "password": "p@ssw0rd"}).json()["token"]
    to = c.post("/api/auth/login", json={"username": "outsider", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    ho = {"Authorization": f"Bearer {to}"}

    d1 = c.post("/api/docs", headers=ha, json={"title": "首页文档", "content": "# 欢迎\n\n参见占位"}).json()["doc_id"]
    d2 = c.post("/api/docs", headers=ha, json={"title": "设计", "content": "链接到 [首页](doc:%s)" % d1}).json()["doc_id"]
    # 回填 d1：用真实 doc_id 写 wikilink 指向 d2
    c.put(f"/api/docs/{d1}", headers=ha, json={"title": "首页文档", "content": "# 欢迎\n\n参见 [[%s|设计]]。" % d2})
    # 同名标题去重
    d3 = c.post("/api/docs", headers=ha, json={"title": "设计", "content": "dup"}).json()["doc_id"]

    # 404：指定不存在的 doc_id
    r0 = c.post("/api/docs/site/build", headers=ha, json={"doc_ids": ["nonexistent"]})
    assert r0.status_code == 404, r0.text

    # 选定 3 篇构建（author 另有 9 篇种子文档，故显式指定）
    r = c.post("/api/docs/site/build", headers=ha, json={"title": "我的站点", "doc_ids": [d1, d2, d3]})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip", r.headers
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "index.html" in names and "manifest.json" in names, names
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["site_title"] == "我的站点" and manifest["page_count"] == 3, manifest
    # slug 去重：两个“设计”应产生不同文件名
    files = [m["file"] for m in manifest["pages"]]
    assert len(set(files)) == 3, files

    # 站内链接重写：d2 的页面应包含指向 d1 slug 的相对链接
    d2_slug = next(m["file"] for m in manifest["pages"] if m["doc_id"] == d2)
    d2_html = zf.read(d2_slug).decode("utf-8")
    d1_slug = next(m["file"] for m in manifest["pages"] if m["doc_id"] == d1).replace(".html", "")
    assert f'href="{d1_slug}.html"' in d2_html, d2_html
    # d1 页面含 wikilink 重写到 d2
    d1_html = zf.read(next(m["file"] for m in manifest["pages"] if m["doc_id"] == d1)).decode("utf-8")
    d2_slug_base = d2_slug.replace(".html", "")
    assert f'href="{d2_slug_base}.html"' in d1_html, d1_html
    # index 列出全部
    idx = zf.read("index.html").decode("utf-8")
    assert all(m["title"] in idx for m in manifest["pages"]), idx

    # 指定 doc_ids 子集
    rsub = c.post("/api/docs/site/build", headers=ha, json={"doc_ids": [d1]})
    assert rsub.status_code == 200
    msub = json.loads(zipfile.ZipFile(io.BytesIO(rsub.content)).read("manifest.json"))
    assert msub["page_count"] == 1 and msub["pages"][0]["doc_id"] == d1, msub

    # 非本人文档 doc_id（不存在）→ 404（无行）
    assert c.post("/api/docs/site/build", headers=ha, json={"doc_ids": ["nope"]}).status_code == 404

    # ---- 团队站点 ----
    tid = c.post("/api/teams", headers=ha, json={"name": "TeamS"}).json()["team_id"]
    td1 = c.post(f"/api/teams/{tid}/docs", headers=ha, json={"title": "T1", "content": "团队页"}).json()["doc_id"]
    # outsider 非成员 → 403
    assert c.post(f"/api/teams/{tid}/site/build", headers=ho, json={}).status_code == 403
    # 成员构建
    rt = c.post(f"/api/teams/{tid}/site/build", headers=ha, json={})
    assert rt.status_code == 200, rt.text
    mt = json.loads(zipfile.ZipFile(io.BytesIO(rt.content)).read("manifest.json"))
    assert mt["page_count"] == 1 and mt["pages"][0]["doc_id"] == td1, mt

print("ALL PASSED")
