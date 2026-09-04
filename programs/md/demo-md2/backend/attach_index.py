# -*- coding: utf-8 -*-
"""附件文本抽取：把 PDF/DOCX/XLSX/PPTX/TXT 等可读附件转为纯文本，供全文索引。

设计目标：
  - 纯 stdlib 优先，避免重型依赖（python-docx/openpyxl/pypdf）在受限环境装不上。
  - docx/xlsx/pptx 本质是 zip+XML，直接 zipfile + 正则剥离标签即可拿到文本。
  - PDF 真正的文本抽取需要 pypdf/pdfplumber；未安装时降级为""（仅文件名可搜，不报错）。
  - 图片/zip 等无可读文本的返回""（OCR 不在本期范围）。

对外：extract_text(filename, content: bytes) -> str
"""
import os
import re
import zipfile

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_xml(xml_bytes: bytes) -> str:
    """从 XML 字节流剥离标签，返回纯文本。"""
    try:
        text = xml_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    # 把自闭合/标签去掉，保留标签间文本
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _extract_zip_xml(content: bytes, member_patterns) -> str:
    """从 zip 中读取匹配 member_patterns 的成员 XML 文本（合并）。
    member_patterns 支持通配 *（如 'xl/worksheets/sheet*.xml'）。"""
    import io
    parts = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except Exception:
        return ""
    try:
        for n in zf.namelist():
            if _name_matches(n, member_patterns):
                try:
                    parts.append(_strip_xml(zf.read(n)))
                except Exception:
                    continue
    finally:
        zf.close()
    return "\n".join(p for p in parts if p)


def _name_matches(name: str, patterns) -> bool:
    for p in patterns:
        if "*" in p:
            prefix = p.split("*", 1)[0]
            suffix = p.rsplit("*", 1)[-1]
            if name.startswith(prefix) and name.endswith(suffix) and len(name) >= len(prefix) + len(suffix):
                return True
        elif name == p:
            return True
    return False


def _extract_docx(content: bytes) -> str:
    return _extract_zip_xml(content, ["word/document.xml"])


def _extract_pptx(content: bytes) -> str:
    # slides/slide1.xml ... slideN.xml
    return _extract_zip_xml(content, ["ppt/slides/slide*.xml"])


def _extract_xlsx(content: bytes) -> str:
    # sharedStrings.xml 存共享字符串；每个 sheet*.xml 也含内联值
    return _extract_zip_xml(content, ["xl/sharedStrings.xml", "xl/worksheets/sheet*.xml"])


def _extract_pdf(content: bytes) -> str:
    # 优先用 pypdf（如安装）；否则降级为""（不抛错）。
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return ""
    try:
        import io
        reader = PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(p for p in parts if p)
    except Exception:
        return ""


# 纯文本类：直接 decode
_TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".yaml", ".yml", ".ini", ".conf", ".py", ".js", ".ts", ".sh", ".sql", ".html", ".htm", ".xml", ".rst", ".org"}


def extract_text(filename: str, content: bytes) -> str:
    """抽取附件可读文本。返回纯文本（无可读内容返回"")。

    注意：返回的是"原始可读文本"，未做分词；调用方应交 FTS 的 fts_tokenize 处理。
    """
    if not content:
        return ""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in _TEXT_EXTS:
        try:
            return content.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    if ext == ".docx":
        return _extract_docx(content)
    if ext == ".pptx":
        return _extract_pptx(content)
    if ext == ".xlsx":
        return _extract_xlsx(content)
    if ext == ".pdf":
        return _extract_pdf(content)
    if ext == ".zip":
        # 列出压缩包内文件名（可按文件名搜）
        try:
            zf = zipfile.ZipFile(__import__("io").BytesIO(content))
            return "\n".join(zf.namelist())
        except Exception:
            return ""
    # 图片/二进制：无可读文本
    return ""
