"""
 代码沙箱代理后端：将前端代码运行请求转发到自建 Judge0 执行引擎。
 同时提供跨域图片代理、PlantUML 渲染代理、文档云端同步/分享、速率限制等能力。
 
 启动方式：
     uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import asyncio
import base64
from collections import OrderedDict
import difflib
import hashlib
import hmac
import json
import logging
from functools import lru_cache
import os
import re
import secrets
import sqlite3
import string
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlencode, urlparse

import aiosqlite
import httpx
from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, RedirectResponse, HTMLResponse
from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from pydantic import BaseModel

# ==================== 模块导入 ====================
from config import *
from config import logger, LANGUAGE_ID_MAP, LANGUAGE_DISPLAY_NAME
from pg_adapter import _asyncpg_available  # asyncpg 是否可用（PG 双模式探测）
from observability import observe_request, span, render_prometheus, snapshot as metrics_snapshot  # noqa: E402
from search_tokenizer import tokenize as _fts_tokenize_text, build_match_query as _fts_build_query  # noqa: E402
from security import is_ssrf_url, is_blocked_ip
from taskqueue import (  # noqa: E402
    enqueue, register_task, get_redis, close_redis,
    worker_loop, presence_bus, REDIS_URL, allow_rate,
)

# Sentry 错误追踪（可选，设 SENTRY_DSN 启用）
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1,
                         environment=os.environ.get("APP_ENV", "development"))
        logger.info("Sentry 已启用")
    except ImportError:
        logger.warning("sentry-sdk 未安装，跳过 Sentry 初始化")

app = FastAPI(title="代码沙箱代理", version="2.0.0")

_cors_origins = CORS_ALLOWED_ORIGINS.split(",") if CORS_ALLOWED_ORIGINS else ["*"]
# 生产环境强制 CORS 白名单：未显式配置则仅允许本地源
if "*" in _cors_origins and os.environ.get("APP_ENV", "").lower() == "production":
    logger.warning("CORS: 生产环境不允许 *，自动收紧为 localhost:3000")
    _cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 安全响应头中间件 ====================
@app.middleware("http")
async def security_headers(request: Request, call_next):
    """为所有响应附加安全响应头（CSP/HSTS/X-Frame-Options 等）。
    开发环境(http)不下发 HSTS，避免锁死本地 http。"""
    resp: Response = await call_next(request)
    if SECURITY_HEADERS_ENABLED:
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        # CSP 仅对 HTML/文本响应下发，避免误伤静态资源/文件下载
        ctype = resp.headers.get("content-type", "")
        if "text/html" in ctype or "application/json" in ctype or ctype == "":
            resp.headers["Content-Security-Policy"] = CSP_DIRECTIVES
        # HSTS 仅在 HTTPS 下生效
        scheme = request.url.scheme
        if scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            resp.headers["Strict-Transport-Security"] = (
                f"max-age={HSTS_MAX_AGE}; includeSubDomains"
            )
    return resp



# ==================== SQLite：共享注册库 + 每用户文档库 ====================
# 共享注册库（registry.db）：users 表（登录鉴权）+ shares 路由表（分享码 → 属主用户）。
# 每用户库（users/<uid>/docs.db）：该用户自己的 documents 表，物理隔离。
_registry_pool: list[aiosqlite.Connection] = []
# OrderedDict 按 LRU 排序（最近访问在尾）；超出 MAX_USER_POOLS/MAX_TEAM_POOLS 时淘汰队首（最久未用）。
_user_db_pools: "OrderedDict[str, list[aiosqlite.Connection]]" = OrderedDict()
_user_db_initialized: set[str] = set()
_DB_POOL_SIZE = 10  # 共享注册库连接池上限
# 后台任务引用：startup 持有，shutdown 时统一 cancel+wait，确保优雅 drain
_bg_tasks: list = []

# 运维状态（供 /metrics 暴露，驱动备份失败/leader 抖动告警）。
# 备份：成功/失败时间戳（unix epoch）+ 累计失败数；leader：本实例是否持主 + 抢主次数。
_ops_state: dict = {
    "backup_last_success": 0.0,
    "backup_last_failure": 0.0,
    "backup_failures": 0,
    "leader_is_leader": 1,   # 未启用选举时恒为 1（_am_leader 恒 True）
    "leader_changes": 0,
}


def _total_idle_connections() -> int:
    """所有用户/团队/registry 池中当前空闲连接总数。"""
    return (len(_registry_pool)
            + sum(len(p) for p in _user_db_pools.values())
            + sum(len(p) for p in _team_db_pools.values()))


async def _close_pool_entries(entries: list) -> None:
    """逐条关闭一个池容器里的所有连接。"""
    while entries:
        db = entries.pop()
        try:
            await db.close()
        except Exception:
            pass


async def _evict_user_pools_if_needed() -> None:
    """超 MAX_USER_POOLS 或全局 idle 超上限时，按 LRU 淘汰最久未用用户池。"""
    while len(_user_db_pools) > MAX_USER_POOLS or (MAX_TOTAL_IDLE_CONNECTIONS and _total_idle_connections() > MAX_TOTAL_IDLE_CONNECTIONS):
        if not _user_db_pools:
            break
        uid, pool = _user_db_pools.popitem(last=False)  # 最久未用
        await _close_pool_entries(pool)
        _user_db_initialized.discard(uid)
        # 全局 idle 仍超且团队池也可淘汰
        if len(_user_db_pools) == 0:
            break


async def _evict_team_pools_if_needed() -> None:
    while len(_team_db_pools) > MAX_TEAM_POOLS or (MAX_TOTAL_IDLE_CONNECTIONS and _total_idle_connections() > MAX_TOTAL_IDLE_CONNECTIONS):
        if not _team_db_pools:
            break
        tid, pool = _team_db_pools.popitem(last=False)
        await _close_pool_entries(pool)
        _team_db_initialized.discard(tid)
        if len(_team_db_pools) == 0:
            break


def _ensure_parent(path: str) -> None:
    """确保给定文件路径的父目录存在（sqlite 无法自动创建不存在的目录）。"""
    parent = Path(path).parent
    parent.mkdir(parents=True, exist_ok=True)


def _data_dir() -> Path:
    p = Path(DOC_DATA_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _residency_dir(region: str = "") -> Path:
    """数据驻留分区根目录：region 对应 RESIDENCY_REGIONS[region].dir，否则落 DOC_DATA_DIR/regions/{region} 或 DOC_DATA_DIR。"""
    if not region:
        return _data_dir()
    cfg = RESIDENCY_REGIONS.get(region) if RESIDENCY_REGIONS else None
    if isinstance(cfg, dict) and cfg.get("dir"):
        p = Path(cfg["dir"])
    else:
        p = _data_dir() / "regions" / region
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sync_read_region(table: str, key: str, key_col: str = "user_id") -> str:
    """同步只读查询 users/teams.residency_region（路径层在 DB 打开前调用）。
    失败/未启用返回空串（回退默认目录）。独立连接、短超时，不影响异步池。"""
    if not DATA_RESIDENCY_ENABLED:
        return ""
    import sqlite3 as _s
    try:
        conn = _s.connect(REGISTRY_DB_PATH, timeout=1.0)
        try:
            row = conn.execute(f"SELECT residency_region FROM {table} WHERE {key_col}=?", (key,)).fetchone()
            return (row[0] if row else "") or ""
        finally:
            conn.close()
    except Exception:
        return ""


def _user_db_path(user_id: str) -> Path:
    region = _sync_read_region("users", user_id)
    d = _residency_dir(region) / "users" / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "docs.db"


def _config_path(user_id: str) -> Path:
    d = _data_dir() / "configs"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{user_id}.json"


# documents 表的建表 + 兼容旧库补列 + 索引（每用户库通用，不含 users 表）
_DOCUMENTS_ADD_COLUMNS = [
    "ALTER TABLE documents ADD COLUMN kind TEXT NOT NULL DEFAULT 'file'",
    "ALTER TABLE documents ADD COLUMN path TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE documents ADD COLUMN user_id TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE documents ADD COLUMN deleted_at TEXT",
    "ALTER TABLE documents ADD COLUMN tags TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE documents ADD COLUMN starred INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN last_opened_at TEXT",
    "ALTER TABLE documents ADD COLUMN share_password TEXT",
    "ALTER TABLE documents ADD COLUMN share_max_views INTEGER",
    "ALTER TABLE documents ADD COLUMN share_views INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN share_burn_after_read INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN share_mode TEXT NOT NULL DEFAULT 'readonly'",
    "ALTER TABLE documents ADD COLUMN is_encrypted INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN enc_salt TEXT",
    "ALTER TABLE documents ADD COLUMN enc_iv TEXT",
    "ALTER TABLE documents ADD COLUMN enc_iters INTEGER NOT NULL DEFAULT 0",
    # DLP 数据分级：public/internal/confidential；机密文档禁止公开分享
    "ALTER TABLE documents ADD COLUMN classification TEXT NOT NULL DEFAULT 'internal'",
    # 文档状态机：draft/in_review/approved/published/archived
    "ALTER TABLE documents ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'",
    # 归档标记：archived=1 表示文档已归档（冷存储，只读，默认从列表隐藏）
    "ALTER TABLE documents ADD COLUMN archived INTEGER NOT NULL DEFAULT 0",
    # 文档级乐观锁：ETag（内容哈希），PUT 携带 If-Match 校验，失配 409
    "ALTER TABLE documents ADD COLUMN etag TEXT NOT NULL DEFAULT ''",
]


async def _apply_documents_schema(db):
    """对给定连接建 documents 表 + 补列 + 索引（幂等）。

    同时注册 fts_tokenize SQL 函数，使 FTS5 触发器在该连接上可调用
    （直接拿 raw 连接跑 schema 的测试/脚本也能正常插入文档）。
    """
    await _register_fts_function(db)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            share_code TEXT UNIQUE,
            share_expires_at TEXT,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)
    for stmt in _DOCUMENTS_ADD_COLUMNS:
        try:
            await db.execute(stmt)
        except sqlite3.OperationalError:
            pass
    await db.execute("CREATE INDEX IF NOT EXISTS idx_share_code ON documents(share_code)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON documents(updated_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_path ON documents(path)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_user ON documents(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_deleted_at ON documents(deleted_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_starred ON documents(starred)")
    # 服务端版本历史：每次更新存快照，便于回溯（替代 localStorage 50 条上限）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            created_by TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON doc_versions(doc_id)")
    # 细粒度文档 ACL：非文档属主也可被授予单篇文档的 read/write 权限（可设过期时间）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_acl (
            doc_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            permission TEXT NOT NULL DEFAULT 'read',
            granted_at TEXT NOT NULL,
            expires_at TEXT,
            PRIMARY KEY (doc_id, user_id)
        )
    """)
    try:
        await db.execute("ALTER TABLE doc_acl ADD COLUMN expires_at TEXT")
    except sqlite3.OperationalError:
        pass
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_acl_user ON doc_acl(user_id)")
    # 内容变更建议（非破坏性评审）：他人提议修改，作者接受/驳回
    await db.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            proposer_id TEXT NOT NULL,
            original_text TEXT NOT NULL DEFAULT '',
            proposed_text TEXT NOT NULL DEFAULT '',
            comment TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            decided_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_suggestions_doc ON suggestions(doc_id)")
    # C2：行锚点评论 + 线程（parent_id 实现回复树；锚点定位文档内片段）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            doc_version INTEGER,
            anchor_type TEXT NOT NULL DEFAULT 'line',
            anchor_start INTEGER,
            anchor_end INTEGER,
            selector TEXT,
            author_user_id TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            parent_id INTEGER,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolver_user_id TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_comments_doc ON doc_comments(doc_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_comments_parent ON doc_comments(parent_id)")
    # P1-8 生命周期门禁电子签名：签署记录绑定签署时刻的内容哈希（防内容事后篡改）。
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_signatures (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            doc_version INTEGER NOT NULL,
            signer_user_id TEXT NOT NULL,
            intent TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            signed_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_sig_doc ON doc_signatures(doc_id)")
    # E2：并行草稿（branch-like drafts）+ 合并。head_content 为分支工作版本；base_content 用于三方合并基线。
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_branches (
            branch_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            base_version INTEGER NOT NULL,
            base_content TEXT NOT NULL DEFAULT '',
            head_content TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            author TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            merged_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_branches_doc ON doc_branches(doc_id)")
    # E5：结构化链接图（断链检测）。broken=1 表示目标在当前库中不存在。
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_doc_id TEXT NOT NULL,
            target_ref TEXT NOT NULL,
            target_doc_id TEXT,
            kind TEXT NOT NULL DEFAULT 'wikilink',
            broken INTEGER NOT NULL DEFAULT 0,
            checked_at TEXT,
            UNIQUE(source_doc_id, target_ref)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_links_source ON doc_links(source_doc_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_links_broken ON doc_links(broken)")
    # 文档贡献统计：每次更新记录贡献者增删行数
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_contributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            lines_added INTEGER NOT NULL DEFAULT 0,
            lines_deleted INTEGER NOT NULL DEFAULT 0,
            ts TEXT NOT NULL
        )
    """)
    # FTS5 全文索引：加速跨文档搜索（LIKE → MATCH）
    # 中文分词：触发器对 title/content 调 fts_tokenize（bigram/jieba）后再入索引，
    # 使"项目"能命中"项目管理流程"（unicode61 默认会把整段 CJK 当 1 个 token 导致漏召回）。
    try:
        await db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(doc_id, title, content, content_rowid='rowid')")
        # 旧触发器（未分词版本）先删后建，保证新库/旧库都走分词
        await db.execute("DROP TRIGGER IF EXISTS documents_ai")
        await db.execute("DROP TRIGGER IF EXISTS documents_ad")
        await db.execute("DROP TRIGGER IF EXISTS documents_au")
        # 触发器：仅当 title/content 变化时同步 FTS 索引（分词后入库）。
        # WHEN 子句确保 status/starred/tags/path 等元数据更新不触发 fts_tokenize，
        # 既减少无效写，也避免未注册该函数的 raw 连接（脚本/测试直连 sqlite3）报错。
        await db.execute("""
            CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(doc_id, title, content) VALUES (new.doc_id, fts_tokenize(new.title), fts_tokenize(new.content));
            END
        """)
        await db.execute("""
            CREATE TRIGGER documents_ad AFTER DELETE ON documents BEGIN
                DELETE FROM documents_fts WHERE doc_id = old.doc_id;
            END
        """)
        await db.execute("""
            CREATE TRIGGER documents_au AFTER UPDATE OF title, content ON documents BEGIN
                DELETE FROM documents_fts WHERE doc_id = old.doc_id;
                INSERT INTO documents_fts(doc_id, title, content) VALUES (new.doc_id, fts_tokenize(new.title), fts_tokenize(new.content));
            END
        """)
        # 首次建索引：填充现有数据（分词后入库）
        await db.execute("INSERT OR IGNORE INTO documents_fts(doc_id, title, content) SELECT doc_id, fts_tokenize(title), fts_tokenize(content) FROM documents WHERE deleted_at IS NULL")
    except sqlite3.OperationalError:
        pass  # FTS5 不可用（旧版 SQLite）或 PG 模式
    # 附件表 + 附件全文索引：抽取 PDF/DOCX/XLSX/PPTX/TXT/MD 等可读文本入 FTS，
    # 使"搜索文档"也能搜到附件内容（docs-as-code 场景的常见诉求）。
    await db.execute("""
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT,
            owner_user_id TEXT NOT NULL,
            filename TEXT NOT NULL DEFAULT '',
            storage_url TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT '',
            size INTEGER NOT NULL DEFAULT 0,
            extracted_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_attachments_doc ON attachments(doc_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_attachments_owner ON attachments(owner_user_id)")
    try:
        await db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS attachments_fts USING fts5(attachment_id, doc_id, filename, content, content_rowid='rowid')")
    except sqlite3.OperationalError:
        pass  # FTS5 不可用
    await db.execute("CREATE INDEX IF NOT EXISTS idx_contrib_doc ON doc_contributions(doc_id)")
    await db.commit()


# ==================== AI 配置加密存储 ====================
# 每用户的大模型 api_key 用 AES-GCM(Fernet) 加密后落库（enc_key 字段），
# 主密钥由 AI_ENC_KEY（默认=AUTH_SECRET）经 HKDF 派生。明文 key 永不落盘、永不回传前端。
# 密钥轮换：AI_ENC_KEY=当前密钥；AI_ENC_KEY_PREVIOUS=逗号分隔的旧密钥。
# 新写入用当前密钥并标注 kid；读取时按 kid 选密钥（旧密文回退试全部密钥）。
_ai_ciphers: list[tuple[str, object]] = []  # [(kid, Fernet), ...] 当前在前


def _kid_of(key_material: str) -> str:
    return hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:8]


def _ai_build_ciphers():
    """惰性构建 (kid, Fernet) 列表：当前密钥在前，其后为历史密钥。

    密钥来源：
    - env 提供者（默认）：用本模块 AI_ENC_KEY 全局（可被运行时/测试改写以模拟轮换），
      历史 key 取 AI_ENC_KEY_PREVIOUS 环境变量。
    - vault/http 提供者：经 kms.resolve_current/resolve_previous 取（见 kms 模块）。
    """
    global _ai_ciphers
    if _ai_ciphers:
        return _ai_ciphers
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    import kms as _kms
    provider = (os.environ.get("KMS_PROVIDER") or "env").lower()
    if provider in ("vault", "http", "cloud"):
        cur = _kms.resolve_current()
        prev = _kms.resolve_previous()
    else:
        cur = AI_ENC_KEY  # 模块全局（config 导入；测试/运维可改写模拟轮换）
        prev = [m.strip() for m in os.environ.get("AI_ENC_KEY_PREVIOUS", "").split(",") if m.strip()]
    materials = []
    if cur:
        materials.append(("current", cur))
    for i, m in enumerate(prev):
        materials.append((f"prev{i}", m))
    ciphers = []
    for _tag, mat in materials:
        kdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"md-editor-ai-enc", info=b"ai-api-key-aes")
        key = kdf.derive(mat.encode("utf-8"))
        ciphers.append((_kid_of(mat), Fernet(_b64url(key))))
    _ai_ciphers = ciphers
    return ciphers


def _ai_fernet_cipher():
    """当前密钥的 Fernet（兼容旧调用点）。"""
    ciphers = _ai_build_ciphers()
    return ciphers[0][1] if ciphers else None


def _b64url(b: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(b).decode("ascii")


def _ai_encrypt(plaintext: str) -> str:
    """加密并标注 kid（当前密钥）。格式：{kid}:{fernet_token}。"""
    if not plaintext:
        return ""
    ciphers = _ai_build_ciphers()
    if not ciphers:
        return ""
    kid, cipher = ciphers[0]
    token = cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{kid}:{token}"


def _ai_decrypt(token: str) -> str:
    """解密：按 kid 选密钥；无 kid（旧密文）回退试全部密钥。"""
    if not token:
        return ""
    ciphers = _ai_build_ciphers()
    if not ciphers:
        return ""
    try:
        # 新格式：{kid}:{fernet}
        if ":" in token and not token.startswith("gAAAAA"):
            kid, _, body = token.partition(":")
            for k, cipher in ciphers:
                if k == kid:
                    return cipher.decrypt(body.encode("ascii")).decode("utf-8")
            # kid 未匹配（密钥已彻底下线）→ 失败
        # 旧格式（无 kid）：逐个密钥试
        for _k, cipher in ciphers:
            try:
                return cipher.decrypt(token.encode("ascii")).decode("utf-8")
            except Exception:
                continue
    except Exception as e:
        logger.warning("AI key 解密失败: %s", e)
    logger.warning("AI key 解密失败：无可用密钥（可能密钥已下线或数据损坏）")
    return ""


def _ai_key_hint(plaintext: str) -> str:
    """脱敏提示：仅显示末 4 位。"""
    if not plaintext:
        return ""
    if len(plaintext) <= 4:
        return "*" * len(plaintext)
    return "*" * (len(plaintext) - 4) + plaintext[-4:]


# ==================== 文档正文静态加密（受监管多租户场景）====================
# 密文标记 atrestv1: 前缀，支持明文/密文混合行共存、开关切换与密钥轮换（按标记识别后解密）。
# 轮换模型（P1-5）：当前密钥在前，历史密钥存于 _doc_atrest_old_ciphers 供漏网行回退解密。
# 轮换时 sweep 全表 atrestv1 密文 → 用旧密钥解密 → 用新密钥重加密 → 切换 current。
_ATREST_PREFIX = "atrestv1:"
_doc_atrest_cipher = None  # 当前 Fernet（惰性缓存；轮换后指向新密钥）
_doc_atrest_old_ciphers: list = []  # 历史 Fernet（轮换后旧 current 入此，供漏网行回退解密）
_doc_atrest_current_key_material: str | None = None  # 当前密钥原文（仅进程内，不落盘/不回传）


def _atrest_kid(key_material: str) -> str:
    """密钥标识：sha256 前 8 hex。非敏感，用于运维对齐当前密钥而无需暴露密钥本身。"""
    return hashlib.sha256(("atrest:" + key_material).encode("utf-8")).hexdigest()[:8]


def _build_atrest_fernet(key_material: str):
    """从密钥原文经独立 HKDF 域派生 32B → Fernet。与 _doc_atrest_build_cipher 同域。"""
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    kdf = HKDF(algorithm=hashes.SHA256(), length=32,
               salt=b"md-editor-doc-atrest", info=b"doc-content-aes")
    return Fernet(_b64url(kdf.derive(key_material.encode("utf-8"))))


def _doc_atrest_build_cipher():
    """构建文档正文加密 Fernet。密钥来源 DOC_ATREST_KEY 或从 AI_ENC_KEY 派生（独立 HKDF 域）。"""
    global _doc_atrest_cipher, _doc_atrest_current_key_material
    if _doc_atrest_cipher is not None:
        return _doc_atrest_cipher
    mat = DOC_ATREST_KEY or AI_ENC_KEY
    if not mat:
        return None
    _doc_atrest_cipher = _build_atrest_fernet(mat)
    _doc_atrest_current_key_material = mat
    return _doc_atrest_cipher


def _doc_atrest_encrypt(plaintext: str) -> str:
    """加密文档正文。未启用/空内容则原样返回（保持向后兼容与索引可用）。"""
    if not DOC_ATREST_ENCRYPTION or not plaintext:
        return plaintext
    cipher = _doc_atrest_build_cipher()
    if cipher is None:
        return plaintext
    try:
        return _ATREST_PREFIX + cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")
    except Exception as e:
        logger.error("文档正文加密失败（回退明文落库）：%s", e)
        return plaintext


def _doc_atrest_decrypt(stored: str) -> str:
    """解密文档正文。无 atrestv1: 前缀（明文/旧数据/未启用）则原样返回。
    先试当前密钥，再试历史密钥（轮换后漏网行回退）。"""
    if not stored or not isinstance(stored, str) or not stored.startswith(_ATREST_PREFIX):
        return stored
    body = stored[len(_ATREST_PREFIX):]
    # 先当前后历史：新写入/已重加密行用当前；漏网旧行用历史回退
    candidates = [_doc_atrest_cipher] + list(_doc_atrest_old_ciphers) if _doc_atrest_cipher is not None else list(_doc_atrest_old_ciphers)
    for cipher in candidates:
        if cipher is None:
            continue
        try:
            return cipher.decrypt(body.encode("ascii")).decode("utf-8")
        except Exception:
            continue
    logger.error("文档正文解密失败：当前与历史密钥均无法解密（密钥可能已彻底下线或数据损坏）")
    return ""


async def _rotate_doc_atrest_master(new_key: str) -> dict:
    """P1-5 at-rest 主密钥轮换：旧 current 入历史 → 新密钥成为 current →
    sweep 全库 atrestv1 密文（用旧密钥解密 → 用新密钥重加密）→ 切换。
    返回重加密行数与新密钥 kid（kid 非敏感，可回传运维对齐）。"""
    global _doc_atrest_cipher, _doc_atrest_old_ciphers, _doc_atrest_current_key_material
    if not new_key or len(new_key) < 16:
        raise HTTPException(400, "new_key 过短（需 ≥16 字符）")
    # 确保当前 cipher 已惰性构建（基于 env 的旧密钥），再将其提升为历史
    old_current = _doc_atrest_build_cipher()
    history = list(_doc_atrest_old_ciphers)
    if old_current is not None:
        history = [old_current, *history]
    new_cipher = _build_atrest_fernet(new_key)
    # 先切换 current → 新写入即用新密钥；sweep 用 history（旧）解密漏网旧密文
    _doc_atrest_cipher = new_cipher
    _doc_atrest_old_ciphers = history
    _doc_atrest_current_key_material = new_key
    count = await _sweep_reencrypt_atrest(history, new_cipher)
    return {"scope": "atrest", "rotated": True, "reencrypted_rows": count,
            "kid_new": _atrest_kid(new_key), "atrest_enabled": bool(DOC_ATREST_ENCRYPTION)}


# at-rest 密文落库的表/列（含主键列），sweep 按此遍历重加密
_ATREST_TABLES = [
    ("documents", "content", "doc_id"),
    ("doc_versions", "content", "id"),
    ("doc_branches", "base_content", "branch_id"),
    ("doc_branches", "head_content", "branch_id"),
]


def _reencrypt_atrest_cell(stored, decrypt_ciphers, new_cipher):
    """单格重加密：atrestv1 密文 → 用旧密钥解密 → 用新密钥重加密。非密文/解不动 → None。"""
    if not stored or not isinstance(stored, str) or not stored.startswith(_ATREST_PREFIX):
        return None
    body = stored[len(_ATREST_PREFIX):]
    plain = None
    for c in decrypt_ciphers:
        if c is None:
            continue
        try:
            plain = c.decrypt(body.encode("ascii")).decode("utf-8")
            break
        except Exception:
            continue
    if plain is None:
        return None  # 旧密钥均无法解密 → 跳过（已在 _doc_atrest_decrypt 记日志）
    return _ATREST_PREFIX + new_cipher.encrypt(plain.encode("utf-8")).decode("ascii")


async def _sweep_reencrypt_atrest(decrypt_ciphers, new_cipher) -> int:
    """遍历所有文档库的 atrestv1 密文并重加密为新密钥。SQLite 逐用户库 + PG 共享表两路。"""
    from pg_adapter import is_pg
    count = 0
    if is_pg():
        from pg_adapter import acquire_conn, release_conn
        conn = await acquire_conn()
        try:
            for tbl, col, pk in _ATREST_TABLES:
                try:
                    rows = await conn.fetch(
                        f'SELECT {pk} AS pk, {col} AS c FROM {tbl} WHERE {col} LIKE $1',
                        f"{_ATREST_PREFIX}%",
                    )
                except Exception:
                    continue  # 表/列不存在（未迁移）→ 跳过
                for r in rows:
                    nv = _reencrypt_atrest_cell(r["c"], decrypt_ciphers, new_cipher)
                    if nv is not None:
                        await conn.execute(
                            f"UPDATE {tbl} SET {col}=$1 WHERE {pk}=$2", nv, r["pk"]
                        )
                        count += 1
        finally:
            await release_conn(conn)
        return count
    # SQLite 模式：逐用户库 + _unowned
    users_dir = _data_dir() / "users"
    paths = list(users_dir.glob("*/docs.db")) if users_dir.exists() else []
    unowned = users_dir / "_unowned" / "docs.db"
    if unowned.exists():
        paths.append(unowned)
    for udb_path in paths:
        uid = udb_path.parent.name
        try:
            async with _db_transaction(uid) as db:
                for tbl, col, pk in _ATREST_TABLES:
                    try:
                        cur = await db.execute(
                            f"SELECT {pk} AS pk, {col} AS c FROM {tbl} WHERE {col} LIKE ?",
                            (f"{_ATREST_PREFIX}%",),
                        )
                        rows = await cur.fetchall()
                    except sqlite3.OperationalError:
                        continue  # 表/列不存在（旧库）→ 跳过
                    for r in rows:
                        nv = _reencrypt_atrest_cell(r["c"], decrypt_ciphers, new_cipher)
                        if nv is not None:
                            await db.execute(
                                f"UPDATE {tbl} SET {col}=? WHERE {pk}=?",
                                (nv, r["pk"]),
                            )
                            count += 1
        except Exception as e:
            logger.warning("at-rest 轮换 sweep 用户库 %s 异常：%s", uid, e)
    return count



def _compute_doc_etag(version: int, title: str, plain_content: str) -> str:
    """文档级乐观锁 ETag：基于版本号 + 标题 + 明文正文的 sha256（与静态加密无关，密钥轮换后稳定）。
    用于 PUT If-Match 并发控制：客户端 GET 时拿到 etag，PUT 回写时携带 If-Match，失配返回 409。"""
    h = hashlib.sha256()
    h.update(f"{version}\x00{title or ''}\x00{plain_content or ''}".encode("utf-8"))
    return h.hexdigest()


async def _apply_ai_configs_schema(db):
    """建 ai_configs + ai_conversations 表（每用户库内）。"""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS ai_configs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            api_url TEXT NOT NULL,
            model TEXT NOT NULL,
            enc_key TEXT NOT NULL DEFAULT '',
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # AI 对话历史：messages 以 JSON 文本存（与每用户库同库，物理隔离于各用户）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS ai_conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            messages_json TEXT NOT NULL DEFAULT '[]',
            msg_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            parent_id TEXT,
            fork_at_msg_index INTEGER
        )
    """)
    try:
        await db.execute("ALTER TABLE ai_conversations ADD COLUMN parent_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE ai_conversations ADD COLUMN fork_at_msg_index INTEGER")
    except sqlite3.OperationalError:
        pass
    await db.execute("CREATE INDEX IF NOT EXISTS idx_ai_conv_updated ON ai_conversations(updated_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_ai_conv_parent ON ai_conversations(parent_id)")
    await db.commit()


async def _apply_team_doc_acl_schema(db):
    """建 team_doc_acl 表（仅团队库）：文档级细粒度授权。
    当某团队文档存在 ACL 行时，读写按 ACL 门禁（owner/admin 旁路）；无 ACL 回退 membership+role。"""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS team_doc_acl (
            doc_id TEXT NOT NULL,
            grantee_user_id TEXT NOT NULL,
            permission TEXT NOT NULL,
            granted_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (doc_id, grantee_user_id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_team_doc_acl_doc ON team_doc_acl(doc_id)")
    try:
        await db.commit()
    except Exception:
        pass


async def _team_doc_acl_check(team_id: str, doc_id: str, user_id: str, need: str) -> str | None:
    """团队文档级 ACL 判定。
    返回：
      'bypass'  —— 用户是 owner/admin，旁路 ACL（治理角色始终可访问）
      'allow'   —— ACL 存在且用户被授予所需权限
      'deny'    —— ACL 存在但用户无所需权限
      None      —— 该文档无 ACL 行，回退调用方的 membership+role 逻辑
    need: 'read' 或 'write'。"""
    # owner/admin 旁路
    role = await _team_member_role(team_id, user_id)
    if role and role in ("owner", "admin"):
        return "bypass"
    async with _team_db_transaction(team_id) as db:
        rows = await (await db.execute(
            "SELECT grantee_user_id, permission FROM team_doc_acl WHERE doc_id=?", (doc_id,)
        )).fetchall()
    if not rows:
        return None  # 无 ACL → 回退 membership+role
    # 该文档受 ACL 管控：只看用户是否被显式授权
    for r in rows:
        if r["grantee_user_id"] != user_id:
            continue
        p = r["permission"]
        if need == "read" and p in ("read", "write"):
            return "allow"
        if need == "write" and p == "write":
            return "allow"
    return "deny"



async def _migrate_legacy_ai_configs(user_id: str):
    """一次性迁移：把旧 settings 文件里明文 ai-configs 导入加密表，并从 settings 清除 key 字段。"""
    async with _db_transaction(user_id) as db:
        cnt = (await (await db.execute("SELECT COUNT(*) AS c FROM ai_configs")).fetchone())["c"]
        if cnt > 0:
            return  # 已有配置，不迁移
    p = _config_path(user_id)
    if not p.exists():
        return
    try:
        raw = json.loads(p.read_text(encoding="utf-8") or "{}")
    except Exception:
        return
    legacy = raw.get("ai-configs")
    if not isinstance(legacy, list) or not legacy:
        return
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        for c in legacy:
            if not isinstance(c, dict):
                continue
            cid = c.get("id") or ("cfg-" + secrets.token_urlsafe(8))
            name = c.get("name") or t_default_name()
            api_url = c.get("apiUrl") or c.get("api_url") or "https://api.openai.com/v1/chat/completions"
            model = c.get("model") or "gpt-4o-mini"
            enc = _ai_encrypt(c.get("apiKey") or c.get("api_key") or "")
            await db.execute(
                "INSERT OR IGNORE INTO ai_configs (id, name, api_url, model, enc_key, usage_count, created_at, updated_at) VALUES (?,?,?,?,?,0,?,?)",
                (cid, name, api_url, model, enc, now, now),
            )
    # 从 settings 文件清除含 key 的字段（避免明文残留）
    for k in ("ai-configs", "ai-api-key", "ai-model"):
        raw.pop(k, None)
    try:
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(p))
    except Exception as e:
        logger.warning("清除旧 ai 配置明文失败 user=%s: %s", user_id, e)


def t_default_name():
    return "默认"


async def _init_registry_db():
    """初始化共享注册库：users + shares 路由表 + teams/team_members/audit_log。"""
    _ensure_parent(REGISTRY_DB_PATH)
    db = await aiosqlite.connect(REGISTRY_DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
    """)
    # 兼容旧库补 is_admin 列
    try:
        await db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # 企业 SSO：OIDC subject（唯一可空），首次 SSO 登录据此关联/创建本地用户
    try:
        await db.execute("ALTER TABLE users ADD COLUMN oidc_sub TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oidc_sub ON users(oidc_sub) WHERE oidc_sub IS NOT NULL")
    except sqlite3.OperationalError:
        pass
    # SAML 2.0 SP：NameID 关联本地用户（唯一可空）
    try:
        await db.execute("ALTER TABLE users ADD COLUMN saml_sub TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_saml_sub ON users(saml_sub) WHERE saml_sub IS NOT NULL")
    except sqlite3.OperationalError:
        pass
    # 2FA：TOTP secret（base32，加密存；空=未启用 2FA）
    try:
        await db.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")
    except sqlite3.OperationalError:
        pass
    # Guest 账号标记（非团队成员，仅访问被 ACL 授权的文档）
    try:
        await db.execute("ALTER TABLE users ADD COLUMN is_guest INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Guest 邮箱 + 邀请令牌
    try:
        await db.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass
    # 邀请令牌表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS guest_invites (
            token TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            guest_username TEXT NOT NULL,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            accepted_at TEXT
        )
    """)
    # Webhook 通知：外部系统回调
    await db.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            team_id TEXT,
            url TEXT NOT NULL,
            events TEXT NOT NULL DEFAULT '*',
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id)")
    # P1-6 外部通知渠道：channel_type(generic/slack/teams) + secret(HMAC 签名)
    try:
        await db.execute("ALTER TABLE webhooks ADD COLUMN channel_type TEXT NOT NULL DEFAULT 'generic'")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE webhooks ADD COLUMN secret TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_team ON webhooks(team_id)")
    except sqlite3.OperationalError:
        pass
    await db.execute("""
        CREATE TABLE IF NOT EXISTS shares (
            share_code TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_shares_owner ON shares(owner_user_id)")
    # 团队文档分享路由：team_id 非空表示该分享码指向团队库（否则回退属主个人库）
    try:
        await db.execute("ALTER TABLE shares ADD COLUMN team_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_shares_team ON shares(team_id)")
    except sqlite3.OperationalError:
        pass
    # P1-5 ACL 感知搜索索引：镜像 per-user doc_acl 授权，使被授权用户的全局搜索可命中
    # 属主库中的文档（per-user 库相互隔离，否则被授权方搜不到授予自己的文档）。
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_grants (
            doc_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            grantee_user_id TEXT NOT NULL,
            permission TEXT NOT NULL,
            granted_at TEXT NOT NULL,
            expires_at TEXT,
            PRIMARY KEY (doc_id, grantee_user_id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_grants_grantee ON doc_grants(grantee_user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_grants_owner ON doc_grants(owner_user_id)")
    # 协同编辑态持久化：room → 最新 Yjs 快照（BLOB，base64 存储为 TEXT）。
    # 客户端周期性提交全量快照（encodeStateAsUpdate），服务端只存最新一份；
    # 增量更新仅实时中继（内存 + Redis 跨实例），不落库（由下一份快照覆盖）。
    await db.execute("""
        CREATE TABLE IF NOT EXISTS collab_state (
            room TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # C1：Yjs 增量更新落库 + 定期合并/GC。快照为全量基线，增量按 seq 顺序在快照之上 apply。
    # 客户端提交全量快照时清空该 room 的增量（快照已包含全部状态）。
    await db.execute("""
        CREATE TABLE IF NOT EXISTS collab_updates (
            room TEXT NOT NULL,
            seq INTEGER NOT NULL,
            data BLOB NOT NULL,
            ts TEXT NOT NULL,
            PRIMARY KEY (room, seq)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_collab_updates_room ON collab_updates(room)")
    # 团队：owner_user_id 为创建者；slug 唯一可空
    await db.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT,
            owner_user_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # 团队成员：role ∈ owner/admin/member/viewer
    await db.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            team_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TEXT NOT NULL,
            PRIMARY KEY (team_id, user_id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tm_user ON team_members(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tm_team ON team_members(team_id)")
    # 团队自定义角色 + 权限矩阵：permissions_json 为权限 key 集合（JSON 数组）。
    # 内建角色（viewer/member/admin/owner）也会在此表占位，便于团队按需调整矩阵。
    await db.execute("""
        CREATE TABLE IF NOT EXISTS team_roles (
            team_id TEXT NOT NULL,
            role TEXT NOT NULL,
            permissions_json TEXT NOT NULL DEFAULT '[]',
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            PRIMARY KEY (team_id, role)
        )
    """)
    # 审计日志：跨团队/全局，含 hash 链防篡改
    await db.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            user_id TEXT,
            team_id TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            detail TEXT,
            prev_hash TEXT,
            record_hash TEXT
        )
    """)
    # 兼容旧库补 hash 列
    try:
        await db.execute("ALTER TABLE audit_log ADD COLUMN prev_hash TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE audit_log ADD COLUMN record_hash TEXT")
    except sqlite3.OperationalError:
        pass
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_team ON audit_log(team_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
    # 物理不可变（WORM）：开启后拦截任何 UPDATE/DELETE（含留存期清理与 re-anchor），
    # 满足 SOX/GDPR/等保/21 CFR Part 11 的"写一次读多次"要求。链式哈希链永不断裂。
    if AUDIT_IMMUTABLE:
        await db.execute(
            "CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log "
            "BEGIN SELECT RAISE(ABORT, 'audit_log 不可变（AUDIT_IMMUTABLE=1）：禁止 UPDATE'); END")
        await db.execute(
            "CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log "
            "BEGIN SELECT RAISE(ABORT, 'audit_log 不可变（AUDIT_IMMUTABLE=1）：禁止 DELETE'); END")
    # 通知：分享被访问/被 @mention/评审请求等
    await db.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            detail TEXT,
            link TEXT,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read)")
    # 文档评审流：pending/approved/rejected
    await db.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            team_id TEXT,
            requester_user_id TEXT NOT NULL,
            reviewer_user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            comment TEXT,
            created_at TEXT NOT NULL,
            decided_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON reviews(reviewer_user_id, status)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_reviews_requester ON reviews(requester_user_id)")
    # 多级审批步骤：每个 review 可有多个有序步骤（串行或并行审批）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS review_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            step INTEGER NOT NULL,
            reviewer_user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            comment TEXT,
            decided_at TEXT,
            mode TEXT NOT NULL DEFAULT 'serial',
            FOREIGN KEY (review_id) REFERENCES reviews(id)
        )
    """)
    try:
        await db.execute("ALTER TABLE review_steps ADD COLUMN mode TEXT NOT NULL DEFAULT 'serial'")
    except sqlite3.OperationalError:
        pass
    # stage 列：标记该步骤所属阶段（工作流多阶段 SLA/升级用）
    try:
        await db.execute("ALTER TABLE review_steps ADD COLUMN stage INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    await db.execute("CREATE INDEX IF NOT EXISTS idx_review_steps_review ON review_steps(review_id)")
    # 通用工作流定义：可配置多阶段审批流程（每阶段独立串行/并行）
    # definition_json: {"steps":[{"reviewers":["u1","u2"],"mode":"parallel"},{"reviewers":["u3"],"mode":"serial"}]}
    await db.execute("""
        CREATE TABLE IF NOT EXISTS workflow_definitions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            team_id TEXT,
            definition_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wfd_team ON workflow_definitions(team_id)")
    # 工作流实例：文档跑某个工作流的运行实例（关联 review）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS workflow_instances (
            id TEXT PRIMARY KEY,
            workflow_def_id TEXT NOT NULL,
            review_id INTEGER,
            doc_id TEXT NOT NULL,
            team_id TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wfi_doc ON workflow_instances(doc_id)")
    # 工作流 SLA：每阶段的截止时间与升级状态（超时自动提醒/转派 escalate_to）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS workflow_sla (
            instance_id TEXT NOT NULL,
            stage INTEGER NOT NULL,
            deadline TEXT NOT NULL,
            escalated INTEGER NOT NULL DEFAULT 0,
            escalated_at TEXT,
            PRIMARY KEY (instance_id, stage)
        )
    """)
    # API Token：用于 REST 自动化（同 Bearer 头；存储哈希，明文仅创建时返回一次）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            token_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)")
    # 已撤销的会话 token（SLO/登出用）：HMAC token 无状态，靠服务端吊销名单失效
    await db.execute("""
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            revoked_at TEXT NOT NULL,
            expires_at TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_revoked_user ON revoked_tokens(user_id)")
    # 会话管理：活跃登录会话追踪
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL,
            last_active TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    # Refresh Token：access 短 TTL + refresh 长 TTL，支持轮换（rotated_from 记录来源）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            rotated_from TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_refresh_hash ON refresh_tokens(token_hash)")
    # 多租户：组织（organization）层隔离。users.org_id / teams.org_id 可空（向后兼容）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            org_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_orgs_slug ON organizations(slug)")
    try:
        await db.execute("ALTER TABLE users ADD COLUMN org_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE teams ADD COLUMN org_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(org_id)")
    except sqlite3.OperationalError:
        pass
    # org_id 维度补齐（audit_log/team_members/notifications），供 RLS/跨组织过滤用
    for _t in ("audit_log", "team_members", "notifications"):
        try:
            await db.execute(f"ALTER TABLE {_t} ADD COLUMN org_id TEXT")
        except sqlite3.OperationalError:
            pass
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_org ON audit_log(org_id)")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tm_org ON team_members(org_id)")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_notif_org ON notifications(org_id)")
    except sqlite3.OperationalError:
        pass
    # 用户展示信息 + 激活态（SCIM @mention/avatar 用）
    try:
        await db.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    # 数据驻留分区：记录用户/团队文档库所在 region
    try:
        await db.execute("ALTER TABLE users ADD COLUMN residency_region TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        await db.execute("ALTER TABLE teams ADD COLUMN residency_region TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    # SCIM 2.0：组（企业 IdP 同步用户/组）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS scim_groups (
            group_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            org_id TEXT,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS scim_group_members (
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            PRIMARY KEY (group_id, user_id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_scim_members_user ON scim_group_members(user_id)")
    # 保存搜索 / 搜索订阅
    await db.execute("""
        CREATE TABLE IF NOT EXISTS saved_searches (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            query TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_id)")
    # 多语言文档变体关联组
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_variants (
            group_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            lang TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            PRIMARY KEY (group_id, lang)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_variants_doc ON doc_variants(doc_id)")
    # 文档模板：个人(team_id=NULL) / 团队(team_id 有值)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            team_id TEXT,
            name TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_templates_team ON templates(team_id)")
    # E6：模板场景类型（rfc/design-doc/runbook/adr...）与变量定义（变量名列表 JSON）
    try:
        await db.execute("ALTER TABLE templates ADD COLUMN kind TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE templates ADD COLUMN variables_json TEXT NOT NULL DEFAULT '[]'")
    except Exception:
        pass
    # P2-11 模板治理：版本号、状态机、继承、受管标志、版本历史
    for _col_ddl in (
        "ALTER TABLE templates ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE templates ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
        "ALTER TABLE templates ADD COLUMN parent_id TEXT",
        "ALTER TABLE templates ADD COLUMN org_managed INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE templates ADD COLUMN updated_by TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE templates ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''",
    ):
        try:
            await db.execute(_col_ddl)
        except Exception:
            pass
    await db.execute("""
        CREATE TABLE IF NOT EXISTS template_versions (
            id TEXT PRIMARY KEY,
            template_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            name TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT '',
            variables_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'active',
            changed_by TEXT NOT NULL,
            changed_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_tplver_tpl ON template_versions(template_id, version)")
    # OAuth2 开放 API：第三方应用（客户端）注册 + 授权码 + 访问令牌作用域
    await db.execute("""
        CREATE TABLE IF NOT EXISTS oauth_clients (
            client_id TEXT PRIMARY KEY,
            client_secret_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            redirect_uris TEXT NOT NULL DEFAULT '',
            scopes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS oauth_codes (
            code TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_oauth_codes_client ON oauth_codes(client_id)")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS oauth_token_scopes (
            token_hash TEXT PRIMARY KEY,
            client_id TEXT,
            scope TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    # AI 用量计费/配额：按 用户+团队+日 计数（team_id 为空表示个人空间）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS ai_usage (
            user_id TEXT NOT NULL,
            team_id TEXT,
            day TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, team_id, day)
        )
    """)
    # E1：文档/团队 ↔ Git 仓库双向绑定（token 加密存储，明文不落库/不回传）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_git_repos (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            repo_url TEXT NOT NULL,
            branch TEXT NOT NULL DEFAULT 'main',
            file_path TEXT NOT NULL DEFAULT '',
            auth_token_enc TEXT NOT NULL DEFAULT '',
            last_commit TEXT,
            auto_publish INTEGER NOT NULL DEFAULT 0,
            webhook_secret TEXT NOT NULL DEFAULT '',
            owner_user_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_git_scope ON doc_git_repos(scope, scope_id)")
    for _col in ("webhook_secret", "owner_user_id"):
        try:
            await db.execute(f"ALTER TABLE doc_git_repos ADD COLUMN {_col} TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass
    # E3：文档集 release（打包多文档的版本指针快照）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doc_releases (
            release_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '1.0',
            manifest TEXT NOT NULL DEFAULT '[]',
            frozen INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # 法务保留（legal hold）：按 user/team/global 范围冻结文档删除与版本清理
    await db.execute("""
        CREATE TABLE IF NOT EXISTS legal_holds (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            scope_id TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL,
            held_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            released_at TEXT,
            released_by TEXT
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_legal_holds_scope ON legal_holds(scope, scope_id, released_at)")
    # 后台任务 leader 选举租约（单行 id=1；holder=instance_id，expires_at 过期则可抢占）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS leader_lease (
            id INTEGER PRIMARY KEY DEFAULT 1,
            holder TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)
    await db.commit()
    return db


