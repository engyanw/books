# ==================== PostgreSQL 共享库建表（PG 模式一次性初始化） ====================
# PG 单库承载全部表（registry + documents + ai_configs）。CREATE TABLE IF NOT EXISTS
# 已合并全部演进列，故无需 ALTER；跳过 SQLite 专有（PRAGMA / FTS5 触发器）。语句经
# pg_adapter.convert_sql 兼容处理（BIGSERIAL 直接写为 PG 原生）。
_PG_SCHEMA_DDL = [
    # ----- registry: 用户/鉴权/团队/审计 -----
    """CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        oidc_sub TEXT,
        saml_sub TEXT,
        totp_secret TEXT,
        is_guest INTEGER NOT NULL DEFAULT 0,
        email TEXT,
        org_id TEXT,
        display_name TEXT,
        avatar_url TEXT,
        active INTEGER NOT NULL DEFAULT 1
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oidc_sub ON users(oidc_sub) WHERE oidc_sub IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_saml_sub ON users(saml_sub) WHERE saml_sub IS NOT NULL",
    """CREATE TABLE IF NOT EXISTS guest_invites (
        token TEXT PRIMARY KEY,
        owner_user_id TEXT NOT NULL,
        guest_username TEXT NOT NULL,
        email TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        accepted_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS webhooks (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        team_id TEXT,
        url TEXT NOT NULL,
        events TEXT NOT NULL DEFAULT '*',
        channel_type TEXT NOT NULL DEFAULT 'generic',
        secret TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_webhooks_team ON webhooks(team_id)",
    "ALTER TABLE webhooks ADD COLUMN IF NOT EXISTS channel_type TEXT NOT NULL DEFAULT 'generic'",
    "ALTER TABLE webhooks ADD COLUMN IF NOT EXISTS secret TEXT",
    """CREATE TABLE IF NOT EXISTS shares (
        share_code TEXT PRIMARY KEY,
        owner_user_id TEXT NOT NULL,
        doc_id TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_shares_owner ON shares(owner_user_id)",
    "ALTER TABLE shares ADD COLUMN IF NOT EXISTS team_id TEXT",
    "CREATE INDEX IF NOT EXISTS idx_shares_team ON shares(team_id)",
    # P1-5 ACL 感知搜索索引（镜像 doc_acl，供被授权方全局搜索）
    """CREATE TABLE IF NOT EXISTS doc_grants (
        doc_id TEXT NOT NULL,
        owner_user_id TEXT NOT NULL,
        grantee_user_id TEXT NOT NULL,
        permission TEXT NOT NULL,
        granted_at TEXT NOT NULL,
        expires_at TEXT,
        PRIMARY KEY (doc_id, grantee_user_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_grants_grantee ON doc_grants(grantee_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_doc_grants_owner ON doc_grants(owner_user_id)",
    """CREATE TABLE IF NOT EXISTS collab_state (
        room TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS collab_updates (
        room TEXT NOT NULL,
        seq INTEGER NOT NULL,
        data BYTEA NOT NULL,
        ts TEXT NOT NULL,
        PRIMARY KEY (room, seq)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_collab_updates_room ON collab_updates(room)",
    """CREATE TABLE IF NOT EXISTS teams (
        team_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT,
        owner_user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        org_id TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(org_id)",
    """CREATE TABLE IF NOT EXISTS team_members (
        team_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        created_at TEXT NOT NULL,
        PRIMARY KEY (team_id, user_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_tm_user ON team_members(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_tm_team ON team_members(team_id)",
    """CREATE TABLE IF NOT EXISTS team_roles (
        team_id TEXT NOT NULL,
        role TEXT NOT NULL,
        permissions_json TEXT NOT NULL DEFAULT '[]',
        is_default INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        PRIMARY KEY (team_id, role)
    )""",
    """CREATE TABLE IF NOT EXISTS audit_log (
        id BIGSERIAL PRIMARY KEY,
        ts TEXT NOT NULL,
        user_id TEXT,
        team_id TEXT,
        action TEXT NOT NULL,
        target_type TEXT,
        target_id TEXT,
        detail TEXT,
        prev_hash TEXT,
        record_hash TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_audit_team ON audit_log(team_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)",
    """CREATE TABLE IF NOT EXISTS notifications (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL,
        detail TEXT,
        link TEXT,
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read)",
    """CREATE TABLE IF NOT EXISTS reviews (
        id BIGSERIAL PRIMARY KEY,
        doc_id TEXT NOT NULL,
        team_id TEXT,
        requester_user_id TEXT NOT NULL,
        reviewer_user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        comment TEXT,
        created_at TEXT NOT NULL,
        decided_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON reviews(reviewer_user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_requester ON reviews(requester_user_id)",
    """CREATE TABLE IF NOT EXISTS review_steps (
        id BIGSERIAL PRIMARY KEY,
        review_id BIGINT NOT NULL,
        step INTEGER NOT NULL,
        reviewer_user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        comment TEXT,
        decided_at TEXT,
        mode TEXT NOT NULL DEFAULT 'serial',
        stage INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (review_id) REFERENCES reviews(id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_review_steps_review ON review_steps(review_id)",
    """CREATE TABLE IF NOT EXISTS workflow_definitions (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        team_id TEXT,
        definition_json TEXT NOT NULL DEFAULT '{}',
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_wfd_team ON workflow_definitions(team_id)",
    """CREATE TABLE IF NOT EXISTS workflow_instances (
        id TEXT PRIMARY KEY,
        workflow_def_id TEXT NOT NULL,
        review_id BIGINT,
        doc_id TEXT NOT NULL,
        team_id TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_wfi_doc ON workflow_instances(doc_id)",
    """CREATE TABLE IF NOT EXISTS workflow_sla (
        instance_id TEXT NOT NULL,
        stage INTEGER NOT NULL,
        deadline TEXT NOT NULL,
        escalated INTEGER NOT NULL DEFAULT 0,
        escalated_at TEXT,
        PRIMARY KEY (instance_id, stage)
    )""",
    """CREATE TABLE IF NOT EXISTS api_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        token_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_used TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)",
    """CREATE TABLE IF NOT EXISTS revoked_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        revoked_at TEXT NOT NULL,
        expires_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_revoked_user ON revoked_tokens(user_id)",
    """CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        ip TEXT,
        user_agent TEXT,
        created_at TEXT NOT NULL,
        last_active TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
    """CREATE TABLE IF NOT EXISTS refresh_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        issued_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT,
        rotated_from TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_refresh_hash ON refresh_tokens(token_hash)",
    """CREATE TABLE IF NOT EXISTS organizations (
        org_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_orgs_slug ON organizations(slug)",
    """CREATE TABLE IF NOT EXISTS scim_groups (
        group_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        org_id TEXT,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS scim_group_members (
        group_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        PRIMARY KEY (group_id, user_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_scim_members_user ON scim_group_members(user_id)",
    """CREATE TABLE IF NOT EXISTS saved_searches (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        query TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_id)",
    """CREATE TABLE IF NOT EXISTS doc_variants (
        group_id TEXT NOT NULL,
        doc_id TEXT NOT NULL,
        lang TEXT NOT NULL,
        owner_user_id TEXT NOT NULL,
        PRIMARY KEY (group_id, lang)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_variants_doc ON doc_variants(doc_id)",
    """CREATE TABLE IF NOT EXISTS templates (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        team_id TEXT,
        name TEXT NOT NULL,
        content TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '',
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT '',
        variables_json TEXT NOT NULL DEFAULT '[]',
        version INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active',
        parent_id TEXT,
        org_managed INTEGER NOT NULL DEFAULT 0,
        updated_by TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
    )""",
    "CREATE INDEX IF NOT EXISTS idx_templates_team ON templates(team_id)",
    """CREATE TABLE IF NOT EXISTS template_versions (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_tplver_tpl ON template_versions(template_id, version)",
    """CREATE TABLE IF NOT EXISTS oauth_clients (
        client_id TEXT PRIMARY KEY,
        client_secret_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        owner_user_id TEXT NOT NULL,
        redirect_uris TEXT NOT NULL DEFAULT '',
        scopes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS oauth_codes (
        code TEXT PRIMARY KEY,
        client_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        redirect_uri TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_oauth_codes_client ON oauth_codes(client_id)",
    """CREATE TABLE IF NOT EXISTS oauth_token_scopes (
        token_hash TEXT PRIMARY KEY,
        client_id TEXT,
        scope TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS ai_usage (
        user_id TEXT NOT NULL,
        team_id TEXT,
        day TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, team_id, day)
    )""",
    """CREATE TABLE IF NOT EXISTS doc_git_repos (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_git_scope ON doc_git_repos(scope, scope_id)",
    "ALTER TABLE doc_git_repos ADD COLUMN IF NOT EXISTS webhook_secret TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE doc_git_repos ADD COLUMN IF NOT EXISTS owner_user_id TEXT NOT NULL DEFAULT ''",
    """CREATE TABLE IF NOT EXISTS doc_releases (
        release_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        version TEXT NOT NULL DEFAULT '1.0',
        manifest TEXT NOT NULL DEFAULT '[]',
        frozen INTEGER NOT NULL DEFAULT 0,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS legal_holds (
        id TEXT PRIMARY KEY,
        scope TEXT NOT NULL,
        scope_id TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL,
        held_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        released_at TEXT,
        released_by TEXT
    )""",
    """CREATE INDEX IF NOT EXISTS idx_legal_holds_scope ON legal_holds(scope, scope_id, released_at)""",
    """CREATE TABLE IF NOT EXISTS leader_lease (
        id INTEGER PRIMARY KEY DEFAULT 1,
        holder TEXT NOT NULL,
        acquired_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )""",
    # ----- documents（每用户/团队库；PG 共享，靠 user_id 过滤） -----
    """CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        share_code TEXT UNIQUE,
        share_expires_at TEXT,
        version INTEGER NOT NULL DEFAULT 1,
        kind TEXT NOT NULL DEFAULT 'file',
        path TEXT NOT NULL DEFAULT '',
        user_id TEXT NOT NULL DEFAULT '',
        deleted_at TEXT,
        tags TEXT NOT NULL DEFAULT '',
        starred INTEGER NOT NULL DEFAULT 0,
        last_opened_at TEXT,
        share_password TEXT,
        share_max_views INTEGER,
        share_views INTEGER NOT NULL DEFAULT 0,
        share_burn_after_read INTEGER NOT NULL DEFAULT 0,
        share_mode TEXT NOT NULL DEFAULT 'readonly',
        is_encrypted INTEGER NOT NULL DEFAULT 0,
        enc_salt TEXT,
        enc_iv TEXT,
        enc_iters INTEGER NOT NULL DEFAULT 0,
        classification TEXT NOT NULL DEFAULT 'internal',
        status TEXT NOT NULL DEFAULT 'draft',
        archived INTEGER NOT NULL DEFAULT 0,
        etag TEXT NOT NULL DEFAULT ''
    )""",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS etag TEXT NOT NULL DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS idx_share_code ON documents(share_code)",
    "CREATE INDEX IF NOT EXISTS idx_updated_at ON documents(updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_path ON documents(path)",
    "CREATE INDEX IF NOT EXISTS idx_user ON documents(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_deleted_at ON documents(deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_starred ON documents(starred)",
    """CREATE TABLE IF NOT EXISTS doc_versions (
        id BIGSERIAL PRIMARY KEY,
        doc_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        created_by TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON doc_versions(doc_id)",
    """CREATE TABLE IF NOT EXISTS doc_acl (
        doc_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        permission TEXT NOT NULL DEFAULT 'read',
        granted_at TEXT NOT NULL,
        expires_at TEXT,
        PRIMARY KEY (doc_id, user_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_acl_user ON doc_acl(user_id)",
    """CREATE TABLE IF NOT EXISTS team_doc_acl (
        doc_id TEXT NOT NULL,
        grantee_user_id TEXT NOT NULL,
        permission TEXT NOT NULL,
        granted_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (doc_id, grantee_user_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_team_doc_acl_doc ON team_doc_acl(doc_id)",
    """CREATE TABLE IF NOT EXISTS suggestions (
        id BIGSERIAL PRIMARY KEY,
        doc_id TEXT NOT NULL,
        proposer_id TEXT NOT NULL,
        original_text TEXT NOT NULL DEFAULT '',
        proposed_text TEXT NOT NULL DEFAULT '',
        comment TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        decided_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_suggestions_doc ON suggestions(doc_id)",
    # P1-8 生命周期门禁电子签名（PG）
    """CREATE TABLE IF NOT EXISTS doc_signatures (
        id TEXT PRIMARY KEY,
        doc_id TEXT NOT NULL,
        doc_version INTEGER NOT NULL,
        signer_user_id TEXT NOT NULL,
        intent TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        signed_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_sig_doc ON doc_signatures(doc_id)",
    """CREATE TABLE IF NOT EXISTS doc_comments (
        id BIGSERIAL PRIMARY KEY,
        doc_id TEXT NOT NULL,
        doc_version INTEGER,
        anchor_type TEXT NOT NULL DEFAULT 'line',
        anchor_start INTEGER,
        anchor_end INTEGER,
        selector TEXT,
        author_user_id TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'open',
        parent_id BIGINT,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        resolver_user_id TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_comments_doc ON doc_comments(doc_id)",
    "CREATE INDEX IF NOT EXISTS idx_doc_comments_parent ON doc_comments(parent_id)",
    """CREATE TABLE IF NOT EXISTS doc_branches (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_branches_doc ON doc_branches(doc_id)",
    """CREATE TABLE IF NOT EXISTS doc_links (
        id BIGSERIAL PRIMARY KEY,
        source_doc_id TEXT NOT NULL,
        target_ref TEXT NOT NULL,
        target_doc_id TEXT,
        kind TEXT NOT NULL DEFAULT 'wikilink',
        broken INTEGER NOT NULL DEFAULT 0,
        checked_at TEXT,
        UNIQUE(source_doc_id, target_ref)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_doc_links_source ON doc_links(source_doc_id)",
    "CREATE INDEX IF NOT EXISTS idx_doc_links_broken ON doc_links(broken)",
    """CREATE TABLE IF NOT EXISTS doc_contributions (
        id BIGSERIAL PRIMARY KEY,
        doc_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        lines_added INTEGER NOT NULL DEFAULT 0,
        lines_deleted INTEGER NOT NULL DEFAULT 0,
        ts TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_contrib_doc ON doc_contributions(doc_id)",
    # ----- AI 配置 -----
    """CREATE TABLE IF NOT EXISTS ai_configs (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        api_url TEXT NOT NULL,
        model TEXT NOT NULL,
        enc_key TEXT NOT NULL DEFAULT '',
        usage_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS ai_conversations (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        messages_json TEXT NOT NULL DEFAULT '[]',
        msg_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        parent_id TEXT,
        fork_at_msg_index INTEGER
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ai_conv_updated ON ai_conversations(updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_ai_conv_parent ON ai_conversations(parent_id)",
    # 附件表（抽取的可读文本存 extracted_text，PG 用 pg_trgm ILIKE 检索；不建 FTS5）
    """CREATE TABLE IF NOT EXISTS attachments (
        id BIGSERIAL PRIMARY KEY,
        doc_id TEXT,
        owner_user_id TEXT NOT NULL,
        filename TEXT NOT NULL DEFAULT '',
        storage_url TEXT NOT NULL,
        content_type TEXT NOT NULL DEFAULT '',
        size BIGINT NOT NULL DEFAULT 0,
        extracted_text TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_attachments_doc ON attachments(doc_id)",
    "CREATE INDEX IF NOT EXISTS idx_attachments_owner ON attachments(owner_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_attachments_fts ON attachments USING gin (extracted_text gin_trgm_ops)",
    # ----- 全文搜索：pg_trgm（CJK 友好的三元组索引，加速 ILIKE 子串匹配 + 相似度排序）-----
    # PG 无 FTS5 等价物（CJK 需 zhparser/pg_jieba 额外扩展，默认未装），故用 pg_trgm 替代：
    # ILIKE '%q%' 走 GIN trigram 索引，中文按字符三元组命中。扩展缺失则降级为顺序扫描（仍可用）。
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "CREATE INDEX IF NOT EXISTS idx_documents_content_trgm ON documents USING gin (content gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS idx_documents_title_trgm ON documents USING gin (title gin_trgm_ops)",
    # ----- 多租户行级安全（RLS）：org_id 维度的库级隔离 -----
    # 设计：org_id = current_setting('app.org_id', true)（严格策略，NULL-org 行仅超级用户可见）。
    # 超级用户（如 demo_md2）天然 BYPASSRLS，故现有 app 流程不受影响；仅在 app 以非超级用户角色
    # （md2_rls）连接时强制生效——证明"即便应用层漏加 WHERE，DB 层也无法跨组织泄露"。
    # 1) 补 org_id 列（users/teams 已有，仅 audit_log/team_members/notifications 缺）
    "ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS org_id TEXT",
    "ALTER TABLE team_members ADD COLUMN IF NOT EXISTS org_id TEXT",
    "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS org_id TEXT",
    "CREATE INDEX IF NOT EXISTS idx_audit_org ON audit_log(org_id)",
    "CREATE INDEX IF NOT EXISTS idx_tm_org ON team_members(org_id)",
    "CREATE INDEX IF NOT EXISTS idx_notif_org ON notifications(org_id)",
    # 2) 严格隔离策略（org_id 必须等于当前会话 app.org_id）
    #    注：PG 的 CREATE POLICY 不支持 IF NOT EXISTS；重复执行会报"已存在"，由 _init_pg_schema
    #    的逐句 except 吞掉 → 等价幂等。
    "CREATE POLICY org_isolation_users ON users USING (org_id = current_setting('app.org_id', true))",
    "CREATE POLICY org_isolation_teams ON teams USING (org_id = current_setting('app.org_id', true))",
    "CREATE POLICY org_isolation_team_members ON team_members USING (org_id = current_setting('app.org_id', true))",
    "CREATE POLICY org_isolation_audit_log ON audit_log USING (org_id = current_setting('app.org_id', true))",
    "CREATE POLICY org_isolation_notifications ON notifications USING (org_id = current_setting('app.org_id', true))",
    "ALTER TABLE users ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE teams ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE team_members ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE notifications ENABLE ROW LEVEL SECURITY",
    # FORCE：即使表属主也受策略约束（超级用户仍 BYPASSRLS，故 app 超管池不受影响）
    "ALTER TABLE users FORCE ROW LEVEL SECURITY",
    "ALTER TABLE teams FORCE ROW LEVEL SECURITY",
    "ALTER TABLE team_members FORCE ROW LEVEL SECURITY",
    "ALTER TABLE audit_log FORCE ROW LEVEL SECURITY",
    "ALTER TABLE notifications FORCE ROW LEVEL SECURITY",
    # 3) 引导函数：解析 user_id→org_id，绕过 RLS（SECURITY DEFINER，以建表超管身份运行）
    #    解决"登录时尚无 org 上下文，但读 users 表需 org 上下文"的鸡生蛋问题。
    """CREATE OR REPLACE FUNCTION app_resolve_org(uid TEXT) RETURNS TEXT
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
            SELECT org_id FROM users WHERE user_id = $1
        $$""",
]


async def _init_pg_schema():
    """PG 共享库一次性建表（幂等）。跳过 SQLite 专有项；冲突对象（已存在）忽略。"""
    from pg_adapter import wrap, unwrap, release_conn, acquire_conn
    conn = wrap(await acquire_conn())
    try:
        for stmt in _PG_SCHEMA_DDL:
            try:
                await conn.execute(stmt)
            except Exception as e:
                # 幂等：已存在/已建对象忽略
                logger.debug("PG DDL 跳过：%s | %s", str(e)[:120], stmt.strip().splitlines()[0][:60])
        # 不可变审计（AUDIT_IMMUTABLE=1）：PG 用 BEFORE UPDATE/DELETE 触发器 + plpgsql 函数阻断。
        # 关闭时保留函数/触发器无害（再次启用等价），但默认 schema 不创建以避免无谓 plpgsql 依赖。
        if AUDIT_IMMUTABLE:
            pg_immutable_stmts = [
                "CREATE OR REPLACE FUNCTION _audit_immutable_block() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'audit_log 不可变（AUDIT_IMMUTABLE=1）：禁止 %', TG_OP; END $$",
                "DROP TRIGGER IF EXISTS audit_no_update ON audit_log",
                "CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_log "
                "FOR EACH STATEMENT EXECUTE FUNCTION _audit_immutable_block()",
                "DROP TRIGGER IF EXISTS audit_no_delete ON audit_log",
                "CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_log "
                "FOR EACH STATEMENT EXECUTE FUNCTION _audit_immutable_block()",
            ]
            for stmt in pg_immutable_stmts:
                try:
                    await conn.execute(stmt)
                except Exception as e:
                    logger.debug("PG immutable DDL 跳过：%s", str(e)[:120])
    finally:
        await release_conn(unwrap(conn))


async def _get_registry_db():
    """从连接池取 registry 连接（PG 模式走 PG pool，SQLite 走文件池）。"""
    from pg_adapter import is_pg, wrap, acquire_conn, release_conn
    if is_pg():
        conn = await acquire_conn()
        return wrap(conn)
    if _registry_pool:
        return _registry_pool.pop()
    _ensure_parent(REGISTRY_DB_PATH)
    db = await aiosqlite.connect(REGISTRY_DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def _put_registry_db(db):
    """归还 registry 连接到池。"""
    from pg_adapter import is_pg, unwrap, release_conn
    if is_pg():
        await release_conn(unwrap(db))
        return
    if len(_registry_pool) < _DB_POOL_SIZE:
        _registry_pool.append(db)
    else:
        await db.close()


@asynccontextmanager
async def _registry_transaction():
    """共享注册库事务上下文（PG 或 SQLite）。"""
    from pg_adapter import is_pg
    db = await _get_registry_db()
    with span("db.registry_transaction"):
        try:
            if is_pg():
                # PG: asyncpg 自带事务
                async with db.transaction():
                    yield db
            else:
                yield db
                await db.commit()
        except Exception:
            if not is_pg():
                await db.rollback()
            raise
        finally:
            await _put_registry_db(db)


# ==================== 团队（每团队库 + 成员/角色/审计）====================
_TEAM_ROLE_RANK = {"viewer": 1, "commenter": 2, "reviewer": 2, "member": 2, "admin": 3, "owner": 4}

# 权限矩阵：可配置的细粒度权限 key 集合。自定义角色可任意组合。
_TEAM_PERMISSIONS = {
    "doc.read", "doc.create", "doc.edit", "doc.delete", "doc.publish", "doc.archive", "doc.comment",
    "review.request", "review.decide",
    "member.invite", "member.remove", "role.manage", "settings.manage",
}
# 内建角色默认权限矩阵（与 _TEAM_ROLE_RANK 的层级语义对齐，保证既有行为不回归）
# P2-10：commenter（仅评论）/reviewer（评审+评论，不可编辑）作为细粒度角色。
_DEFAULT_ROLE_MATRIX = {
    "viewer": {"doc.read", "doc.publish", "review.decide"},
    "commenter": {"doc.read", "doc.comment"},
    "reviewer": {"doc.read", "doc.comment", "review.request", "review.decide"},
    "member": {"doc.read", "doc.create", "doc.edit", "doc.delete", "doc.archive", "doc.comment",
               "review.request", "review.decide", "doc.publish"},
    "admin": {"doc.read", "doc.create", "doc.edit", "doc.delete", "doc.publish", "doc.archive", "doc.comment",
              "review.request", "review.decide", "member.invite", "member.remove", "settings.manage"},
    "owner": set(_TEAM_PERMISSIONS),
}


def _normalize_perms(permissions) -> set:
    """将权限入参（list/set/逗号串）归一为合法权限 key 集合，忽略未知项。"""
    if isinstance(permissions, str):
        permissions = [p.strip() for p in permissions.split(",") if p.strip()]
    return {p for p in (permissions or []) if p in _TEAM_PERMISSIONS}


async def _team_role_permissions(team_id: str, role: str) -> set:
    """取团队某角色的权限集合。无自定义行时回退到内建默认矩阵。"""
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT permissions_json FROM team_roles WHERE team_id=? AND role=?",
            (team_id, role),
        )).fetchone()
    if row:
        try:
            return _normalize_perms(json.loads(row["permissions_json"]))
        except Exception:
            pass
    return set(_DEFAULT_ROLE_MATRIX.get(role, set()))


async def _has_team_permission(team_id: str, user_id: str, permission: str) -> bool:
    role = await _team_member_role(team_id, user_id)
    if role is None:
        return False
    perms = await _team_role_permissions(team_id, role)
    return permission in perms


async def _require_team_permission(team_id: str, user_id: str, permission: str):
    """要求当前用户在该团队拥有指定权限，否则 403。owner 始终通过（保底）。"""
    role = await _team_member_role(team_id, user_id)
    if role is None:
        raise HTTPException(403, "非团队成员")
    if role == "owner":
        return role
    perms = await _team_role_permissions(team_id, role)
    if permission not in perms:
        raise HTTPException(403, f"当前角色无 {permission} 权限")
    return role


async def _seed_default_team_roles(team_id: str, db):
    """为新建团队写入内建角色的默认权限矩阵占位行。"""
    now = _utcnow_iso()
    for role, perms in _DEFAULT_ROLE_MATRIX.items():
        await db.execute(
            "INSERT OR IGNORE INTO team_roles (team_id, role, permissions_json, is_default, created_at) VALUES (?,?,?,?,?)",
            (team_id, role, json.dumps(sorted(perms)), 1, now),
        )

_team_db_pools: "OrderedDict[str, list]" = OrderedDict()
_team_db_initialized: set = set()


def _team_db_path(team_id: str) -> Path:
    region = _sync_read_region("teams", team_id, key_col="team_id")
    d = _residency_dir(region) / "teams" / team_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "docs.db"


async def _get_team_db(team_id: str):
    """从团队连接池取连接（PG 模式共享 pool，SQLite 走文件池）。"""
    from pg_adapter import is_pg, wrap, acquire_conn, release_conn
    if is_pg():
        return wrap(await acquire_conn())
    pool = _team_db_pools.get(team_id)
    if pool:
        _team_db_pools.move_to_end(team_id)
        return pool.pop()
    db = await aiosqlite.connect(_team_db_path(team_id))
    db.row_factory = aiosqlite.Row
    await _register_fts_function(db)
    if team_id not in _team_db_initialized:
        await _apply_documents_schema(db)
        await _apply_ai_configs_schema(db)
        await _apply_team_doc_acl_schema(db)
        _team_db_initialized.add(team_id)
    return db


async def _put_team_db(team_id: str, db):
    from pg_adapter import is_pg, unwrap, release_conn
    if is_pg():
        await release_conn(unwrap(db))
        return
    pool = _team_db_pools.setdefault(team_id, [])
    _team_db_pools.move_to_end(team_id)
    if len(pool) < _DB_POOL_SIZE:
        pool.append(db)
    else:
        await db.close()
    await _evict_team_pools_if_needed()


@asynccontextmanager
async def _team_db_transaction(team_id: str):
    """团队库事务上下文（PG 或 SQLite）。PG 模式下 team_id 用于 WHERE 过滤（共享 pool）。"""
    from pg_adapter import is_pg
    db = await _get_team_db(team_id)
    with span("db.team_transaction", team=team_id):
        try:
            if is_pg():
                async with db.transaction():
                    yield db
            else:
                yield db
                await db.commit()
        except Exception:
            if not is_pg():
                await db.rollback()
            raise
        finally:
            await _put_team_db(team_id, db)


async def _team_member_role(team_id: str, user_id: str) -> str | None:
    """返回用户在该团队的角色；非成员返回 None。"""
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT role FROM team_members WHERE team_id=? AND user_id=?", (team_id, user_id)
        )).fetchone()
    return row["role"] if row else None


async def _require_team_role(team_id: str, user_id: str, min_role: str) -> str:
    """校验成员身份与最低角色；不满足抛 403。返回当前角色。"""
    role = await _team_member_role(team_id, user_id)
    if role is None:
        raise HTTPException(403, "你不是该团队成员")
    if _TEAM_ROLE_RANK.get(role, 0) < _TEAM_ROLE_RANK.get(min_role, 0):
        raise HTTPException(403, f"需要 {min_role} 及以上权限")
    return role


async def _resolve_user_org(user_id: str) -> str | None:
    """解析用户所属 org_id（PG 走 RLS 旁路的 SECURITY DEFINER 函数；SQLite 直读）。
    用于审计/通知落 org_id，及非超级用户连接的 org 上下文引导。失败返回 None（不影响主流程）。"""
    if not user_id:
        return None
    try:
        if is_pg():
            async with _registry_transaction() as db:
                row = await (await db.execute("SELECT app_resolve_org(?)", (user_id,))).fetchone()
            return row[0] if row else None
        async with _registry_transaction() as db:
            row = await (await db.execute("SELECT org_id FROM users WHERE user_id=?", (user_id,))).fetchone()
        return row["org_id"] if row else None
    except Exception as e:
        logger.debug("解析用户 org 失败: %s", e)
        return None


async def _resolve_user_id_by_username(username: str) -> str | None:
    """根据用户名解析 user_id（registry 库）。不存在返回 None。"""
    if not username:
        return None
    try:
        async with _registry_transaction() as db:
            row = await (await db.execute("SELECT user_id FROM users WHERE username=?", (username.strip(),))).fetchone()
        return row["user_id"] if row else None
    except Exception:
        return None


async def _username_of(user_id: str) -> str | None:
    """根据 user_id 反查 username（registry 库）。不存在返回 None。"""
    if not user_id:
        return None
    try:
        async with _registry_transaction() as db:
            row = await (await db.execute("SELECT username FROM users WHERE user_id=?", (user_id,))).fetchone()
        return row["username"] if row else None
    except Exception:
        return None


async def _set_org_context(db, org_id: str | None):
    """在当前 PG 事务内设置 app.org_id（事务级），使 RLS 策略可见对应 org 行。
    SQLite 为 no-op（无 RLS）。生产部署应让 app 以非超级用户角色连接并在每个请求调用此函数。"""
    if not is_pg():
        return
    try:
        await db.execute("SELECT set_config('app.org_id', ?, true)", (org_id or "",))
    except Exception as e:
        logger.debug("设置 org 上下文失败: %s", e)


async def _audit(user_id: str, team_id: str | None, action: str,
                 target_type: str = None, target_id: str = None, detail: str = None):
    """记录审计日志（含 hash 链防篡改）。失败仅告警，不影响主流程。"""
    try:
        ts = _utcnow_iso()
        org_id = await _resolve_user_org(user_id)
        async with _registry_transaction() as db:
            # 获取上一条记录的 hash
            prev = await (await db.execute("SELECT record_hash FROM audit_log ORDER BY id DESC LIMIT 1")).fetchone()
            prev_hash = prev["record_hash"] if prev and prev["record_hash"] else "GENESIS"
            # 计算本条 hash = sha256(prev_hash + ts + user_id + action + detail)
            content = f"{prev_hash}|{ts}|{user_id or ''}|{action}|{target_id or ''}|{detail or ''}"
            record_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            await db.execute(
                "INSERT INTO audit_log (ts, user_id, team_id, action, target_type, target_id, detail, prev_hash, record_hash, org_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ts, user_id, team_id, action, target_type, target_id, detail, prev_hash, record_hash, org_id),
            )
    except Exception as e:
        logger.warning("写审计日志失败: %s", e)


async def _notify(user_id: str, ntype: str, detail: str = None, link: str = None, team_id: str = None):
    """给某用户发站内通知 + 触发匹配的 webhook（个人 + 团队）。失败仅告警。"""
    try:
        org_id = await _resolve_user_org(user_id)
        async with _registry_transaction() as db:
            await db.execute(
                "INSERT INTO notifications (user_id, type, detail, link, is_read, created_at, org_id) VALUES (?,?,?,?,?,?,?)",
                (user_id, ntype, detail, link, 0, _utcnow_iso(), org_id),
            )
    except Exception as e:
        logger.warning("写通知失败: %s", e)
    # 触发 webhook（个人 + 团队；同步确保可靠发出）
    await _fire_webhooks(user_id, ntype, {"detail": detail, "link": link}, team_id=team_id)
    # 一等公民集成连接器（Slack/Teams）；仅对配置的事件类型推送
    if ntype in INTEGRATION_NOTIFY_EVENTS:
        await _integration_notify(ntype, detail, link)


async def _integration_notify(event: str, detail: str = None, link: str = None):
    """推送关键事件到 Slack / Microsoft Teams（配置驱动，失败仅告警不阻断）。"""
    text = f"[md-docs] {event}: {detail or ''}{(' ' + link) if link else ''}"
    payloads = []
    if INTEGRATION_SLACK_WEBHOOK_URL:
        payloads.append((INTEGRATION_SLACK_WEBHOOK_URL, {"text": text}))
    if INTEGRATION_TEAMS_WEBHOOK_URL:
        payloads.append((INTEGRATION_TEAMS_WEBHOOK_URL, {"text": text}))
    for url, body in payloads:
        try:
            async with httpx.AsyncClient(timeout=10.0) as cli:
                r = await cli.post(url, json=body)
                if r.status_code >= 300:
                    logger.warning("集成推送失败 %s → %s", url, r.status_code)
        except Exception as e:
            logger.warning("集成推送异常 %s: %s", url, e)


def _parse_mentions(text: str) -> list:
    """从文本解析 @mention 用户名（去重保序）。与注册校验 [A-Za-z0-9_.\\-]{1,32} 对齐。"""
    if not text:
        return []
    seen, out = set(), []
    for m in re.findall(r"(?:^|\s)@([A-Za-z0-9_.\-]{1,32})", text):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


async def _notify_mentions(text: str, *, author_id: str, link: str, detail_prefix: str = "提及你"):
    """解析 text 中的 @mention，查 username→user_id 后发通知；跳过作者自身。"""
    names = _parse_mentions(text)
    if not names:
        return
    placeholders = ",".join("?" for _ in names)
    try:
        async with _registry_transaction() as db:
            rows = await (await db.execute(
                f"SELECT user_id, username FROM users WHERE username IN ({placeholders}) AND active=1", names
            )).fetchall()
    except Exception:
        rows = []
    for r in rows:
        if r["user_id"] == author_id:
            continue
        await _notify(r["user_id"], "mention", detail=f"{detail_prefix}（@{r['username']}）", link=link)


def _format_webhook_payload(channel_type: str, event: str, user_id: str, payload: dict) -> tuple:
    """按渠道类型构造请求体。返回 (body_dict, is_json)。
    - generic: 原始 JSON（向后兼容）  - slack: Incoming Webhook 文本块  - teams: Adaptive Card"""
    detail = payload.get("detail") or ""
    link = payload.get("link") or ""
    text = f"[{event}] {detail}".strip()
    if link:
        text = f"{text}  {link}".strip()
    if channel_type == "slack":
        return {"text": text}, True
    if channel_type == "teams":
        return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
                "content": {"type": "AdaptiveCard", "version": "1.2",
                             "body": [{"type": "TextBlock", "text": text, "wrap": True}]}}]}, True
    return {"event": event, "user_id": user_id, **payload}, True


async def _fire_webhooks(user_id: str, event: str, payload: dict, team_id: str = None):
    """查找匹配的 webhook（个人 user_id + 可选团队 team_id）并 POST。
    渠道感知（generic/slack/teams）+ HMAC-SHA256 签名 + 失败重试 1 次。"""
    import fnmatch
    try:
        async with _registry_transaction() as db:
            if team_id:
                rows = await (await db.execute(
                    "SELECT url, events, channel_type, secret FROM webhooks WHERE user_id=? OR team_id=?",
                    (user_id, team_id)
                )).fetchall()
            else:
                rows = await (await db.execute(
                    "SELECT url, events, channel_type, secret FROM webhooks WHERE user_id=?", (user_id,)
                )).fetchall()
    except Exception:
        return
    for r in rows:
        events = (r["events"] or "*").split(",")
        if not any(fnmatch.fnmatch(event, e.strip()) for e in events):
            continue
        body, is_json = _format_webhook_payload(r["channel_type"] or "generic", event, user_id, payload)
        headers = {}
        if r["secret"]:
            sig = hmac.new((r["secret"] or "").encode("utf-8"),
                           json.dumps(body).encode("utf-8"), hashlib.sha256).hexdigest()
            headers["X-Signature"] = sig
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(r["url"], json=body, headers=headers)
                break
            except Exception as e:
                if attempt == 2:
                    logger.warning("Webhook 投递失败 url=%s event=%s: %s", r["url"], event, e)


async def _notify_saved_search_matches(title: str, content: str, author_id: str):
    """新文档创建时扫描所有用户的保存搜索，匹配则通知订阅者。"""
    try:
        # 先读取所有保存搜索（事务内）
        async with _registry_transaction() as db:
            rows = await (await db.execute("SELECT id, user_id, name, query FROM saved_searches")).fetchall()
        # 事务结束后逐条通知（避免嵌套 registry 事务）
        for r in rows:
            if r["user_id"] == author_id:
                continue
            q = r["query"]
            # 大小写不敏感匹配
            if q and (q.lower() in (title or "").lower() or q.lower() in (content or "").lower()):
                await _notify(r["user_id"], "search.match",
                              detail=f"新文档匹配你的搜索「{r['name']}」：{title}",
                              link=f"/?search={q}")
    except Exception as e:
        logger.warning("保存搜索匹配失败: %s", e)


async def _is_admin(user_id: str) -> bool:
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,))).fetchone()
    return bool(row and row["is_admin"])


# ==================== AI 用量计费/配额 ====================
def _ai_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _ai_usage_count(user_id: str, team_id: str | None) -> int:
    """当日该用户（在指定空间）已用次数。team_id='' 用 NULL 存个人空间。"""
    day = _ai_today()
    async with _registry_transaction() as db:
        if team_id:
            row = await (await db.execute(
                "SELECT count FROM ai_usage WHERE user_id=? AND team_id=? AND day=?", (user_id, team_id, day)
            )).fetchone()
        else:
            row = await (await db.execute(
                "SELECT count FROM ai_usage WHERE user_id=? AND team_id IS NULL AND day=?", (user_id, day)
            )).fetchone()
    return row["count"] if row else 0


async def _ai_usage_inc(user_id: str, team_id: str | None, n: int = 1):
    day = _ai_today()
    async with _registry_transaction() as db:
        if team_id:
            await db.execute(
                "INSERT INTO ai_usage (user_id, team_id, day, count) VALUES (?,?,?,?) "
                "ON CONFLICT(user_id, team_id, day) DO UPDATE SET count=count+?",
                (user_id, team_id, day, n, n),
            )
        else:
            await db.execute(
                "INSERT INTO ai_usage (user_id, team_id, day, count) VALUES (?,NULL,?,?) "
                "ON CONFLICT(user_id, team_id, day) DO UPDATE SET count=count+?",
                (user_id, day, n, n),
            )


async def _ai_quota_check(user_id: str, team_id: str | None) -> str | None:
    """校验配额；超限返回错误提示，否则返回 None。"""
    used = await _ai_usage_count(user_id, team_id)
    q = AI_TEAM_DAILY_QUOTA if team_id else AI_USER_DAILY_QUOTA
    if q and used >= q:
        scope = f"团队每日 {q}" if team_id else f"用户每日 {q}"
        return f"AI 调用已达{scope}配额上限（已用 {used} 次）"
    return None


async def _user_doc_usage(user_id: str) -> dict:
    """用户文档用量：{count, storage_bytes}（未删除文档数与正文字节）。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT COUNT(*) AS c, "
            "COALESCE(SUM(LENGTH(content)),0) AS bytes "
            "FROM documents WHERE deleted_at IS NULL AND user_id=?",
            (user_id,),
        )).fetchone()
    return {"count": int(row["c"] or 0), "storage_bytes": int(row["bytes"] or 0)}


async def _team_doc_usage(tid: str) -> dict:
    """团队文档用量：{count, storage_bytes, member_count}（文档在团队库，成员在注册库）。"""
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(LENGTH(content)),0) AS bytes "
            "FROM documents WHERE deleted_at IS NULL"
        )).fetchone()
    async with _registry_transaction() as rdb:
        m = await (await rdb.execute(
            "SELECT COUNT(*) AS c FROM team_members WHERE team_id=?", (tid,)
        )).fetchone()
    return {"count": int(row["c"] or 0), "storage_bytes": int(row["bytes"] or 0),
            "member_count": int(m["c"] or 0)}


async def _user_team_count(user_id: str) -> int:
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT COUNT(*) AS c FROM teams WHERE owner_user_id=?", (user_id,)
        )).fetchone()
    return int(row["c"] or 0)


async def _doc_quota_check_user(user_id: str, extra_bytes: int = 0) -> Optional[str]:
    """用户文档/存储配额校验；超限返回提示。"""
    if not USER_MAX_DOCS and not USER_MAX_STORAGE_BYTES:
        return None
    u = await _user_doc_usage(user_id)
    if USER_MAX_DOCS and u["count"] >= USER_MAX_DOCS:
        return f"文档数已达上限 {USER_MAX_DOCS}（当前 {u['count']}）"
    if USER_MAX_STORAGE_BYTES and u["storage_bytes"] + extra_bytes > USER_MAX_STORAGE_BYTES:
        return f"存储已达上限 {USER_MAX_STORAGE_BYTES} 字节（已用 {u['storage_bytes']}）"
    return None


async def _doc_quota_check_team(tid: str, extra_bytes: int = 0) -> Optional[str]:
    if not TEAM_MAX_DOCS and not TEAM_MAX_STORAGE_BYTES:
        return None
    u = await _team_doc_usage(tid)
    if TEAM_MAX_DOCS and u["count"] >= TEAM_MAX_DOCS:
        return f"团队文档数已达上限 {TEAM_MAX_DOCS}（当前 {u['count']}）"
    if TEAM_MAX_STORAGE_BYTES and u["storage_bytes"] + extra_bytes > TEAM_MAX_STORAGE_BYTES:
        return f"团队存储已达上限 {TEAM_MAX_STORAGE_BYTES} 字节（已用 {u['storage_bytes']}）"
    return None


async def _team_quota_check_create(user_id: str) -> Optional[str]:
    if not USER_MAX_TEAMS:
        return None
    n = await _user_team_count(user_id)
    if n >= USER_MAX_TEAMS:
        return f"已达团队数上限 {USER_MAX_TEAMS}（当前 {n}）"
    return None


# ==================== 法务保留（legal hold）====================
async def _doc_legal_hold(user_id: str = None, team_id: str = None) -> Optional[str]:
    """返回阻断删除的活跃法务保留原因；无保留返回 None。
    范围：global（全站）、user（某用户全部个人文档）、team（某团队全部文档）。"""
    async with _registry_transaction() as db:
        clauses = ["released_at IS NULL"]
        params = []
        rows = []
        # 优先 global
        g = await (await db.execute(
            "SELECT reason FROM legal_holds WHERE scope='global' AND released_at IS NULL LIMIT 1"
        )).fetchone()
        if g:
            return f"全局法务保留：{g['reason']}"
        if user_id:
            rows = await (await db.execute(
                "SELECT reason FROM legal_holds WHERE scope='user' AND scope_id=? AND released_at IS NULL LIMIT 1",
                (user_id,),
            )).fetchall()
            if rows:
                return f"用户法务保留：{rows[0]['reason']}"
        if team_id:
            rows = await (await db.execute(
                "SELECT reason FROM legal_holds WHERE scope='team' AND scope_id=? AND released_at IS NULL LIMIT 1",
                (team_id,),
            )).fetchall()
            if rows:
                return f"团队法务保留：{rows[0]['reason']}"
    return None


def _fts_sql_tok(s):
    """SQLite 触发器调用的分词函数（FTS5 写入前对 CJK 文本切词）。"""
    try:
        return _fts_tokenize_text(s if isinstance(s, str) else "")
    except Exception:
        return s if isinstance(s, str) else ""


async def _register_fts_function(db):
    """在每个 SQLite 连接注册 fts_tokenize SQL 函数，供 FTS5 触发器使用。PG 跳过。"""
    try:
        await db.create_function("fts_tokenize", 1, _fts_sql_tok)
    except Exception:
        pass  # PG 或不支持 create_function：FTS5 本就仅 SQLite


async def _get_db(user_id: str):
    """从该用户的连接池取连接（PG 模式共享 pool，SQLite 走文件池）；首次建表。"""
    from pg_adapter import is_pg, wrap, acquire_conn, release_conn
    if is_pg():
        return wrap(await acquire_conn())
    pool = _user_db_pools.get(user_id)
    if pool:
        # 命中即提升为最近使用（移到尾部）
        _user_db_pools.move_to_end(user_id)
        return pool.pop()
    db = await aiosqlite.connect(_user_db_path(user_id))
    db.row_factory = aiosqlite.Row
    await _register_fts_function(db)
    if user_id not in _user_db_initialized:
        await _apply_documents_schema(db)
        await _apply_ai_configs_schema(db)
        _user_db_initialized.add(user_id)
    return db


async def _put_db(user_id: str, db):
    from pg_adapter import is_pg, unwrap, release_conn
    if is_pg():
        await release_conn(unwrap(db))
        return
    pool = _user_db_pools.setdefault(user_id, [])
    _user_db_pools.move_to_end(user_id)  # 归还即最近使用
    if len(pool) < USER_DB_POOL_SIZE:
        pool.append(db)
    else:
        await db.close()
    # 超容量按 LRU 淘汰最久未用用户的整池
    await _evict_user_pools_if_needed()


@asynccontextmanager
async def _db_transaction(user_id: str):
    """每用户文档库事务上下文（PG 或 SQLite）。PG 模式下 user_id 用于 WHERE 过滤。"""
    from pg_adapter import is_pg
    db = await _get_db(user_id)
    with span("db.transaction", user=user_id):
        try:
            if is_pg():
                async with db.transaction():
                    yield db
            else:
                yield db
                await db.commit()
        except Exception:
            if not is_pg():
                await db.rollback()
            raise
        finally:
            await _put_db(user_id, db)


def _delete_unowned_files(unowned_db: Path):
    """删除 _unowned 库及其 WAL/SHM。"""
    for p in (unowned_db, unowned_db.with_name(unowned_db.name + "-wal"), unowned_db.with_name(unowned_db.name + "-shm")):
        try:
            if p.exists(): p.unlink()
        except Exception:
            pass


async def _migrate_legacy_db():
    """一次性迁移：把旧单库 docs.db（含 users+documents）拆分为每用户库 + 共享注册库。幂等。"""
    legacy = Path(DOC_DB_PATH)
    users_root = _data_dir() / "users"
    # 已有用户目录 → 视为已迁移
    try:
        if users_root.exists() and any(users_root.iterdir()):
            return
    except Exception:
        pass
    if not legacy.exists():
        return
    try:
        src = await aiosqlite.connect(str(legacy))
        src.row_factory = aiosqlite.Row
        names = {r["name"] for r in await (await src.execute("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "documents" not in names:
            await src.close(); return
        users_rows = []
        if "users" in names:
            users_rows = await (await src.execute("SELECT * FROM users")).fetchall()
        docs = await (await src.execute("SELECT * FROM documents")).fetchall()
        await src.close()
        if not docs and not users_rows:
            return
        cols = list(docs[0].keys()) if docs else []
        col_list = ",".join(cols)
        placeholders = ",".join("?" for _ in cols)
        by_user: dict[str, list] = {}
        share_routes = []
        for d in docs:
            uid = d["user_id"] or "_unowned"
            by_user.setdefault(uid, []).append(d)
            if d["share_code"]:
                share_routes.append((d["share_code"], uid, d["doc_id"]))
        for uid, rows in by_user.items():
            async with _db_transaction(uid) as db:
                for d in rows:
                    await db.execute(f"INSERT OR IGNORE INTO documents ({col_list}) VALUES ({placeholders})", [d[c] for c in cols])
        async with _registry_transaction() as rdb:
            for u in users_rows:
                await rdb.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, password_hash, created_at) VALUES (?,?,?,?)",
                    (u["user_id"], u["username"], u["password_hash"], u["created_at"]),
                )
            for sc, uid, did in share_routes:
                await rdb.execute(
                    "INSERT OR IGNORE INTO shares (share_code, owner_user_id, doc_id, created_at) VALUES (?,?,?,?)",
                    (sc, uid, did, _utcnow_iso()),
                )
        # 旧库重命名为备份，不再用作主库
        backup = legacy.with_name(legacy.name + ".pre-split")
        try:
            if backup.exists(): backup.unlink()
            legacy.rename(backup)
        except Exception as e:
            logger.warning("旧库重命名失败（可手动删除）: %s", e)
        logger.info("迁移完成：%d 篇文档 -> %d 个用户库", len(docs), len(by_user))
    except Exception as e:
        logger.warning("迁移旧库失败（跳过）: %s", e)


async def _claim_unowned_docs(user_id: str):
    """注册时把迁移期未归属（_unowned）的旧文档认领到新用户库（保留旧版首个用户认领语义）。"""
    unowned = _data_dir() / "users" / "_unowned" / "docs.db"
    if not unowned.exists():
        return
    src = await aiosqlite.connect(str(unowned))
    src.row_factory = aiosqlite.Row
    docs = await (await src.execute("SELECT * FROM documents")).fetchall()
    await src.close()
    if not docs:
        _delete_unowned_files(unowned)
        return
    cols = list(docs[0].keys())
    col_list = ",".join(cols)
    placeholders = ",".join("?" for _ in cols)
    share_codes = [d["share_code"] for d in docs if d["share_code"]]
    async with _db_transaction(user_id) as db:
        for d in docs:
            await db.execute(f"INSERT OR IGNORE INTO documents ({col_list}) VALUES ({placeholders})", [d[c] for c in cols])
        # 认领：把这些文档的 user_id 改为当前用户
        await db.execute("UPDATE documents SET user_id=? WHERE user_id='' OR user_id='_unowned'", (user_id,))
    # 更新分享路由属主
    if share_codes:
        async with _registry_transaction() as rdb:
            for sc in share_codes:
                await rdb.execute("UPDATE shares SET owner_user_id=? WHERE share_code=?", (user_id, sc))
    _delete_unowned_files(unowned)
    logger.info("用户 %s 认领 %d 篇未归属旧文档", user_id, len(docs))


async def _seed_examples(user_id: str):
    """为新用户在云端根目录创建 examples 文件夹及各特性示例文档。

    仅在用户库为空（无任何未软删文档）时播种，保证幂等：新用户获示例，
    已有内容或迁移认领了旧文档的用户不受影响。
    """
    from seed_examples import EXAMPLES
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT COUNT(*) AS c FROM documents WHERE deleted_at IS NULL"
        )).fetchone()
        if row and row["c"] > 0:
            return
        now = _utcnow_iso()
        # examples 文件夹（path='' 表示根目录）
        folder_id = secrets.token_urlsafe(12)
        await db.execute(
            "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, user_id) "
            "VALUES (?, ?, '', ?, ?, 'folder', '', ?)",
            (folder_id, "examples", now, now, user_id),
        )
        for ex in EXAMPLES:
            doc_id = secrets.token_urlsafe(12)
            await db.execute(
                "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, user_id) "
                "VALUES (?, ?, ?, ?, ?, 'file', 'examples', ?)",
                (doc_id, ex["title"], ex["content"], now, now, user_id),
            )
    logger.info("为新用户播种示例文档 user=%s 数量=%d", user_id, len(EXAMPLES))


def _generate_share_code(length: int = SHARE_CODE_LENGTH) -> str:
    import secrets
    chars = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==================== 实时协同（WebSocket 房间广播）====================
# y-websocket 兼容：同 room 的连接互相广播二进制消息，实现 Yjs 协同编辑。
# room 命名：team:doc（团队文档）或 personal:user:doc（个人文档）。
_collab_rooms: dict[str, set] = {}
_collab_presence: dict[str, dict] = {}  # room -> {uid: username}


async def _collab_broadcast_text(room: str, text: str, exclude=None):
    """本房间本进程内广播文本消息（可选排除某个连接）。"""
    conns = _collab_rooms.get(room)
    if not conns:
        return
    for other in list(conns):
        if other is exclude:
            continue
        try:
            await other.send_text(text)
        except Exception:
            pass


async def _collab_broadcast_bytes(room: str, data: bytes, exclude=None):
    """本房间本进程内广播二进制（Yjs update）。"""
    conns = _collab_rooms.get(room)
    if not conns:
        return
    for other in list(conns):
        if other is exclude:
            continue
        try:
            await other.send_bytes(data)
        except Exception:
            pass


async def _collab_save_state(room: str, state_b64: str):
    """持久化最新 Yjs 快照（全量状态，客户端提交）。
    P2-12：快照体积超 COLLAB_MAX_SNAPSHOT_BYTES 时拒绝持久化（保护 DB/广播）。"""
    if len(state_b64) > COLLAB_MAX_SNAPSHOT_BYTES:
        logger.warning("协同快照超限拒绝持久化 room=%s size=%d cap=%d", room, len(state_b64), COLLAB_MAX_SNAPSHOT_BYTES)
        return False
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO collab_state (room, state, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(room) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
            (room, state_b64, now),
        )
    return True


async def _collab_load_state(room: str) -> Optional[str]:
    """读取已持久化的 Yjs 快照（base64），无则 None。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT state FROM collab_state WHERE room=?", (room,))).fetchone()
    return row["state"] if row else None


async def _collab_append_update(room: str, data: bytes):
    """落库一条 Yjs 增量更新（按 room 内自增 seq）。失败仅告警，不影响实时广播。
    P2-12：保留上限 COLLAB_MAX_UPDATES_PER_ROOM，超限按 seq 删最旧，防无界增长。"""
    try:
        now = _utcnow_iso()
        async with _registry_transaction() as db:
            row = await (await db.execute("SELECT COALESCE(MAX(seq),0) AS m FROM collab_updates WHERE room=?", (room,))).fetchone()
            seq = (row["m"] if row else 0) + 1
            await db.execute("INSERT INTO collab_updates (room, seq, data, ts) VALUES (?,?,?,?)",
                             (room, seq, data, now))
            # 保留上限：删最旧增量，限制单 room collab_updates 体积
            if COLLAB_MAX_UPDATES_PER_ROOM > 0:
                cap_row = await (await db.execute(
                    "SELECT seq FROM collab_updates WHERE room=? ORDER BY seq DESC LIMIT 1 OFFSET ?",
                    (room, COLLAB_MAX_UPDATES_PER_ROOM),
                )).fetchone()
                if cap_row:
                    await db.execute("DELETE FROM collab_updates WHERE room=? AND seq<=?", (room, cap_row["seq"]))
    except Exception as e:
        logger.warning("落库协同增量失败 room=%s: %s", room, e)


async def _collab_load_updates(room: str) -> list:
    """读取某 room 的全部待 apply 增量（按 seq 升序，返回 bytes 列表）。"""
    try:
        async with _registry_transaction() as db:
            rows = await (await db.execute(
                "SELECT data FROM collab_updates WHERE room=? ORDER BY seq ASC", (room,)
            )).fetchall()
    except Exception:
        return []
    return [r["data"] for r in rows]


async def _collab_clear_updates(room: str):
    """全量快照已包含全部状态 → 清空该 room 的增量。"""
    try:
        async with _registry_transaction() as db:
            await db.execute("DELETE FROM collab_updates WHERE room=?", (room,))
    except Exception:
        pass


