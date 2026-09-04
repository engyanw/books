"""baseline: stamp current schema.

当前 registry/documents schema 由应用启动时的幂等 DDL 维护
(_init_registry_db / _apply_documents_schema，CREATE TABLE IF NOT EXISTS +
ALTER TABLE ADD COLUMN)。本迁移作为基线 stamp：既有库用 `alembic stamp head`
标记到此版本，后续增量变更走 alembic 迁移（见 0002+）。

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-14
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 基线：不做实际 DDL（schema 已由应用幂等建表覆盖）。
    # 新部署应先启动一次后端让其建表，再 `alembic stamp head` 标记基线。
    pass


def downgrade():
    pass
