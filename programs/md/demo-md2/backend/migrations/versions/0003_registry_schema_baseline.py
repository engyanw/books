"""registry schema baseline: 让 alembic 真正接管注册库表结构。

此前基线(0001)仅 stamp，schema 由应用运行时幂等 DDL(_init_registry_db)维护，
PG 模式下 SQLite 语法(AUTOINCREMENT)无法直接执行 → PG 部署的表结构其实未受控。
本迁移把全部注册库表的 DDL 纳入 alembic，方言感知(SQLite/PG 可移植)，
使得 `alembic upgrade head` 即可在全新库上构建完整 schema，后续变更走迁移脚本。

幂等：全部 CREATE TABLE IF NOT EXISTS；ALTER 列用 try/except 容错已存在。

Revision ID: 0003_registry_schema
Revises: 0002_org_isolation
Create Date: 2026-08-14
"""
from alembic import op
import sqlite3

revision = "0003_registry_schema"
down_revision = "0002_org_isolation"
branch_labels = None
depends_on = None


def _dialect():
    try:
        return op.get_bind().dialect.name
    except Exception:
        return "sqlite"


def _pk(name="id"):
    """自增主键：SQLite 用 AUTOINCREMENT，PG 用 BIGSERIAL。"""
    return f"{name} INTEGER PRIMARY KEY AUTOINCREMENT" if _dialect() == "sqlite" else f"{name} BIGSERIAL PRIMARY KEY"


def _exe(sql):
    try:
        op.execute(sql)
    except sqlite3.OperationalError:
        pass  # 列/表已存在等幂等容错（仅 SQLite）
    except Exception:
        # PG 下 CREATE IF NOT EXISTS 安全；ALTER 列已存在抛 DuplicateColumn → 忽略
        pass


def upgrade():
    _exe(f"""CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0
    )""")
    _exe("CREATE TABLE IF NOT EXISTS guest_invites (token TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, guest_username TEXT NOT NULL, email TEXT, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, accepted_at TEXT)")
    _exe("CREATE TABLE IF NOT EXISTS webhooks (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, team_id TEXT, url TEXT NOT NULL, events TEXT NOT NULL DEFAULT '*', created_at TEXT NOT NULL)")
    _exe("CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id)")
    _exe("CREATE TABLE IF NOT EXISTS shares (share_code TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, doc_id TEXT NOT NULL, created_at TEXT NOT NULL)")
    _exe("CREATE INDEX IF NOT EXISTS idx_shares_owner ON shares(owner_user_id)")
    _exe("CREATE TABLE IF NOT EXISTS collab_state (room TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT NOT NULL)")
    _exe("CREATE TABLE IF NOT EXISTS teams (team_id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT, owner_user_id TEXT NOT NULL, created_at TEXT NOT NULL)")
    _exe("CREATE TABLE IF NOT EXISTS team_members (team_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member', created_at TEXT NOT NULL, PRIMARY KEY (team_id, user_id))")
    _exe("CREATE INDEX IF NOT EXISTS idx_tm_user ON team_members(user_id)")
    _exe("CREATE INDEX IF NOT EXISTS idx_tm_team ON team_members(team_id)")
    _exe("CREATE TABLE IF NOT EXISTS team_roles (team_id TEXT NOT NULL, role TEXT NOT NULL, permissions_json TEXT NOT NULL DEFAULT '[]', is_default INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, PRIMARY KEY (team_id, role))")
    _exe(f"""CREATE TABLE IF NOT EXISTS audit_log (
        {_pk()},
        ts TEXT NOT NULL, user_id TEXT, team_id TEXT, action TEXT NOT NULL,
        target_type TEXT, target_id TEXT, detail TEXT, prev_hash TEXT, record_hash TEXT
    )""")
    _exe("CREATE INDEX IF NOT EXISTS idx_audit_team ON audit_log(team_id)")
    _exe("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
    _exe(f"""CREATE TABLE IF NOT EXISTS notifications (
        {_pk()},
        user_id TEXT NOT NULL, type TEXT NOT NULL, detail TEXT, link TEXT,
        is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
    )""")
    _exe("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read)")
    _exe(f"""CREATE TABLE IF NOT EXISTS reviews (
        {_pk()},
        doc_id TEXT NOT NULL, team_id TEXT, requester_user_id TEXT NOT NULL,
        reviewer_user_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        comment TEXT, created_at TEXT NOT NULL, decided_at TEXT
    )""")
    _exe("CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON reviews(reviewer_user_id, status)")
    _exe("CREATE INDEX IF NOT EXISTS idx_reviews_requester ON reviews(requester_user_id)")
    _exe(f"""CREATE TABLE IF NOT EXISTS review_steps (
        {_pk()},
        review_id INTEGER NOT NULL, step INTEGER NOT NULL, reviewer_user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', comment TEXT, decided_at TEXT,
        mode TEXT NOT NULL DEFAULT 'serial'
    )""")
    _exe("CREATE INDEX IF NOT EXISTS idx_review_steps_review ON review_steps(review_id)")
    _exe("CREATE TABLE IF NOT EXISTS workflow_definitions (id TEXT PRIMARY KEY, name TEXT NOT NULL, team_id TEXT, definition_json TEXT NOT NULL DEFAULT '{}', created_by TEXT NOT NULL, created_at TEXT NOT NULL)")
    _exe("CREATE INDEX IF NOT EXISTS idx_wfd_team ON workflow_definitions(team_id)")
    _exe("CREATE TABLE IF NOT EXISTS workflow_instances (id TEXT PRIMARY KEY, workflow_def_id TEXT NOT NULL, review_id INTEGER, doc_id TEXT NOT NULL, team_id TEXT, status TEXT NOT NULL DEFAULT 'running', created_at TEXT NOT NULL)")
    _exe("CREATE INDEX IF NOT EXISTS idx_wfi_doc ON workflow_instances(doc_id)")
    _exe("CREATE TABLE IF NOT EXISTS api_tokens (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', token_hash TEXT NOT NULL, created_at TEXT NOT NULL, last_used TEXT)")
    _exe("CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id)")
    _exe("CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)")
    _exe("CREATE TABLE IF NOT EXISTS revoked_tokens (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, revoked_at TEXT NOT NULL, expires_at TEXT)")
    _exe("CREATE INDEX IF NOT EXISTS idx_revoked_user ON revoked_tokens(user_id)")
    _exe("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, ip TEXT, user_agent TEXT, created_at TEXT NOT NULL, last_active TEXT NOT NULL)")
    _exe("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    _exe("CREATE TABLE IF NOT EXISTS organizations (org_id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT, created_at TEXT NOT NULL)")
    _exe("CREATE INDEX IF NOT EXISTS idx_orgs_slug ON organizations(slug)")
    _exe("CREATE TABLE IF NOT EXISTS saved_searches (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, query TEXT NOT NULL, created_at TEXT NOT NULL)")
    _exe("CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_id)")
    _exe("CREATE TABLE IF NOT EXISTS doc_variants (group_id TEXT NOT NULL, doc_id TEXT NOT NULL, lang TEXT NOT NULL, owner_user_id TEXT NOT NULL, PRIMARY KEY (group_id, lang))")
    _exe("CREATE INDEX IF NOT EXISTS idx_doc_variants_doc ON doc_variants(doc_id)")
    _exe("CREATE TABLE IF NOT EXISTS templates (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, team_id TEXT, name TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL, created_at TEXT NOT NULL)")
    _exe("CREATE INDEX IF NOT EXISTS idx_templates_team ON templates(team_id)")
    _exe("CREATE TABLE IF NOT EXISTS oauth_clients (client_id TEXT PRIMARY KEY, client_secret_hash TEXT NOT NULL, name TEXT NOT NULL, owner_user_id TEXT NOT NULL, redirect_uris TEXT NOT NULL DEFAULT '', scopes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
    _exe("CREATE TABLE IF NOT EXISTS oauth_codes (code TEXT PRIMARY KEY, client_id TEXT NOT NULL, user_id TEXT NOT NULL, redirect_uri TEXT NOT NULL, scope TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0)")
    _exe("CREATE INDEX IF NOT EXISTS idx_oauth_codes_client ON oauth_codes(client_id)")
    _exe("CREATE TABLE IF NOT EXISTS oauth_token_scopes (token_hash TEXT PRIMARY KEY, client_id TEXT, scope TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
    _exe("CREATE TABLE IF NOT EXISTS ai_usage (user_id TEXT NOT NULL, team_id TEXT, day TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, team_id, day))")
    # 补列（向后兼容旧库）：幂等 ALTER
    for col, ddl in [
        ("oidc_sub", "ALTER TABLE users ADD COLUMN oidc_sub TEXT"),
        ("saml_sub", "ALTER TABLE users ADD COLUMN saml_sub TEXT"),
        ("totp_secret", "ALTER TABLE users ADD COLUMN totp_secret TEXT"),
        ("is_guest", "ALTER TABLE users ADD COLUMN is_guest INTEGER NOT NULL DEFAULT 0"),
        ("email", "ALTER TABLE users ADD COLUMN email TEXT"),
        ("org_id_users", "ALTER TABLE users ADD COLUMN org_id TEXT"),
        ("org_id_teams", "ALTER TABLE teams ADD COLUMN org_id TEXT"),
        ("mode_rs", "ALTER TABLE review_steps ADD COLUMN mode TEXT NOT NULL DEFAULT 'serial'"),
        ("prev_hash", "ALTER TABLE audit_log ADD COLUMN prev_hash TEXT"),
        ("record_hash", "ALTER TABLE audit_log ADD COLUMN record_hash TEXT"),
    ]:
        _exe(ddl)
    _exe("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oidc_sub ON users(oidc_sub) WHERE oidc_sub IS NOT NULL")
    _exe("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_saml_sub ON users(saml_sub) WHERE saml_sub IS NOT NULL")
    _exe("CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(org_id)")


def downgrade():
    # 生产基线不可降级（会丢数据）。仅声明。
    pass
