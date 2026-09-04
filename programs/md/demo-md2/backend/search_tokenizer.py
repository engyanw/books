# -*- coding: utf-8 -*-
"""中文分词全文检索 tokenizer。

问题：SQLite FTS5 默认 unicode61 把连续 CJK 视为单个 token（如"项目管理"是 1 个 token），
导致搜"项目"无法命中"项目管理"。本模块在写入 FTS 前对文本做分词，把 CJK 切成 bigram
（"项目管理" → "项目 目管理" ... 实为 2-gram 滑窗），ASCII 按空白/标点切词并小写化。
查询端用同一 tokenizer 处理后拼成 FTS5 AND 查询（每个 token 加引号，空格连接）。

有 jieba 时优先用精确分词（"项目管理流程" → "项目 管理 流程"），更准；
无 jieba 时回退 bigram（无需重依赖，覆盖 2 字及以上中文检索）。
"""
import re

_CJK_RE = re.compile(r"[一-鿿㐀-䶿]")
_CJK_RUN_RE = re.compile(r"[一-鿿㐀-䶿]+")
_ASCII_WORD_RE = re.compile(r"[A-Za-z0-9_]+")

try:  # 惰性、可选依赖
    import jieba  # type: ignore
    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False


def _bigrams(run: str) -> list[str]:
    """CJK 连续段切成 2-gram 滑窗。

    长度 1-2：整段作为一个 token（"项目" → ["项目"]，便于 2 字词精确命中）。
    长度 ≥3：取所有相邻 2-gram（"项目管理" → ["项目","目管","管理"]），
    不再追加末字单字——末单字会作为查询 token 时对索引过度约束（索引里
    未必有该孤立单字 token），反而漏召回。
    """
    n = len(run)
    if n <= 2:
        return [run] if run else []
    return [run[i:i + 2] for i in range(n - 1)]


def tokenize(text: str) -> str:
    """文本 → 空格连接的 token 串（用于写入 FTS5 / 构造查询）。"""
    if not text:
        return ""
    out: list[str] = []
    pos = 0
    for m in _CJK_RUN_RE.finditer(text):
        # ASCII 段
        if m.start() > pos:
            seg = text[pos:m.start()]
            out.extend(w.lower() for w in _ASCII_WORD_RE.findall(seg))
        run = m.group()
        if _HAS_JIEBA:
            try:
                words = [w for w in jieba.cut(run) if w.strip()]
            except Exception:
                words = _bigrams(run)
            # jieba 可能切出 1-2 字词，直接用；但 3 字以上单 token 仍补 bigram 提升召回
            for w in words:
                out.append(w)
                if len(w) > 2:
                    out.extend(_bigrams(w))
        else:
            out.extend(_bigrams(run))
        pos = m.end()
    # 尾部 ASCII
    if pos < len(text):
        out.extend(w.lower() for w in _ASCII_WORD_RE.findall(text[pos:]))
    # 去重保序
    seen = set()
    uniq = []
    for t in out:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return " ".join(uniq)


def build_match_query(q: str) -> str:
    """用户查询 → FTS5 MATCH 串（每个 token 加双引号防注入，空格=AND）。"""
    if not q:
        return ""
    tokens = tokenize(q).split()
    if not tokens:
        return ""
    parts = []
    for t in tokens:
        parts.append('"' + t.replace('"', '""') + '"')
    return " ".join(parts)
