"""Alembic env.py：根据 DATABASE_URL（PostgreSQL）或 REGISTRY_DB_PATH（SQLite）连接。

支持异步（asyncpg）与同步（sqlite3/sqlalchemy）两种驱动。本项目的 schema 主要由
应用启动时的幂等 DDL（_apply_documents_schema / _init_registry_db）维护；alembic
用于版本化增量变更（新增列/表/索引），基线已 stamp 到当前状态。
"""
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# 让 alembic 能 import config / pg_adapter
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
REGISTRY_DB_PATH = os.environ.get("REGISTRY_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "registry.db"))

target_metadata = None  # 无 ORM 模型，不做 autogenerate


def _sync_sqlite_url():
    # asyncpg 用 asyncpg，但离线/同步渲染用 sqlite3 驱动
    return f"sqlite:///{REGISTRY_DB_PATH}"


def run_migrations_offline():
    """离线模式：生成 SQL 脚本。"""
    if DATABASE_URL:
        url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
    else:
        url = _sync_sqlite_url()
    context.configure(url=url, literal_binds=True, dialect_name="postgresql" if DATABASE_URL else "sqlite")
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        dialect_name="postgresql" if DATABASE_URL else "sqlite",
        compare_type=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online_sync():
    """同步在线模式（SQLite 用 sqlalchemy）。"""
    from sqlalchemy import create_engine
    url = _sync_sqlite_url()
    engine = create_engine(url, future=True)
    with engine.connect() as conn:
        do_run_migrations(conn)
    engine.dispose()


async def run_migrations_online_async():
    """异步在线模式（PostgreSQL 用 asyncpg）。"""
    import asyncpg
    dsn = DATABASE_URL
    # 简化：用 sqlalchemy + psycopg2 同步驱动跑 PG 迁移更稳，这里回退同步
    from sqlalchemy import create_engine
    url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            do_run_migrations(conn)
        engine.dispose()
    except Exception as e:
        raise RuntimeError(f"PG 迁移连接失败（需 psycopg2-binary）: {e}") from e


if context.is_offline_mode():
    run_migrations_offline()
else:
    if DATABASE_URL:
        try:
            run_migrations_online_async()
        except Exception:
            # 无 psycopg2 时尝试 asyncpg 直连（不走 sqlalchemy，仅记录）
            raise
    else:
        run_migrations_online_sync()
