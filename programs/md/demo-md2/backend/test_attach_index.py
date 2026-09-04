# -*- coding: utf-8 -*-
"""#3 二进制附件全文索引 回归。

验证：
  1. attach_index.extract_text：txt 直解；docx（zip+XML）剥标签得文本；pdf 无 pypdf 时空（不抛）。
  2. POST /api/upload?doc_id=... 索引附件（返回 indexed=True + extracted_chars>0）。
  3. GET /api/attachments/search?q=... 命中附件内容。
  4. GET /api/docs/{doc_id}/attachments 列出附件。
  5. GET /api/search?q=... 全局搜索返回 kind="attachment" 命中（与文档结果合并）。
"""
import os, shutil, tempfile, io, zipfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="attach_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"

import main  # noqa: E402
import attach_index  # noqa: E402


def _make_docx(text: str) -> bytes:
    """构造最小合法 docx（zip：含 word/document.xml）。"""
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        + "".join(f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>' for text in text.split("\n"))
        + '</w:body></w:document>'
    )
    buf = io.BytesIO()
    zf = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
    zf.writestr("word/document.xml", doc_xml)
    zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
    zf.close()
    return buf.getvalue()


# --- 1) 抽取函数单测 ---
txt = b"hello searchable attachment content"
assert attach_index.extract_text("a.txt", txt) == "hello searchable attachment content"
docx_bytes = _make_docx("架构决策记录\nADR-007 数据加密")
extracted = attach_index.extract_text("a.docx", docx_bytes)
assert "架构决策记录" in extracted and "ADR-007" in extracted, extracted
# pdf 无 pypdf 时返回""（不抛）
pdf_text = attach_index.extract_text("a.pdf", b"%PDF-1.4 garbage")
assert pdf_text == "", pdf_text  # 环境无 pypdf 则空；若有 pypdf 也接受非空
# 图片返回""（无可读文本）
assert attach_index.extract_text("a.png", b"\x89PNG\r\n") == ""
print("extract_text OK")

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 创建一个文档用于关联附件
    did = c.post("/api/docs", headers=h, json={"title": "doc", "content": "# main"}).json()["doc_id"]

    # --- 2) 上传 txt 附件，关联 doc_id，应被索引 ---
    r = c.post("/api/upload?doc_id=" + did, headers=h,
               files={"file": ("notes.txt", txt, "text/plain")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["indexed"] is True and body["extracted_chars"] > 0, body

    # 上传 docx 附件
    r = c.post("/api/upload?doc_id=" + did, headers=h,
               files={"file": ("adr.docx", _make_docx("架构决策记录 ADR-007"), "application/vnd.openxmlformats")})
    assert r.status_code == 200, r.text
    assert r.json()["indexed"] is True, r.json()

    # 上传图片（不应被索引，indexed=False）
    r = c.post("/api/upload", headers=h,
               files={"file": ("pic.png", b"\x89PNG\r\n\x1a\n", "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["indexed"] is False, r.json()

    # --- 3) 附件搜索：命中 txt 内容 ---
    r = c.get("/api/attachments/search?q=searchable", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert any(i["filename"] == "notes.txt" for i in items), items
    # 命中 docx 内容
    r = c.get("/api/attachments/search?q=架构决策", headers=h)
    items = r.json()["items"]
    assert any(i["filename"] == "adr.docx" for i in items), items

    # --- 4) 列出文档附件 ---
    r = c.get(f"/api/docs/{did}/attachments", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    names = {i["filename"] for i in items}
    assert "notes.txt" in names and "adr.docx" in names, names
    txt_item = next(i for i in items if i["filename"] == "notes.txt")
    assert txt_item["indexed_chars"] > 0, txt_item

    # --- 5) 全局搜索返回 attachment 命中 ---
    r = c.get("/api/search?q=searchable", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert any(i.get("kind") == "attachment" and i["filename"] == "notes.txt" for i in items), items

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
