# -*- coding: utf-8 -*-
"""⑥导出图表/数学渲染。
- export?fmt=html：含 mermaid 代码块 → 注入 mermaid.js 运行时 + <div class="mermaid">；含 $...$ → 注入 KaTeX。
- 无 mermaid/数学的文档 → 不注入额外运行时。
- 静态站点构建同样包含运行时。
"""
import os, tempfile, io, zipfile, json

TMP = tempfile.mkdtemp(prefix="render_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 不配置 mmdc → 走客户端运行时渲染路径
os.environ.pop("MERMAID_MMDC_COMMAND", None)

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "ru", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "ru", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    mermaid_src = "graph TD\n  A-->B\n  B-->C"
    did = c.post("/api/docs", headers=h, json={
        "title": "图表与数学",
        "content": "# 标题\n\n```mermaid\n" + mermaid_src + "\n```\n\n行内 $E=mc^2$ 与块级 $$\\int_0^1 x dx$$"
    }).json()["doc_id"]
    plain_did = c.post("/api/docs", headers=h, json={"title": "纯文本", "content": "只是普通段落。"}).json()["doc_id"]

    # 含 mermaid+math 的导出
    r = c.get(f"/api/docs/{did}/export?fmt=html", headers=h)
    assert r.status_code == 200, r.text
    html = r.text
    assert '<div class="mermaid">' in html and "graph TD" in html, html
    assert "mermaid" in html.lower() and "mermaid.min.js" in html, "缺 mermaid 运行时"
    assert "katex" in html.lower() and "auto-render" in html, "缺 KaTeX 运行时"
    assert "E=mc^2" in html and "\\int_0^1" in html, html  # 数学原文保留交客户端渲染

    # 纯文本文档 → 不注入额外运行时
    r2 = c.get(f"/api/docs/{plain_did}/export?fmt=html", headers=h)
    plain_html = r2.text
    assert "mermaid.min.js" not in plain_html, "无 mermaid 不应注入"
    assert "katex" not in plain_html.lower(), "无数学不应注入 KaTeX"

    # 静态站点同样注入运行时
    rs = c.post("/api/docs/site/build", headers=h, json={"doc_ids": [did], "title": "S"})
    assert rs.status_code == 200, rs.text
    zf = zipfile.ZipFile(io.BytesIO(rs.content))
    page = next(n for n in zf.namelist() if n.endswith(".html") and n != "index.html")
    sp = zf.read(page).decode("utf-8")
    assert '<div class="mermaid">' in sp and "mermaid.min.js" in sp, sp
    assert "katex" in sp.lower() and "auto-render" in sp, sp

print("ALL PASSED")
