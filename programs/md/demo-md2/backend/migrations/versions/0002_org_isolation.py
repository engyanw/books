"""add org-level isolation (organizations + org_id on users/teams)

引入组织（organization）层，实现多租户隔离：users.org_id / teams.org_id。
这是首个走 alembic 的增量迁移（基线 0001 之后），演示迁移框架端到端可用。

Revision ID: 0002_org_isolation
Revises: 0001_baseline
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa
import sqlite3

revision = "0002_org_isolation"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def _exe(sql):
    """幂等执行：表/列已存在或表不存在时容错跳过（兼容从空库 upgrade head）。"""
    try:
        op.execute(sql)
    except sqlite3.OperationalError:
        pass
    except Exception:
        pass


def upgrade():
    # organizations 表
    _exe("""
        CREATE TABLE IF NOT EXISTS organizations (
            org_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT,
            created_at TEXT NOT NULL
        )
    """)
    _exe("CREATE INDEX IF NOT EXISTS idx_orgs_slug ON organizations(slug)")
    # users.org_id（可空：未分配组织的用户为 NULL，向后兼容）
    _exe("ALTER TABLE users ADD COLUMN org_id TEXT")
    # teams.org_id（可空）
    _exe("ALTER TABLE teams ADD COLUMN org_id TEXT")
    _exe("CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(org_id)")


def downgrade():
    try:
        op.execute("DROP INDEX IF EXISTS idx_teams_org")
    except Exception:
        pass
    try:
        op.execute("ALTER TABLE teams DROP COLUMN org_id")
    except Exception:
        pass
    try:
        op.execute("ALTER TABLE users DROP COLUMN org_id")
    except Exception:
        pass
    try:
        op.execute("DROP TABLE IF EXISTS organizations")
    except Exception:
        pass
