"""
PostgreSQL 迁移适配层：当 DATABASE_URL 配置时提供 PG 连接池 + 统一查询接口。
不配置时自动回退到现有 SQLite per-user 架构（零改动）。

核心设计：PGConnection / PGCursor 提供与 aiosqlite.Connection / Cursor 兼容的
execute()/fetchone()/fetchall()/lastrowid 接口，使 main.py 中 560+ 处
`await (await db.execute("... WHERE id=?", (pid,))).fetchone()` 模式在 PG 下零改动可用。

迁移指南见 DEPLOY_MULTI_TEAM.md "PostgreSQL 迁移补充细节"。
"""
import os
import re
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger("sandbox-proxy")

try:
    import asyncpg
    import asyncpg.exceptions as _apg_exc
    _asyncpg_available = True
except ImportError:
    asyncpg = None
    _apg_exc = None
    _asyncpg_available = False

from config import DATABASE_URL, DB_POOL_MIN, DB_POOL_MAX


def _translate(exc: Exception) -> Exception:
    """把 asyncpg 异常翻译为 sqlite3 等价，使上层 `except sqlite3.IntegrityError/
    OperationalError` 零改动复用（如 auth_register 的 409 占名检测、ALTER 幂等等）。"""
    if _apg_exc is None or not isinstance(exc, _apg_exc.PostgresError):
        return exc
    if isinstance(exc, (
        _apg_exc.UniqueViolationError, _apg_exc.ForeignKeyViolationError,
        _apg_exc.NotNullViolationError, _apg_exc.CheckViolationError,
        _apg_exc.ExclusionViolationError,
    )):
        return sqlite3.IntegrityError(str(exc))
    return sqlite3.OperationalError(str(exc))


_pg_pool = None
_use_pg = bool(DATABASE_URL) and _asyncpg_available


async def init_pg_pool():
    """初始化 PostgreSQL 连接池（仅 DATABASE_URL 配置时）。"""
    global _pg_pool
    if not _use_pg or _pg_pool:
        return
    _pg_pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=DB_POOL_MIN, max_size=DB_POOL_MAX,
        command_timeout=30, statement_cache_size=100,
    )
    logger.info("PostgreSQL 连接池已初始化 (%s-%s)", DB_POOL_MIN, DB_POOL_MAX)


async def close_pg_pool():
    """关闭 PG 连接池。"""
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None


def is_pg() -> bool:
    """是否使用 PostgreSQL。"""
    return _use_pg and _pg_pool is not None


# ==================== 连接池访问（避免 main 里 `from pg_adapter import _pg_pool` 的陈旧绑定） ====================
async def acquire_conn():
    """从 PG 池获取一条裸 asyncpg.Connection。"""
    return await _pg_pool.acquire()


async def release_conn(conn):
    """归还一条裸 asyncpg.Connection 到 PG 池。"""
    await _pg_pool.release(conn)


# ==================== SQL 方言转换 ====================
def convert_sql(sql: str) -> str:
    """将 SQLite 语法转换为 PG 兼容：

    1. `?` 占位符 → `$1/$2/...`
    2. `INSERT OR IGNORE INTO` → `INSERT INTO`（由调用方/此处补 `ON CONFLICT DO NOTHING`）
    3. `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGSERIAL PRIMARY KEY`
    4. `INSERT OR REPLACE INTO` → `INSERT INTO`（冲突覆盖语义由 ON CONFLICT DO UPDATE 处理，较少见；此处降级为 DO NOTHING）
    注意：不处理字符串字面量内的 `?`（SQLite 模式下亦不以此区分），符合现有用法。
    """
    if sql is None:
        return sql
    out = sql

    # 3. AUTOINCREMENT（CREATE TABLE 内）
    out = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "BIGSERIAL PRIMARY KEY",
        out,
        flags=re.IGNORECASE,
    )

    # 2. INSERT OR IGNORE / INSERT OR REPLACE → ON CONFLICT DO NOTHING
    conflict_append = False
    if re.search(r"INSERT\s+OR\s+IGNORE\s+INTO", out, flags=re.IGNORECASE) or \
       re.search(r"INSERT\s+OR\s+REPLACE\s+INTO", out, flags=re.IGNORECASE):
        out = re.sub(r"INSERT\s+OR\s+(?:IGNORE|REPLACE)\s+INTO", "INSERT INTO", out, flags=re.IGNORECASE)
        conflict_append = True

    # 1. ? → $N
    n = [0]

    def _ph(_m):
        n[0] += 1
        return f"${n[0]}"
    out = re.sub(r"\?", _ph, out)

    if conflict_append and "ON CONFLICT" not in out.upper():
        out = out.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    return out


# ==================== PG 适配器：统一 Row 接口 ====================
class PGRow:
    """包装 asyncpg.Record，提供与 aiosqlite.Row 兼容的 __getitem__ 接口。"""
    def __init__(self, record):
        self._record = record

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._record[key]
        return self._record[key]

    def keys(self):
        return dict(self._record).keys() if self._record else []

    def get(self, key, default=None):
        d = dict(self._record) if self._record else {}
        return d.get(key, default)


class PGCursor:
    """模拟 aiosqlite.Cursor：execute 后缓冲结果，fetchone/fetchall 依次取出。

    语义对齐 aiosqlite：
    - execute(SELECT/WITH/VALUES 或含 RETURNING) → 立即 fetch 全部行入缓冲（内存换简单）
    - execute(INSERT/UPDATE/DELETE/CREATE/ALTER) → conn.execute 立即执行返回状态；无行缓冲
    - lastrowid：INSERT...RETURNING id 时取回 id（兼容 SQLite AUTOINCREMENT lastrowid 用法）
    """
    def __init__(self, conn: "PGConnection"):
        self._conn = conn
        self._rows = None      # list[PGRow] | None（None=非查询语句）
        self._status = None
        self._lastrowid = None
        self._rowcount = -1

    async def _run(self, sql, params):
        sql_pg = convert_sql(sql)
        upper = sql_pg.lstrip().upper()
        verb = upper.split(' ', 1)[0] if upper else ''
        is_query = verb in ('SELECT', 'WITH', 'VALUES', 'PRAGMA') or 'RETURNING' in upper
        args = list(params) if params else []
        try:
            if is_query:
                rows = await self._conn._raw().fetch(sql_pg, *args)
                self._rows = [PGRow(r) for r in rows]
                # lastrowid 兼容：INSERT...RETURNING id
                if verb == 'INSERT' and self._rows:
                    try:
                        if 'id' in self._rows[0].keys():
                            self._lastrowid = self._rows[0]['id']
                    except Exception:
                        pass
                self._rowcount = len(self._rows)
            else:
                self._status = await self._conn._raw().execute(sql_pg, *args)
                # 解析 "INSERT 0 1" 行数
                try:
                    parts = str(self._status).split()
                    if len(parts) >= 3 and parts[1] in ('0',):
                        self._rowcount = int(parts[2])
                except Exception:
                    pass
        except Exception as e:
            # PRAGMA 等 SQLite 专有语句在 PG 下静默跳过（init 路径不依赖其结果）
            if verb == 'PRAGMA':
                self._rows = []
                self._rowcount = 0
                return
            # 翻译 asyncpg 错误为 sqlite3 等价（复用上层 except 分支）
            raise _translate(e) from e

    async def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)

    async def fetchall(self):
        if not self._rows:
            return []
        r = self._rows
        self._rows = []
        return r

    async def fetchmany(self, size=1):
        if not self._rows:
            return []
        r = self._rows[:size]
        self._rows = self._rows[size:]
        return r

    @property
    def lastrowid(self):
        return self._lastrowid

    @property
    def rowcount(self):
        return self._rowcount

    @property
    def description(self):
        return None

    async def close(self):
        self._rows = None


class PGConnection:
    """包装 asyncpg.Connection，提供与 aiosqlite.Connection 兼容的接口。

    - execute(sql, params=None) → PGCursor（立即执行；查询结果入缓冲）
    - executemany(sql, seq)     → asyncpg executemany
    - fetchone/fetchall         → 便捷直查（不经 cursor）
    - commit/rollback           → no-op（事务由 _registry_transaction/_db_transaction 的 db.transaction() 管理）
    - close                     → no-op（连接归还由 _put_*_db 处理）
    - row_factory               → 可读写 no-op（asyncpg 不需要）
    """
    def __init__(self, conn):
        self._conn = conn

    def _raw(self):
        return self._conn

    def transaction(self):
        """委托给裸 asyncpg.Connection 的事务上下文（供 _registry_transaction 等使用）。"""
        return self._conn.transaction()

    async def execute(self, sql, params=None):
        cur = PGCursor(self)
        await cur._run(sql, params)
        return cur

    async def executemany(self, sql, seq):
        sql_pg = convert_sql(sql)
        # asyncpg executemany 期望 [(...), ...]
        seq = [tuple(p) if not isinstance(p, tuple) else p for p in seq]
        await self._conn.executemany(sql_pg, seq)
        return None

    async def fetchone(self, sql, params=None):
        sql_pg = convert_sql(sql)
        args = list(params) if params else []
        row = await self._conn.fetchrow(sql_pg, *args)
        return PGRow(row) if row else None

    async def fetchall(self, sql, params=None):
        sql_pg = convert_sql(sql)
        args = list(params) if params else []
        rows = await self._conn.fetch(sql_pg, *args)
        return [PGRow(r) for r in rows]

    async def commit(self):
        # PG 模式下事务由 transaction() 上下文管理；此处 no-op
        return

    async def rollback(self):
        return

    async def close(self):
        # 连接生命周期由连接池管理
        return

    @property
    def row_factory(self):
        return None

    @row_factory.setter
    def row_factory(self, val):
        pass  # asyncpg 不需要 row_factory


async def pg_query_one(conn, sql, params=None):
    """执行查询返回单行（PGRow 兼容）。"""
    if params:
        row = await conn.fetchrow(sql, *params)
    else:
        row = await conn.fetchrow(sql)
    return PGRow(row) if row else None


async def pg_query_all(conn, sql, params=None):
    """执行查询返回多行（PGRow 列表）。"""
    if params:
        rows = await conn.fetch(sql, *params)
    else:
        rows = await conn.fetch(sql)
    return [PGRow(r) for r in rows]


# ==================== 兼容辅助 ====================
def wrap(conn) -> "PGConnection":
    """把裸 asyncpg.Connection 包装为 aiosqlite 兼容的 PGConnection。"""
    return PGConnection(conn)


def unwrap(db: "PGConnection"):
    """从 PGConnection 取回裸 asyncpg.Connection（归还池时用）。"""
    if isinstance(db, PGConnection):
        return db._conn
    return db
