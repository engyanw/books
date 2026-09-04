# ==================== OAuth2 开放 API（第三方应用接入）====================
# 流程：用户注册客户端(client_id/secret) → 第三方引导用户到 /oauth/authorize
# 授权后回调带 code → 第三方用 code+secret 换 /oauth/token 得 access_token（复用 API token
# 校验，可访问 /api/docs 等），令牌带 scope（docs:read/docs:write）记录于 oauth_token_scopes。
_SUPPORTED_OAUTH_SCOPES = {"docs:read", "docs:write", "openid"}


class OAuthClientCreate(BaseModel):
    name: str
    redirect_uris: list[str] = []
    scopes: list[str] = []


@app.post("/api/oauth/clients", status_code=201)
async def create_oauth_client(req: OAuthClientCreate, user_id: str = Depends(_require_user)):
    """注册第三方应用，返回 client_id + 明文 secret（仅一次）。"""
    raw_secret = "cs_" + secrets.token_urlsafe(32)
    cid = "c-" + secrets.token_urlsafe(10)
    now = _utcnow_iso()
    sc = ",".join(s for s in req.scopes if s in _SUPPORTED_OAUTH_SCOPES)
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO oauth_clients (client_id, client_secret_hash, name, owner_user_id, redirect_uris, scopes, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (cid, _hash_api_token(raw_secret), (req.name or "").strip()[:64] or "app",
             user_id, "\n".join(req.redirect_uris), sc, now),
        )
    await _audit(user_id, None, "oauth.client.create", "client", cid, req.name)
    return {"client_id": cid, "client_secret": raw_secret, "name": req.name,
            "redirect_uris": req.redirect_uris, "scopes": sc.split(",") if sc else []}


@app.get("/api/oauth/clients")
async def list_oauth_clients(user_id: str = Depends(_require_user)):
    """列出我注册的 OAuth 客户端（不含 secret）。"""
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT client_id, name, redirect_uris, scopes, created_at FROM oauth_clients WHERE owner_user_id=? ORDER BY created_at DESC",
            (user_id,),
        )).fetchall()
    return {"items": [
        {"client_id": r["client_id"], "name": r["name"],
         "redirect_uris": (r["redirect_uris"] or "").split("\n") if r["redirect_uris"] else [],
         "scopes": (r["scopes"] or "").split(",") if r["scopes"] else [],
         "created_at": r["created_at"]}
        for r in rows
    ]}


@app.delete("/api/oauth/clients/{cid}")
async def delete_oauth_client(cid: str, user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT owner_user_id FROM oauth_clients WHERE client_id=?", (cid,))).fetchone()
        if not row:
            raise HTTPException(404, "客户端不存在")
        if row["owner_user_id"] != user_id:
            raise HTTPException(403, "无权删除")
        await db.execute("DELETE FROM oauth_clients WHERE client_id=?", (cid,))
        await db.execute("DELETE FROM oauth_token_scopes WHERE client_id=?", (cid,))
    await _audit(user_id, None, "oauth.client.delete", "client", cid, None)
    return {"ok": True}


@app.get("/oauth/authorize")
async def oauth_authorize(
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    scope: str = "",
    state: str = "",
    # 资源所有者凭据：简化授权码流（Web 前端可改为已有会话）。生产建议改为读会话。
    user_token: str = "",
):
    """授权端点：校验客户端 + 回调地址，签发一次性授权码 code。

    本实现接受已登录用户的会话/API token（user_token）代表所有者同意授权，
    适用于脚本/集成测试场景；浏览器场景可由前端先用会话调此端点。
    """
    if response_type != "code":
        raise HTTPException(400, "仅支持 response_type=code")
    if not client_id or not redirect_uri:
        raise HTTPException(400, "client_id 与 redirect_uri 必填")
    async with _registry_transaction() as db:
        client = await (await db.execute(
            "SELECT client_id, redirect_uris, scopes FROM oauth_clients WHERE client_id=?", (client_id,)
        )).fetchone()
        if not client:
            raise HTTPException(404, "客户端不存在")
        allowed = (client["redirect_uris"] or "").split("\n")
        if redirect_uri not in allowed:
            raise HTTPException(400, "redirect_uri 未登记")
    # 解析所有者
    payload = _parse_token(user_token)
    uid = None
    if payload and payload.get("uid") and not await _is_token_revoked(user_token):
        uid = payload["uid"]
    else:
        uid2 = await _api_token_user(user_token)
        uid = uid2
    if not uid:
        raise HTTPException(401, "需要所有者登录态以授权")
    # 过滤 scope
    req_scopes = [s for s in (scope or "").split() if s in _SUPPORTED_OAUTH_SCOPES]
    code = "oc_" + secrets.token_urlsafe(24)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO oauth_codes (code, client_id, user_id, redirect_uri, scope, created_at, used) VALUES (?,?,?,?,?,?,0)",
            (code, client_id, uid, redirect_uri, " ".join(req_scopes), now),
        )
    from urllib.parse import urlencode
    params = {"code": code}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}{urlencode(params)}")


@app.post("/oauth/token")
async def oauth_token(req: Request):
    """令牌端点：授权码换 access_token（复用 API token 体系，附 scope）。"""
    form = await req.form()
    grant_type = (form.get("grant_type") or "").strip()
    cid = (form.get("client_id") or "").strip()
    csecret = (form.get("client_secret") or "").strip()
    code = (form.get("code") or "").strip()
    redirect_uri = (form.get("redirect_uri") or "").strip()
    if grant_type != "authorization_code":
        raise HTTPException(400, "仅支持 authorization_code")
    async with _registry_transaction() as db:
        client = await (await db.execute(
            "SELECT client_id, client_secret_hash FROM oauth_clients WHERE client_id=?", (cid,)
        )).fetchone()
        if not client or client["client_secret_hash"] != _hash_api_token(csecret):
            raise HTTPException(401, "客户端认证失败")
        coderow = await (await db.execute(
            "SELECT user_id, redirect_uri, scope, used, created_at FROM oauth_codes WHERE code=?", (code,)
        )).fetchone()
        if not coderow:
            raise HTTPException(400, "授权码无效")
        if coderow["used"]:
            raise HTTPException(400, "授权码已使用")
        if coderow["redirect_uri"] != redirect_uri:
            raise HTTPException(400, "redirect_uri 不一致")
        await db.execute("UPDATE oauth_codes SET used=1 WHERE code=?", (code,))
        # 签发访问令牌（落入 api_tokens，_require_user 即可识别）
        raw = "pat_" + secrets.token_urlsafe(32)
        tid = "tok-" + secrets.token_urlsafe(8)
        now = _utcnow_iso()
        await db.execute(
            "INSERT INTO api_tokens (id, user_id, name, token_hash, created_at) VALUES (?,?,?,?,?)",
            (tid, coderow["user_id"], f"oauth:{cid}", _hash_api_token(raw), now),
        )
        await db.execute(
            "INSERT INTO oauth_token_scopes (token_hash, client_id, scope, created_at) VALUES (?,?,?,?)",
            (_hash_api_token(raw), cid, coderow["scope"] or "", now),
        )
    return {"access_token": raw, "token_type": "Bearer", "scope": coderow["scope"] or "",
            "expires_in": 0}  # PAT 无过期（可由吊销名单失效）


async def _oauth_token_scopes(token: str) -> str:
    """查询某 token 的 OAuth scope（非 OAuth 令牌返回空串）。"""
    try:
        h = _hash_api_token(token)
        async with _registry_transaction() as db:
            row = await (await db.execute("SELECT scope FROM oauth_token_scopes WHERE token_hash=?", (h,))).fetchone()
        return (row["scope"] if row else "") or ""
    except Exception:
        return ""


def _require_scope(required: str):
    """依赖：OAuth 令牌需具备 required scope；非 OAuth 令牌(PAT/会话)默认放行。

    PAT/会话由用户在控制台签发，等同完全权限；OAuth 第三方令牌受限作用域。
    """
    async def _dep(request: Request) -> str:
        uid = await _require_user(request)
        token = request.headers.get("Authorization", "")
        token = token.removeprefix("Bearer ").strip() if token.lower().startswith("bearer ") else ""
        scopes = (await _oauth_token_scopes(token)).split()
        if scopes and required not in scopes:
            raise HTTPException(403, f"OAuth 令牌缺少 scope: {required}")
        return uid
    return _dep


# 开放 API 路由清单（供第三方集成发现）：path → method + 所需 scope
OPEN_API_ROUTES = [
    {"path": "/api/docs", "method": "GET", "scope": "docs:read", "desc": "列出当前用户文档"},
    {"path": "/api/docs", "method": "POST", "scope": "docs:write", "desc": "创建文档"},
    {"path": "/api/docs/{doc_id}", "method": "GET", "scope": "docs:read", "desc": "获取文档内容"},
    {"path": "/api/docs/{doc_id}", "method": "PUT", "scope": "docs:write", "desc": "更新文档"},
    {"path": "/api/search", "method": "GET", "scope": "docs:read", "desc": "全文检索"},
]


@lru_cache(maxsize=1)
def _oauth_open_route_matchers() -> list:
    """预编译 OPEN_API_ROUTES 的 (method, regex) 匹配器：{param} 段匹配 [^/]+。"""
    import re as _re
    out = []
    for r in OPEN_API_ROUTES:
        segs = []
        for seg in r["path"].split("/"):
            if seg.startswith("{") and seg.endswith("}"):
                segs.append(r"[^/]+")
            else:
                segs.append(_re.escape(seg))
        out.append((r["method"].upper(), _re.compile("^" + "/".join(segs) + "$")))
    return out


def _oauth_route_allowed(method: str, path: str) -> bool:
    """(method, path) 是否落在 OPEN_API_ROUTES 声明的开放面。"""
    m = method.upper()
    for rmethod, rx in _oauth_open_route_matchers():
        if rmethod == m and rx.match(path):
            return True
    return False


@app.get("/api/v1/openapi")
async def open_api_discovery():
    """开放 API 元信息：列出可被第三方 OAuth 令牌访问的路由及其所需 scope。"""
    return {"name": "md-editor-open-api", "version": "1", "auth": "OAuth2 Bearer",
            "authorize": "/oauth/authorize", "token": "/oauth/token",
            "scopes": sorted(_SUPPORTED_OAUTH_SCOPES - {"openid"}),
            "routes": OPEN_API_ROUTES}


# ==================== 可观测性：系统指标 ====================
@app.get("/api/admin/metrics")
async def admin_metrics(user_id: str = Depends(_require_user)):
    """系统级指标（仅管理员）：用户/团队/文档/AI 调用计数。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        users = (await (await db.execute("SELECT COUNT(*) AS c FROM users")).fetchone())["c"]
        teams = (await (await db.execute("SELECT COUNT(*) AS c FROM teams")).fetchone())["c"]
        api_calls = (await (await db.execute("SELECT COUNT(*) AS c FROM ai_usage")).fetchone())["c"]
        audit = (await (await db.execute("SELECT COUNT(*) AS c FROM audit_log")).fetchone())["c"]
        tokens = (await (await db.execute("SELECT COUNT(*) AS c FROM api_tokens")).fetchone())["c"]
    # 文档数需遍历每用户库；给出近似（按用户库文件计数）
    doc_count = 0
    users_dir = _data_dir() / "users"
    if users_dir.exists():
        for udb in users_dir.glob("*/docs.db"):
            try:
                import sqlite3 as _s
                conn = _s.connect(str(udb)); conn.row_factory = _s.Row
                doc_count += conn.execute("SELECT COUNT(*) FROM documents WHERE deleted_at IS NULL").fetchone()[0]
                conn.close()
            except Exception:
                pass
    return {"users": users, "teams": teams, "docs": doc_count,
            "ai_calls_total": api_calls, "audit_entries": audit, "api_tokens": tokens}


# ==================== 跨团队全文搜索 ====================
async def _search_granted(user_id, like, fts_q, limit, results):
    """P1-5：搜索被他人授予（doc_acl）的文档。
    PG 共享库：单次 JOIN（documents + doc_grants，按 grantee 过滤 + 过期裁剪）。
    SQLite per-user：按属主分组打开各属主库，限制 doc_id IN (...) 搜索授予的文档。"""
    now = _utcnow_iso()
    from pg_adapter import is_pg
    if is_pg():
        async with _registry_transaction() as rdb:
            rows = await (await rdb.execute(
                "SELECT d.doc_id, d.title, substr(d.content,1,80) AS preview, d.path, d.kind, d.updated_at "
                "FROM documents d JOIN doc_grants g ON g.doc_id=d.doc_id "
                "WHERE g.grantee_user_id=? AND d.deleted_at IS NULL "
                "AND (d.title ILIKE ? OR d.content ILIKE ?) "
                "AND (g.expires_at IS NULL OR g.expires_at > ?) "
                "ORDER BY d.updated_at DESC LIMIT ?",
                (user_id, like, like, now, limit),
            )).fetchall()
        for r in rows:
            results.append({"doc_id": r["doc_id"], "title": r["title"], "preview": r["preview"] or "",
                            "path": r["path"] or "", "kind": r["kind"] or "file", "team_id": None,
                            "team_name": None, "scope": "granted", "updated_at": r["updated_at"]})
        return
    # SQLite per-user：按属主分组
    async with _registry_transaction() as rdb:
        grants = await (await rdb.execute(
            "SELECT DISTINCT doc_id, owner_user_id FROM doc_grants WHERE grantee_user_id=? "
            "AND (expires_at IS NULL OR expires_at > ?)", (user_id, now)
        )).fetchall()
    by_owner = {}
    for g in grants:
        by_owner.setdefault(g["owner_user_id"], []).append(g["doc_id"])
    for owner_uid, doc_ids in by_owner.items():
        ph = ",".join("?" * len(doc_ids))
        try:
            async with _db_transaction(owner_uid) as odb:
                try:
                    rows = await (await odb.execute(
                        f"SELECT d.doc_id, d.title, substr(d.content,1,80) AS preview, d.path, d.kind, d.updated_at "
                        f"FROM documents d JOIN documents_fts f ON d.doc_id=f.doc_id "
                        f"WHERE d.deleted_at IS NULL AND d.doc_id IN ({ph}) "
                        f"AND documents_fts MATCH ? ORDER BY d.updated_at DESC LIMIT ?",
                        (*doc_ids, fts_q, limit),
                    )).fetchall()
                except Exception:
                    rows = await (await odb.execute(
                        f"SELECT doc_id, title, substr(content,1,80) AS preview, path, kind, updated_at "
                        f"FROM documents WHERE deleted_at IS NULL AND doc_id IN ({ph}) "
                        f"AND (title LIKE ? OR content LIKE ?) ORDER BY updated_at DESC LIMIT ?",
                        (*doc_ids, like, like, limit),
                    )).fetchall()
                for r in rows:
                    results.append({"doc_id": r["doc_id"], "title": r["title"], "preview": r["preview"] or "",
                                    "path": r["path"] or "", "kind": r["kind"] or "file", "team_id": None,
                                    "team_name": None, "scope": "granted", "updated_at": r["updated_at"]})
        except Exception as e:
            logger.warning("属主库 ACL 搜索失败 owner=%s: %s", owner_uid, e)


@app.get("/api/search")
async def global_search(q: str = "", limit: int = 50, user_id: str = Depends(_require_scope("docs:read"))):
    """跨空间全文搜索：优先用 FTS5 MATCH（性能优），回退 LIKE。
    权限由团队成员身份保证（只搜有权访问的团队）。"""
    q = (q or "").strip()
    if not q:
        return {"items": []}
    limit = max(1, min(limit, 200))
    like = f"%{q}%"
    # 中文分词：用同一 tokenizer 把查询切成 token，拼成 FTS5 AND 查询（每 token 加引号防注入）
    fts_q = _fts_build_query(q)
    results = []

    async def _search_db(db, scope, team_id, team_name, owner_uid=None):
        """在给定连接上执行搜索：PG 用 ILIKE（pg_trgm GIN 加速、大小写不敏感）；
        SQLite 优先 FTS5 MATCH（中文分词+相关性），失败回退 LIKE。
        owner_uid（个人库）用于 PG 共享库模式下按 user_id 收敛，防跨用户泄露。"""
        from pg_adapter import is_pg
        owner_clause = "AND user_id=?" if (is_pg() and owner_uid) else ""
        owner_params = [owner_uid] if (is_pg() and owner_uid) else []
        if is_pg():
            # pg_trgm 的 similarity() 提供相关性评分（三元组相似度，CJK 友好）；
            # GIN 索引加速 ILIKE 命中，similarity() 排序让最相关的文档靠前（对齐 SQLite FTS5 bm25 体验）。
            try:
                rows = await (await db.execute(
                    "SELECT doc_id, title, substr(content,1,80) AS preview, path, kind, updated_at, "
                    "GREATEST(similarity(title, ?), similarity(content, ?)) AS rel "
                    "FROM documents WHERE deleted_at IS NULL AND (title ILIKE ? OR content ILIKE ?) "
                    f"{owner_clause} ORDER BY rel DESC, updated_at DESC LIMIT ?",
                    (q, q, like, like, *owner_params, limit),
                )).fetchall()
            except Exception:
                # pg_trgm 扩展缺失时回退到无相关性排序的 ILIKE（仍可用）
                rows = await (await db.execute(
                    "SELECT doc_id, title, substr(content,1,80) AS preview, path, kind, updated_at, 0 AS rel "
                    "FROM documents WHERE deleted_at IS NULL AND (title ILIKE ? OR content ILIKE ?) "
                    f"{owner_clause} ORDER BY updated_at DESC LIMIT ?",
                    (like, like, *owner_params, limit),
                )).fetchall()
        else:
            try:
                rows = await (await db.execute(
                    "SELECT d.doc_id, d.title, substr(d.content,1,80) AS preview, d.path, d.kind, d.updated_at, "
                    "bm25(documents_fts, 0.0, 5.0, 1.0) AS rel "
                    "FROM documents d JOIN documents_fts f ON d.doc_id = f.doc_id "
                    "WHERE d.deleted_at IS NULL AND documents_fts MATCH ? "
                    "ORDER BY bm25(documents_fts, 0.0, 5.0, 1.0) ASC LIMIT ?",
                    (fts_q, limit),
                )).fetchall()
            except Exception:
                rows = await (await db.execute(
                    "SELECT doc_id, title, substr(content,1,80) AS preview, path, kind, updated_at, 0 AS rel "
                    "FROM documents WHERE deleted_at IS NULL AND (title LIKE ? OR content LIKE ?) "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (like, like, limit),
                )).fetchall()
        for r in rows:
            # 统一为"越大越相关"：FTS5 bm25 为负（越负越相关）取绝对值；
            # PG similarity 与 LIKE 回退的 0 已是"越大越相关"，abs 不改变其语义。
            results.append({"doc_id": r["doc_id"], "title": r["title"], "preview": r["preview"] or "",
                            "path": r["path"] or "", "kind": r["kind"] or "file", "team_id": team_id,
                            "team_name": team_name, "scope": scope, "updated_at": r["updated_at"],
                            "relevance": abs(r["rel"] or 0.0)})

    # 1) 个人库
    with span("search.global", q=q, limit=limit):
        try:
            async with _db_transaction(user_id) as db:
                await _search_db(db, "personal", None, None, owner_uid=user_id)
                # 附件全文搜索（同库 attachments_fts）：命中附件内容/文件名
                try:
                    arows = await (await db.execute(
                        "SELECT a.id, a.doc_id, a.filename, a.storage_url, substr(a.extracted_text,1,80) AS preview, a.created_at, "
                        "bm25(attachments_fts, 0.0, 1.0, 2.0, 4.0) AS rel "
                        "FROM attachments a JOIN attachments_fts f ON a.id = CAST(f.attachment_id AS INTEGER) "
                        "WHERE attachments_fts MATCH ? ORDER BY bm25(attachments_fts, 0.0, 1.0, 2.0, 4.0) ASC LIMIT ?",
                        (fts_q, limit),
                    )).fetchall()
                except Exception:
                    arows = await (await db.execute(
                        "SELECT id, doc_id, filename, storage_url, substr(extracted_text,1,80) AS preview, created_at, 0 AS rel "
                        "FROM attachments WHERE filename LIKE ? OR extracted_text LIKE ? ORDER BY created_at DESC LIMIT ?",
                        (like, like, limit),
                    )).fetchall()
                for a in arows:
                    results.append({"doc_id": a["doc_id"] or "", "title": a["filename"], "filename": a["filename"],
                                    "preview": a["preview"] or "", "path": a["storage_url"],
                                    "kind": "attachment", "team_id": None, "team_name": None,
                                    "scope": "personal", "updated_at": a["created_at"],
                                    "attachment_id": a["id"], "relevance": abs(a["rel"] or 0.0)})
        except Exception as e:
            logger.warning("个人库搜索失败 user=%s: %s", user_id, e)
        # 2) 团队库
        try:
            async with _registry_transaction() as rdb:
                team_rows = await (await rdb.execute(
                    "SELECT m.team_id, t.name FROM team_members m JOIN teams t ON t.team_id=m.team_id WHERE m.user_id=?",
                    (user_id,),
                )).fetchall()
        except Exception:
            team_rows = []
        for tr in team_rows:
            tid = tr["team_id"]; tname = tr["name"]
            try:
                async with _team_db_transaction(tid) as db:
                    await _search_db(db, "team", tid, tname)
            except Exception as e:
                logger.warning("团队库搜索失败 team=%s: %s", tid, e)
        # 3) ACL 授予的文档（他人授予 read/write 的文档，跨用户可见）
        try:
            await _search_granted(user_id, like, fts_q, limit, results)
        except Exception as e:
            logger.warning("ACL 授权文档搜索失败 user=%s: %s", user_id, e)
        # 合并、去重、按相关性（降序）+ 更新时间（降序）排序、截断
        seen = set()
        deduped = []
        for r in sorted(results, key=lambda x: (x.get("relevance") or 0.0, x.get("updated_at") or ""), reverse=True):
            key = (r.get("team_id"), r["doc_id"], r.get("kind"), r.get("attachment_id"))
            if key in seen:
                continue
            seen.add(key)
            # relevance 仅供排序，不回传给前端（内部字段）
            r.pop("relevance", None)
            deduped.append(r)
            if len(deduped) >= limit:
                break
        return {"items": deduped}


# ==================== 文档模板库 ====================
class TemplateCreateRequest(BaseModel):
    name: str
    content: str = ""
    category: str = ""
    kind: str = ""  # E6：场景类型 rfc/design-doc/runbook/adr 等
    variables: list[str] = []  # E6：可插值的变量名列表
    parent_id: Optional[str] = None  # P2-11：继承自父模板
    org_managed: bool = False  # P2-11：组织级受管模板（需审批）


@app.get("/api/templates")
async def list_templates(team_id: Optional[str] = None, kind: Optional[str] = None, user_id: str = Depends(_require_user)):
    """列出模板。team_id 指定时返回该团队模板（需成员）；否则返回个人模板。kind 过滤场景类型。"""
    if team_id:
        await _require_team_role(team_id, user_id, "viewer")
        async with _registry_transaction() as db:
            rows = await (await db.execute(
                "SELECT id, name, content, category, kind, variables_json, created_by, created_at, version, status, parent_id, org_managed FROM templates WHERE team_id=? "
                + ("AND kind=?" if kind else "") + " ORDER BY created_at DESC",
                ([team_id, kind] if kind else [team_id]),
            )).fetchall()
    else:
        async with _registry_transaction() as db:
            rows = await (await db.execute(
                "SELECT id, name, content, category, kind, variables_json, created_by, created_at, version, status, parent_id, org_managed FROM templates "
                "WHERE user_id=? AND team_id IS NULL " + ("AND kind=?" if kind else "") + " ORDER BY created_at DESC",
                ([user_id, kind] if kind else [user_id]),
            )).fetchall()
    return {"items": [
        {"id": r["id"], "name": r["name"], "content": r["content"],
         "category": r["category"], "kind": r["kind"] or "", "variables": _safe_json_loads(r["variables_json"], []),
         "created_by": r["created_by"], "created_at": r["created_at"],
         "version": r["version"], "status": r["status"], "parent_id": r["parent_id"],
         "org_managed": bool(r["org_managed"])}
        for r in rows
    ]}


def _safe_json_loads(s, default):
    try:
        import json as _j
        return _j.loads(s) if s else default
    except Exception:
        return default


@app.post("/api/templates", status_code=201)
async def create_template(req: TemplateCreateRequest, team_id: Optional[str] = None, user_id: str = Depends(_require_user)):
    """创建模板。team_id query 参数指定则创建团队模板(需 admin)。
    P2-11：org_managed=true 创建受管模板（团队 admin），起始状态 draft，需 submit→approve 审批。
    parent_id 指定父模板以继承。"""
    name = (req.name or "").strip()
    if not name or len(name) > 128:
        raise HTTPException(400, "模板名必填且 ≤128 字符")
    org_managed = 1 if req.org_managed else 0
    if team_id:
        await _require_team_role(team_id, user_id, "admin")
    if org_managed and not team_id:
        raise HTTPException(400, "受管模板须在团队（组织）作用域下创建")
    parent_id = (req.parent_id or "").strip() or None
    if parent_id:
        async with _registry_transaction() as db:
            prow = await (await db.execute("SELECT id FROM templates WHERE id=?", (parent_id,))).fetchone()
        if not prow:
            raise HTTPException(404, "父模板不存在")
    tid = secrets.token_urlsafe(10)
    now = _utcnow_iso()
    import json as _j
    var_json = _j.dumps([v.strip() for v in (req.variables or []) if v.strip()], ensure_ascii=False)
    status = "draft" if org_managed else "active"
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO templates (id, user_id, team_id, name, content, category, kind, variables_json, created_by, created_at, version, status, parent_id, org_managed, updated_by, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?)",
            (tid, user_id, team_id, name, req.content, (req.category or "").strip()[:64],
             (req.kind or "").strip()[:32], var_json, user_id, now, status, parent_id, org_managed, user_id, now),
        )
    await _audit(user_id, team_id, "template.create", "template", tid, name)
    return {"id": tid, "name": name, "created_at": now, "version": 1, "status": status, "org_managed": bool(org_managed)}


@app.post("/api/templates/{tid}/instantiate", status_code=201)
async def instantiate_template(tid: str, payload: dict = Body(...), user_id: str = Depends(_require_user)):
    """用模板生成新文档：对模板 content 做 Jinja2 变量插值（{{ var }}）后创建文档。
    body: {variables: {key: value, ...}, title?: "..."}（团队模板需成员权限）。
    P2-11 治理门禁：deprecated 模板禁止实例化(410)；受管(org_managed)且未审批
    (status 不在 approved/active)禁止实例化(409)。parent_id 指定时继承父模板——
    先渲染父链再拼接子模板内容（带环检测+深度上限）。"""
    from jinja2 import Environment, BaseLoader, StrictUndefined
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT name, content, kind, variables_json, user_id, team_id, version, status, parent_id, org_managed FROM templates WHERE id=?", (tid,)
        )).fetchone()
    if not row:
        raise HTTPException(404, "模板不存在")
    if row["team_id"]:
        await _require_team_role(row["team_id"], user_id, "member")
    elif row["user_id"] != user_id:
        # 个人模板：仅本人可实例化
        raise HTTPException(403, "只能实例化自己的模板")
    # 治理门禁
    if row["status"] == "deprecated":
        raise HTTPException(410, "模板已废弃，禁止实例化")
    if row["org_managed"] and row["status"] not in ("approved", "active"):
        raise HTTPException(409, "受管模板未通过审批，禁止实例化")
    variables = payload.get("variables") or {}
    title = (payload.get("title") or row["name"]).strip()
    env = Environment(loader=BaseLoader(), autoescape=False, keep_trailing_newline=True)
    # 继承：收集父链（自顶向下），依次渲染并拼接；带环检测与深度上限
    chain_content = []
    if row["parent_id"]:
        seen = {tid}
        cur_parent = row["parent_id"]
        depth = 0
        while cur_parent and cur_parent not in seen and depth < 8:
            seen.add(cur_parent)
            depth += 1
            async with _registry_transaction() as db:
                prow = await (await db.execute(
                    "SELECT content, parent_id FROM templates WHERE id=?", (cur_parent,)
                )).fetchone()
            if not prow:
                break
            try:
                chain_content.append(env.from_string(prow["content"] or "").render(**variables))
            except Exception as e:
                raise HTTPException(400, f"父模板变量插值失败: {e}")
            cur_parent = prow["parent_id"]
    # 严格插值：模板声明了变量但调用未提供 → 报错，避免静默产出占位符
    try:
        child_rendered = env.from_string(row["content"] or "").render(**variables)
    except Exception as e:
        raise HTTPException(400, f"变量插值失败: {e}")
    rendered = "\n\n".join([p for p in chain_content if p and p.strip()] + ([child_rendered] if child_rendered is not None else []))
    # 创建文档（个人库）
    doc_id = "doc-" + secrets.token_urlsafe(10)
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        await db.execute(
            "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, user_id) VALUES (?,?,?,?,?,'file','',?)",
            (doc_id, title[:200], rendered, now, now, user_id),
        )
    await _audit(user_id, row["team_id"], "template.instantiate", "template", tid, f"->doc={doc_id}")
    return {"doc_id": doc_id, "title": title, "kind": row["kind"] or "", "version": row["version"]}


# E6：内置场景模板骨架（RFC/design-doc/runbook/ADR），含 Jinja2 变量占位
_BUILTIN_TEMPLATES = {
    "rfc": {
        "name": "RFC 草案", "kind": "rfc",
        "variables": ["title", "author", "date", "status", "summary", "motivation", "design", "risks"],
        "content": """# RFC: {{ title }}

- 作者：{{ author }}
- 日期：{{ date }}
- 状态：{{ status }}

## 摘要
{{ summary }}

## 动机
{{ motivation }}

## 设计方案
{{ design }}

## 风险与权衡
{{ risks }}
""",
    },
    "design-doc": {
        "name": "设计文档", "kind": "design-doc",
        "variables": ["title", "author", "context", "goals", "architecture", "data_model", "tradeoffs"],
        "content": """# 设计文档：{{ title }}

- 作者：{{ author }}

## 背景与上下文
{{ context }}

## 目标与非目标
{{ goals }}

## 架构
{{ architecture }}

## 数据模型
{{ data_model }}

## 取舍
{{ tradeoffs }}
""",
    },
    "runbook": {
        "name": "运维手册 (Runbook)", "kind": "runbook",
        "variables": ["service", "owner", "severity", "symptoms", "diagnose", "mitigate", "escalate"],
        "content": """# Runbook：{{ service }}

- 负责人：{{ owner }}
- 严重度：{{ severity }}

## 症状
{{ symptoms }}

## 诊断步骤
{{ diagnose }}

## 缓解措施
{{ mitigate }}

## 升级路径
{{ escalate }}
""",
    },
    "adr": {
        "name": "架构决策记录 (ADR)", "kind": "adr",
        "variables": ["title", "date", "context", "decision", "consequences"],
        "content": """# ADR：{{ title }}

- 日期：{{ date }}

## 背景
{{ context }}

## 决策
{{ decision }}

## 后果
{{ consequences }}
""",
    },
}


@app.get("/api/templates/builtin")
async def list_builtin_templates(user_id: str = Depends(_require_user)):
    """列出内置场景模板骨架（RFC/设计文档/Runbook/ADR）及其变量定义。"""
    return {"items": [
        {"name": k, "display_name": v["name"], "kind": v["kind"], "variables": v["variables"]}
        for k, v in _BUILTIN_TEMPLATES.items()
    ]}


@app.post("/api/templates/builtin/{name}/instantiate", status_code=201)
async def instantiate_builtin_template(name: str, payload: dict = Body(...), user_id: str = Depends(_require_user)):
    """用内置场景模板生成新文档（Jinja2 变量插值）。body: {variables: {...}, title?}"""
    from jinja2 import Environment, BaseLoader
    tpl = _BUILTIN_TEMPLATES.get(name)
    if not tpl:
        raise HTTPException(404, f"未知内置模板: {name}")
    variables = payload.get("variables") or {}
    title = (payload.get("title") or tpl["name"]).strip()
    env = Environment(loader=BaseLoader(), autoescape=False, keep_trailing_newline=True)
    try:
        rendered = env.from_string(tpl["content"]).render(**variables)
    except Exception as e:
        raise HTTPException(400, f"变量插值失败: {e}")
    doc_id = "doc-" + secrets.token_urlsafe(10)
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        await db.execute(
            "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, user_id) VALUES (?,?,?,?,?,'file','',?)",
            (doc_id, title[:200], rendered, now, now, user_id),
        )
    await _audit(user_id, None, "template.instantiate_builtin", "template", name, f"->doc={doc_id}")
    return {"doc_id": doc_id, "title": title, "kind": tpl["kind"]}



# ==================== P2-11 模板治理：版本/审批/继承/受管 ====================
_TEMPLATE_STATUS_FLOW = {
    "draft": ["pending"],            # submit
    "pending": ["approved", "draft"],  # approve / reject
    "approved": ["deprecated", "draft"],  # deprecate / re-edit
    "deprecated": ["draft"],         # revive
}


@app.get("/api/templates/{tid}")
async def get_template_detail(tid: str, user_id: str = Depends(_require_user)):
    """模板详情：含版本号、状态、继承链、版本历史。"""
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT id, user_id, team_id, name, content, category, kind, variables_json, created_by, created_at, version, status, parent_id, org_managed, updated_by, updated_at FROM templates WHERE id=?", (tid,)
        )).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        vrows = await (await db.execute(
            "SELECT version, name, status, changed_by, changed_at FROM template_versions WHERE template_id=? ORDER BY version DESC", (tid,)
        )).fetchall()
    if row["team_id"]:
        await _require_team_role(row["team_id"], user_id, "viewer")
    elif row["user_id"] != user_id:
        raise HTTPException(403, "只能查看自己的模板")
    # 解析继承链
    chain = []
    cur = row["parent_id"]
    seen = {tid}
    while cur and cur not in seen and len(chain) < 8:
        seen.add(cur)
        async with _registry_transaction() as db:
            prow = await (await db.execute("SELECT id, name FROM templates WHERE id=?", (cur,))).fetchone()
        if not prow:
            chain.append({"id": cur, "name": None, "broken": True})
            break
        chain.append({"id": prow["id"], "name": prow["name"], "broken": False})
        cur = None  # 单层继承链展示即可，深层经 instantiate 已处理
    return {
        "id": row["id"], "name": row["name"], "content": row["content"],
        "category": row["category"], "kind": row["kind"] or "",
        "variables": _safe_json_loads(row["variables_json"], []),
        "created_by": row["created_by"], "created_at": row["created_at"],
        "version": row["version"], "status": row["status"],
        "parent_id": row["parent_id"], "org_managed": bool(row["org_managed"]),
        "updated_by": row["updated_by"], "updated_at": row["updated_at"],
        "parent_chain": chain,
        "versions": [{"version": v["version"], "name": v["name"], "status": v["status"],
                      "changed_by": v["changed_by"], "changed_at": v["changed_at"]} for v in vrows],
    }


@app.put("/api/templates/{tid}")
async def update_template(tid: str, req: TemplateCreateRequest, user_id: str = Depends(_require_user)):
    """更新模板：个人模板需本人；团队模板需 admin；受管模板需 admin。
    版本治理：编辑即版本号 +1，旧版本快照入 template_versions；受管模板编辑后状态回退 draft（需重新审批）。"""
    name = (req.name or "").strip()
    if not name or len(name) > 128:
        raise HTTPException(400, "模板名必填且 ≤128 字符")
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT user_id, team_id, version, status, org_managed FROM templates WHERE id=?", (tid,)
        )).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        if row["team_id"]:
            await _require_team_role(row["team_id"], user_id, "admin")
        elif row["user_id"] != user_id:
            raise HTTPException(403, "只能编辑自己的模板")
        # 快照旧版本
        snap = await (await db.execute(
            "SELECT name, content, kind, variables_json, version, status FROM templates WHERE id=?", (tid,)
        )).fetchone()
        await db.execute(
            "INSERT INTO template_versions (id, template_id, version, name, content, kind, variables_json, status, changed_by, changed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (secrets.token_urlsafe(10), tid, snap["version"], snap["name"], snap["content"], snap["kind"],
             snap["variables_json"], snap["status"], user_id, _utcnow_iso()),
        )
        import json as _j
        var_json = _j.dumps([v.strip() for v in (req.variables or []) if v.strip()], ensure_ascii=False)
        new_status = "draft" if row["org_managed"] else "active"
        await db.execute(
            "UPDATE templates SET name=?, content=?, category=?, kind=?, variables_json=?, version=version+1, status=?, updated_by=?, updated_at=? WHERE id=?",
            (name, req.content, (req.category or "").strip()[:64], (req.kind or "").strip()[:32], var_json,
             new_status, user_id, _utcnow_iso(), tid),
        )
        new_ver = (await (await db.execute("SELECT version FROM templates WHERE id=?", (tid,))).fetchone())["version"]
    await _audit(user_id, row["team_id"], "template.update", "template", tid, f"v{new_ver}")
    return {"id": tid, "version": new_ver, "status": new_status}


@app.post("/api/templates/{tid}/submit")
async def submit_template(tid: str, user_id: str = Depends(_require_user)):
    """提交审批：draft→pending。受管模板专用。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT user_id, team_id, status, org_managed FROM templates WHERE id=?", (tid,))).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        if row["team_id"]:
            await _require_team_role(row["team_id"], user_id, "admin")
        elif row["user_id"] != user_id:
            raise HTTPException(403, "只能提交自己的模板")
        if row["status"] != "draft":
            raise HTTPException(409, f"当前状态 {row['status']} 不可提交审批")
        await db.execute("UPDATE templates SET status='pending', updated_by=?, updated_at=? WHERE id=?",
                         (user_id, _utcnow_iso(), tid))
    await _audit(user_id, row["team_id"], "template.submit", "template", tid, "draft->pending")
    return {"id": tid, "status": "pending"}


@app.post("/api/templates/{tid}/approve")
async def approve_template(tid: str, user_id: str = Depends(_require_user)):
    """审批通过：pending→approved。需团队 admin（受管模板属组织治理动作）。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT team_id, status, org_managed FROM templates WHERE id=?", (tid,))).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        if not row["team_id"]:
            raise HTTPException(400, "个人模板无需审批")
        await _require_team_role(row["team_id"], user_id, "admin")
        if row["status"] != "pending":
            raise HTTPException(409, f"当前状态 {row['status']} 不可审批")
        await db.execute("UPDATE templates SET status='approved', updated_by=?, updated_at=? WHERE id=?",
                         (user_id, _utcnow_iso(), tid))
    await _audit(user_id, row["team_id"], "template.approve", "template", tid, "pending->approved")
    return {"id": tid, "status": "approved"}


@app.post("/api/templates/{tid}/reject")
async def reject_template(tid: str, payload: dict = Body(default={}), user_id: str = Depends(_require_user)):
    """驳回：pending→draft（可附 reason）。需团队 admin。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT team_id, status FROM templates WHERE id=?", (tid,))).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        if not row["team_id"]:
            raise HTTPException(400, "个人模板无需审批")
        await _require_team_role(row["team_id"], user_id, "admin")
        if row["status"] != "pending":
            raise HTTPException(409, f"当前状态 {row['status']} 不可驳回")
        await db.execute("UPDATE templates SET status='draft', updated_by=?, updated_at=? WHERE id=?",
                         (user_id, _utcnow_iso(), tid))
    reason = (payload or {}).get("reason") or ""
    await _audit(user_id, row["team_id"], "template.reject", "template", tid, f"pending->draft {reason}")
    return {"id": tid, "status": "draft"}


@app.post("/api/templates/{tid}/deprecate")
async def deprecate_template(tid: str, user_id: str = Depends(_require_user)):
    """废弃：approved→deprecated（禁止实例化）。需团队 admin。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT team_id, status FROM templates WHERE id=?", (tid,))).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        if not row["team_id"]:
            raise HTTPException(400, "个人模板不可废弃")
        await _require_team_role(row["team_id"], user_id, "admin")
        if row["status"] != "approved":
            raise HTTPException(409, f"当前状态 {row['status']} 不可废弃")
        await db.execute("UPDATE templates SET status='deprecated', updated_by=?, updated_at=? WHERE id=?",
                         (user_id, _utcnow_iso(), tid))
    await _audit(user_id, row["team_id"], "template.deprecate", "template", tid, "approved->deprecated")
    return {"id": tid, "status": "deprecated"}


@app.delete("/api/templates/{tid}")
async def delete_template(tid: str, user_id: str = Depends(_require_user)):
    """删除模板。个人模板需本人；团队模板需 admin。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT user_id, team_id FROM templates WHERE id=?", (tid,))).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        if row["team_id"]:
            await _require_team_role(row["team_id"], user_id, "admin")
        elif row["user_id"] != user_id:
            raise HTTPException(403, "只能删除自己的模板")
        await db.execute("DELETE FROM template_versions WHERE template_id=?", (tid,))
        await db.execute("DELETE FROM templates WHERE id=?", (tid,))
    await _audit(user_id, row["team_id"] if row else None, "template.delete", "template", tid, None)
    return {"ok": True}


# ==================== P1: 文档状态机 ====================
_DOC_STATUS_FLOW = {"draft": ["in_review"], "in_review": ["approved", "draft"], "approved": ["published", "draft"], "published": ["archived", "draft"], "archived": ["draft"]}

@app.put("/api/docs/{doc_id}/status")
async def update_doc_status(doc_id: str, status: str, user_id: str = Depends(_require_user)):
    """文档状态转移。允许的状态：draft→in_review→approved→published→archived。
    P1-8：开启 LIFECYCLE_REQUIRE_SIGNATURE 后，approved/published 必须经电子签名路径，
    此端点拒绝直接转入（409）；签名路径 POST /api/docs/{id}/sign 完成有签流转转。"""
    if status not in _DOC_STATUS_FLOW:
        raise HTTPException(400, f"非法状态：{status}")
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT status FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        cur_status = row["status"] if "status" in row.keys() else "draft"
        if status not in _DOC_STATUS_FLOW.get(cur_status, []):
            raise HTTPException(409, f"状态 {cur_status} 不可直接转为 {status}")
        # 门禁：approved/published 必须经电子签名（仅严格模式）
        if LIFECYCLE_REQUIRE_SIGNATURE and status in ("approved", "published"):
            raise HTTPException(409, f"严格生命周期模式：{status} 须经电子签名 POST /api/docs/{doc_id}/sign?intent={'approve' if status=='approved' else 'publish'}")
        await db.execute("UPDATE documents SET status=? WHERE doc_id=?", (status, doc_id))
    await _audit(user_id, None, "doc.status", "doc", doc_id, f"{cur_status}->{status}")
    return {"doc_id": doc_id, "status": status}


@app.post("/api/docs/{doc_id}/sign")
async def sign_doc(doc_id: str, intent: str, user_id: str = Depends(_require_user)):
    """电子签名：记录签署人/意图/内容哈希/版本；严格模式下可流转 approved/published。
    intent: review（仅留签）/approve（in_review→approved）/publish（approved→published）。"""
    if intent not in ("review", "approve", "publish"):
        raise HTTPException(400, "intent 需为 review/approve/publish")
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT content, version, status FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?",
            (doc_id, user_id)
        )).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        plain = _doc_atrest_decrypt(row["content"]) if row["content"] else ""
        content_hash = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        version = row["version"] if "version" in row.keys() else 1
        cur_status = row["status"] if "status" in row.keys() else "draft"
        new_status = cur_status
        if intent == "approve":
            if cur_status != "in_review":
                raise HTTPException(409, f"approve 需当前状态 in_review，现为 {cur_status}")
            new_status = "approved"
        elif intent == "publish":
            if cur_status != "approved":
                raise HTTPException(409, f"publish 需当前状态 approved，现为 {cur_status}")
            new_status = "published"
        sid = "sig-" + secrets.token_urlsafe(8)
        await db.execute(
            "INSERT INTO doc_signatures (id, doc_id, doc_version, signer_user_id, intent, content_hash, signed_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (sid, doc_id, version, user_id, intent, content_hash, _utcnow_iso()),
        )
        if new_status != cur_status:
            await db.execute("UPDATE documents SET status=? WHERE doc_id=?", (new_status, doc_id))
    await _audit(user_id, None, "doc.sign", "doc", doc_id, f"intent={intent} v{version} hash={content_hash[:12]}")
    return {"signature_id": sid, "doc_id": doc_id, "intent": intent, "content_hash": content_hash,
            "version": version, "status": new_status}


@app.get("/api/docs/{doc_id}/signatures")
async def list_signatures(doc_id: str, user_id: str = Depends(_require_user)):
    """列出文档的电子签名；content_matches 标记签署时的内容哈希是否仍匹配当前内容（防篡改）。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT content FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id)
        )).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        plain = _doc_atrest_decrypt(row["content"]) if row["content"] else ""
        cur_hash = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        sigs = await (await db.execute(
            "SELECT id, doc_version, signer_user_id, intent, content_hash, signed_at "
            "FROM doc_signatures WHERE doc_id=? ORDER BY signed_at ASC", (doc_id,)
        )).fetchall()
    return {"items": [{"id": r["id"], "version": r["doc_version"], "signer_user_id": r["signer_user_id"],
                       "intent": r["intent"], "content_hash": r["content_hash"], "signed_at": r["signed_at"],
                       "content_matches": r["content_hash"] == cur_hash} for r in sigs]}


# ==================== P2: 文档归档（冷存储，只读） ====================
@app.post("/api/docs/{doc_id}/archive")
async def archive_doc(doc_id: str, user_id: str = Depends(_require_user)):
    """归档文档：标记 archived=1，列表默认隐藏，内容只读。
    归档时自动把状态置为 archived（若支持）。可取消归档恢复可编辑。"""
    async with _db_transaction(user_id) as db:
        try:
            await db.execute("UPDATE documents SET archived=1 WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))
            if db.total_changes == 0:
                raise HTTPException(404, "文档不存在")
            # 同步状态（若列存在）
            try:
                await db.execute("UPDATE documents SET status='archived' WHERE doc_id=?", (doc_id,))
            except Exception:
                pass
        except sqlite3.OperationalError as e:
            if "no such column" in str(e):
                raise HTTPException(500, "归档功能未就绪（请重启后端应用迁移）")
            raise
    await _audit(user_id, None, "doc.archive", "doc", doc_id, "archived=1")
    return {"doc_id": doc_id, "archived": True}


@app.post("/api/docs/{doc_id}/unarchive")
async def unarchive_doc(doc_id: str, user_id: str = Depends(_require_user)):
    """取消归档：恢复可编辑。状态从 archived 回到 published。"""
    async with _db_transaction(user_id) as db:
        await db.execute("UPDATE documents SET archived=0 WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))
        if db.total_changes == 0:
            raise HTTPException(404, "文档不存在")
        try:
            await db.execute("UPDATE documents SET status='published' WHERE doc_id=?", (doc_id,))
        except Exception:
            pass
    await _audit(user_id, None, "doc.unarchive", "doc", doc_id, "archived=0")
    return {"doc_id": doc_id, "archived": False}


# ==================== P2: GDPR 数据导出与账户删除 ====================
from fastapi.responses import StreamingResponse as _StreamingResponse


@app.get("/api/account/export")
async def export_account_data(user_id: str = Depends(_require_user)):
    """导出当前用户全部数据（GDPR 数据可携带权）：所有文档 .md + 配置 JSON，打包 zip 流式下载。"""
    import io, zipfile, json as _json
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 配置文件
        cfg_path = _config_path(user_id)
        if cfg_path.exists():
            zf.writestr("settings.json", cfg_path.read_text(encoding="utf-8"))
        # 全部文档
        async with _db_transaction(user_id) as db:
            rows = await (await db.execute(
                "SELECT doc_id, title, content, created_at, updated_at, version, tags FROM documents WHERE deleted_at IS NULL AND user_id=? ORDER BY updated_at DESC",
                (user_id,),
            )).fetchall()
            manifest = []
            for r in rows:
                safe_title = (r["title"] or r["doc_id"]).replace("/", "_")
                fname = f"docs/{safe_title}.md"
                # 文件名冲突时带 doc_id
                if any(i["file"] == fname for i in manifest):
                    fname = f"docs/{safe_title}.{r['doc_id'][:6]}.md"
                zf.writestr(fname, r["content"] or "")
                manifest.append({"file": fname, "doc_id": r["doc_id"], "title": r["title"],
                                 "created_at": r["created_at"], "updated_at": r["updated_at"],
                                 "version": r["version"], "tags": r["tags"]})
        zf.writestr("manifest.json", _json.dumps({"user_id": user_id, "doc_count": len(manifest),
                                                   "documents": manifest}, ensure_ascii=False, indent=2))
    buf.seek(0)
    await _audit(user_id, None, "account.export", "user", user_id, f"docs={len(manifest)}")
    headers = {"Content-Disposition": f'attachment; filename="account-{user_id[:8]}.zip"'}
    return _StreamingResponse(buf, media_type="application/zip", headers=headers)


class AccountDeleteRequest(BaseModel):
    password: str = ""
    confirm: str = ""


@app.delete("/api/account")
async def delete_account(req: AccountDeleteRequest, request: Request, mode: str = "delete",
                         user_id: str = Depends(_require_user)):
    """注销账户（GDPR 被遗忘权）：需密码确认 + 输入 DELETE 确认串。
    mode=delete（默认）：硬删除用户库/配置/registry 行。
    mode=anonymize：保留文档与审计，PII 匿名化（username→anon_<uid>、email/display_name 置空、
      password_hash 置不可用、active=0），满足"可逆注销 / 审计完整性"场景。"""
    if req.confirm != "DELETE":
        raise HTTPException(400, "请输入 DELETE 确认（req.confirm）")
    # 密码校验（SSO 账户无密码则跳过密码校验但需 confirm）
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT password_hash, username FROM users WHERE user_id=?", (user_id,))).fetchone()
    if not row:
        raise HTTPException(404, "用户不存在")
    if row["password_hash"] and not _verify_password(req.password, row["password_hash"]):
        raise HTTPException(401, "密码错误")
    uname = row["username"]
    # 吊销当前 token（两种模式都吊销）
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
    if token and "." in token and _parse_token(token):
        await _revoke_token(token, user_id)
    # 同时吊销该用户所有 refresh token
    try:
        async with _registry_transaction() as db:
            await db.execute("UPDATE refresh_tokens SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
                             (_utcnow_iso(), user_id))
    except Exception:
        pass

    if mode == "anonymize":
        # 匿名化：保留文档与审计，清除 PII
        anon_name = f"anon_{user_id[:8]}"
        async with _registry_transaction() as db:
            await db.execute(
                "UPDATE users SET username=?, password_hash='', email=NULL, display_name=NULL, "
                "avatar_url=NULL, totp_secret=NULL, active=0 WHERE user_id=?",
                (anon_name, user_id),
            )
            await db.execute("DELETE FROM api_tokens WHERE user_id=?", (user_id,))
            await db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            await db.execute("DELETE FROM revoked_tokens WHERE user_id=?", (user_id,))
            await db.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
        await _audit(user_id, None, "account.anonymize", "user", user_id, uname)
        # 用户库文件保留（文档仍在），仅清配置中的 PII（settings 不含 PII，保留）
        return {"anonymized": True, "username": anon_name}

    await _audit(user_id, None, "account.delete", "user", user_id, uname)
    # 删 registry 中该用户的所有痕迹
    async with _registry_transaction() as db:
        await db.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM team_members WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM api_tokens WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM revoked_tokens WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM saved_searches WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM shares WHERE owner_user_id=?", (user_id,))
    # 删用户库文件 + 配置文件
    import shutil as _sh
    udb_dir = _user_db_path(user_id).parent
    if udb_dir.exists():
        _sh.rmtree(udb_dir, ignore_errors=True)
    cfg = _config_path(user_id)
    if cfg.exists():
        try:
            cfg.unlink()
        except Exception:
            pass
    return {"deleted": True, "username": uname}


# ==================== P1: 2FA/MFA (TOTP) ====================
@app.post("/api/auth/totp/setup")
async def totp_setup(user_id: str = Depends(_require_user)):
    """生成 TOTP 密钥并返回 otpauth URI（供前端渲染二维码）。"""
    secret = _totp_generate_secret()
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT username FROM users WHERE user_id=?", (user_id,))).fetchone()
        uname = row["username"] if row else "user"
        # 暂存 secret（未验证前不启用）
        await db.execute("UPDATE users SET totp_secret=? WHERE user_id=?", (secret, user_id))
    return {"secret": secret, "uri": _totp_uri(secret, uname)}


@app.post("/api/auth/totp/verify")
async def totp_verify(code: str, user_id: str = Depends(_require_user)):
    """验证 TOTP 码，确认启用 2FA。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT totp_secret FROM users WHERE user_id=?", (user_id,))).fetchone()
    if not row or not row["totp_secret"]:
        raise HTTPException(400, "未设置 TOTP")
    if not _totp_verify(row["totp_secret"], code):
        raise HTTPException(401, "验证码错误")
    await _audit(user_id, None, "auth.totp.enable", "user", user_id, None)
    return {"ok": True, "enabled": True}


@app.post("/api/auth/totp/disable")
async def totp_disable(code: str, user_id: str = Depends(_require_user)):
    """关闭 2FA（需验证当前码）。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT totp_secret FROM users WHERE user_id=?", (user_id,))).fetchone()
    if not row or not row["totp_secret"]:
        raise HTTPException(400, "未启用 2FA")
    if not _totp_verify(row["totp_secret"], code):
        raise HTTPException(401, "验证码错误")
    async with _registry_transaction() as db:
        await db.execute("UPDATE users SET totp_secret=NULL WHERE user_id=?", (user_id,))
    return {"ok": True, "enabled": False}


@app.get("/api/auth/totp/status")
async def totp_status(user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT totp_secret FROM users WHERE user_id=?", (user_id,))).fetchone()
    return {"enabled": bool(row and row["totp_secret"])}


# 修改 auth_login：检查 2FA
@app.post("/api/auth/login/2fa")
async def auth_login_2fa(req: AuthRequest, code: str = ""):
    """2FA 第二步：用户名+密码+TOTP 码 → token。"""
    username = (req.username or "").strip()
    password = req.password or ""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM users WHERE username=?", (username,))).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    if not row["totp_secret"]:
        raise HTTPException(400, "该用户未启用 2FA")
    if not _totp_verify(row["totp_secret"], code):
        raise HTTPException(401, "验证码错误")
    return await _auth_payload(row["user_id"], username)


# ==================== P1: Webhook 通知 ====================
class WebhookCreateRequest(BaseModel):
    url: str
    events: str = "*"
    channel_type: str = "generic"  # generic / slack / teams
    secret: str = ""  # HMAC-SHA256 签名密钥（generic 写入 X-Signature 头）


@app.post("/api/webhooks", status_code=201)
async def create_webhook(req: WebhookCreateRequest, team_id: Optional[str] = None, user_id: str = Depends(_require_user)):
    if not req.url.startswith("http"):
        raise HTTPException(400, "URL 必须以 http 开头")
    if req.channel_type not in ("generic", "slack", "teams"):
        raise HTTPException(400, "channel_type 需为 generic/slack/teams")
    if team_id:
        await _require_team_role(team_id, user_id, "admin")
    wid = "wh-" + secrets.token_urlsafe(8)
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO webhooks (id, user_id, team_id, url, events, channel_type, secret, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (wid, user_id, team_id, req.url, (req.events or "*")[:200], req.channel_type, (req.secret or "")[:128], _utcnow_iso()),
        )
    return {"id": wid, "url": req.url, "events": req.events, "channel_type": req.channel_type}


@app.get("/api/webhooks")
async def list_webhooks(user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT id, url, events, channel_type, team_id, created_at FROM webhooks "
            "WHERE user_id=? OR (team_id IN (SELECT team_id FROM team_members WHERE user_id=?)) "
            "ORDER BY created_at DESC", (user_id, user_id)
        )).fetchall()
    return {"items": [{"id": r["id"], "url": r["url"], "events": r["events"],
                       "channel_type": r["channel_type"] or "generic", "team_id": r["team_id"],
                       "created_at": r["created_at"]} for r in rows]}


@app.delete("/api/webhooks/{wid}")
async def delete_webhook(wid: str, user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT user_id, team_id FROM webhooks WHERE id=?", (wid,)
        )).fetchone()
        if not row:
            raise HTTPException(404, "webhook 不存在")
        # 属主本人 或 该团队 admin 可删
        owner = row["user_id"] == user_id
        if not owner and row["team_id"]:
            role = await _team_member_role(row["team_id"], user_id)
            owner = role is not None and _TEAM_ROLE_RANK.get(role, 0) >= _TEAM_ROLE_RANK.get("admin", 0)
        if not owner:
            raise HTTPException(403, "无权删除该 webhook")
        await db.execute("DELETE FROM webhooks WHERE id=?", (wid,))
    return {"ok": True}


# ==================== P1: 细粒度文档 ACL ====================
@app.put("/api/docs/{doc_id}/acl")
async def set_doc_acl(doc_id: str, target_username: str, permission: str, expires_days: int = 0, user_id: str = Depends(_require_user)):
    """给指定用户授予文档级权限（read/write/admin），可设过期天数。仅文档属主或 admin 可操作。"""
    if permission not in ("read", "write", "admin"):
        raise HTTPException(400, "权限需为 read/write/admin")
    expires_at = None
    if expires_days and expires_days > 0:
        from datetime import timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
    async with _registry_transaction() as rdb:
        target = await (await rdb.execute("SELECT user_id FROM users WHERE username=?", (target_username.strip(),))).fetchone()
        if not target:
            raise HTTPException(404, "用户不存在")
        # P1-5：镜像授权到 registry 索引，供被授权方全局搜索（DELETE+INSERT 方言无关）
        await rdb.execute("DELETE FROM doc_grants WHERE doc_id=? AND grantee_user_id=?", (doc_id, target["user_id"]))
        await rdb.execute(
            "INSERT INTO doc_grants (doc_id, owner_user_id, grantee_user_id, permission, granted_at, expires_at) VALUES (?,?,?,?,?,?)",
            (doc_id, user_id, target["user_id"], permission, _utcnow_iso(), expires_at),
        )
    async with _db_transaction(user_id) as db:
        doc = await (await db.execute("SELECT user_id FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not doc:
            raise HTTPException(404, "文档不存在")
        if doc["user_id"] != user_id:
            raise HTTPException(403, "仅文档属主可设置 ACL")
        await db.execute(
            "INSERT OR REPLACE INTO doc_acl (doc_id, user_id, permission, granted_at, expires_at) VALUES (?,?,?,?,?)",
            (doc_id, target["user_id"], permission, _utcnow_iso(), expires_at),
        )
    await _audit(user_id, None, "doc.acl.set", "doc", doc_id, f"user={target_username},perm={permission},expires={expires_at or 'never'}")
    return {"ok": True, "user_id": target["user_id"], "permission": permission, "expires_at": expires_at}


@app.get("/api/docs/{doc_id}/acl")
async def list_doc_acl(doc_id: str, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        doc = await (await db.execute("SELECT user_id FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not doc:
            raise HTTPException(404, "文档不存在")
        rows = await (await db.execute("SELECT user_id, permission, granted_at FROM doc_acl WHERE doc_id=?", (doc_id,))).fetchall()
    return {"items": [{"user_id": r["user_id"], "permission": r["permission"], "granted_at": r["granted_at"]} for r in rows]}


@app.delete("/api/docs/{doc_id}/acl/{uid}")
async def delete_doc_acl(doc_id: str, uid: str, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        doc = await (await db.execute("SELECT user_id FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not doc:
            raise HTTPException(404, "文档不存在")
        if doc["user_id"] != user_id:
            raise HTTPException(403, "仅文档属主可管理 ACL")
        await db.execute("DELETE FROM doc_acl WHERE doc_id=? AND user_id=?", (doc_id, uid))
    # P1-5：同步删除 registry 授权索引
    async with _registry_transaction() as rdb:
        await rdb.execute("DELETE FROM doc_grants WHERE doc_id=? AND grantee_user_id=?", (doc_id, uid))
    return {"ok": True}


# ==================== P1: 外部 Guest 协作者 ====================
class GuestCreateRequest(BaseModel):
    username: str
    password: str
    name: str = ""
    email: Optional[str] = None


@app.post("/api/guests", status_code=201)
async def create_guest(req: GuestCreateRequest, user_id: str = Depends(_require_user)):
    """创建 Guest 账号（非团队成员，仅能访问被 ACL 授权的文档）。"""
    username = (req.username or "").strip()
    password = req.password or ""
    if not username or not password:
        raise HTTPException(400, "用户名和密码不能为空")
    if len(username) > 32 or not re.match(r"^[A-Za-z0-9_.\-]+$", username):
        raise HTTPException(400, "用户名仅支持字母数字、下划线、点、短横线（≤32 字符）")
    if len(password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    guest_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    email = (req.email or "").strip() or None
    async with _registry_transaction() as db:
        try:
            await db.execute(
                "INSERT INTO users (user_id, username, password_hash, created_at, is_admin, is_guest, email) VALUES (?,?,?,?,0,1,?)",
                (guest_id, username, _hash_password(password), now, email),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "用户名已被占用")
    await _audit(user_id, None, "guest.create", "user", guest_id, username)
    logger.info("创建 Guest username=%s by user=%s", username, user_id)
    return {"user_id": guest_id, "username": username, "is_guest": True}


@app.get("/api/guests")
async def list_guests(user_id: str = Depends(_require_user)):
    """列出自己创建的 Guest 账号（通过 ACL 关联的）。"""
    async with _registry_transaction() as db:
        # Guest 账号 = is_guest=1，且在当前用户库的 doc_acl 中有记录
        rows = await (await db.execute("SELECT user_id, username, created_at FROM users WHERE is_guest=1 ORDER BY created_at DESC")).fetchall()
    # 过滤：只返回在当前用户文档 ACL 中被授权的 guest
    guest_ids = [r["user_id"] for r in rows]
    if not guest_ids:
        return {"items": []}
    async with _db_transaction(user_id) as db:
        placeholders = ",".join("?" * len(guest_ids))
        acl_rows = await (await db.execute(f"SELECT DISTINCT user_id FROM doc_acl WHERE user_id IN ({placeholders})", guest_ids)).fetchall()
    acl_uids = {r["user_id"] for r in acl_rows}
    return {"items": [
        {"user_id": r["user_id"], "username": r["username"], "created_at": r["created_at"]}
        for r in rows if r["user_id"] in acl_uids
    ]}


@app.delete("/api/guests/{gid}")
async def delete_guest(gid: str, user_id: str = Depends(_require_user)):
    """删除 Guest 账号（同时清除其 ACL 授权）。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT is_guest FROM users WHERE user_id=?", (gid,))).fetchone()
        if not row or not row["is_guest"]:
            raise HTTPException(404, "Guest 不存在")
        await db.execute("DELETE FROM users WHERE user_id=?", (gid,))
        await db.execute("DELETE FROM api_tokens WHERE user_id=?", (gid,))
    # 清除所有库中的 ACL
    users_dir = _data_dir() / "users"
    if users_dir.exists():
        for udb_path in users_dir.glob("*/docs.db"):
            try:
                import sqlite3 as _s
                conn = _s.connect(str(udb_path))
                conn.execute("DELETE FROM doc_acl WHERE user_id=?", (gid,))
                conn.commit(); conn.close()
            except Exception:
                pass
    await _audit(user_id, None, "guest.delete", "user", gid, None)
    return {"ok": True}


# Guest 邮件邀请
class GuestInviteRequest(BaseModel):
    guest_username: str
    email: str


@app.post("/api/guests/invite", status_code=201)
async def invite_guest(req: GuestInviteRequest, user_id: str = Depends(_require_user)):
    """生成邀请令牌。若配 SMTP 则自动发邀请邮件给对方。
    对方访问 /api/guests/accept?token=xxx 设密码完成注册。"""
    token = secrets.token_urlsafe(24)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO guest_invites (token, owner_user_id, guest_username, email, status, created_at) VALUES (?,?,?,?, 'pending', ?)",
            (token, user_id, req.guest_username.strip(), req.email.strip(), now),
        )
    await _audit(user_id, None, "guest.invite", "invite", token, req.guest_username)
    # 构建完整邀请 URL
    base_url = os.environ.get("APP_BASE_URL", "")
    invite_url = f"{base_url}/api/guests/accept?token={token}" if base_url else f"/api/guests/accept?token={token}"
    # 若配 SMTP 则发邮件
    email_sent = False
    if SMTP_HOST and SMTP_FROM and req.email:
        try:
            from email_templates import send_templated_email
            await send_templated_email(req.email, "guest_invite", {
                "guest_name": req.guest_username,
                "inviter": inviter_name,
                "invite_url": invite_url,
            })
            email_sent = True
        except Exception as e:
            logger.warning("邀请邮件入队失败: %s", e)
    return {"token": token, "invite_url": invite_url, "guest_username": req.guest_username, "email": req.email, "email_sent": email_sent}


async def _send_email(to: str, subject: str, body: str):
    """通过 SMTP 发送邮件（异步）。"""
    from aiosmtplib import SMTP
    msg = f"From: {SMTP_FROM}\nTo: {to}\nSubject: {subject}\nContent-Type: text/plain; charset=utf-8\n\n{body}"
    smtp = SMTP(hostname=SMTP_HOST, port=SMTP_PORT, use_tls=SMTP_USE_TLS)
    await smtp.connect()
    if SMTP_USER:
        await smtp.login(SMTP_USER, SMTP_PASSWORD)
    await smtp.sendmail(SMTP_FROM, [to], msg)
    await smtp.quit()


async def _send_digest_to_user(user_id: str) -> dict:
    """给单个用户发送未读通知邮件摘要。返回统计 {user_id, unread, sent, skipped}。

    sent=False 的常见原因：无 SMTP 配置、用户无 email、无未读。仅在配置 SMTP 且
    EMAIL_DIGEST_ENABLED 时真正投递；否则只统计（便于运维预览与测试）。
    """
    from email_templates import send_templated_email
    res = {"user_id": user_id, "unread": 0, "sent": False, "reason": ""}
    async with _registry_transaction() as db:
        u = await (await db.execute("SELECT username, email FROM users WHERE user_id=?", (user_id,))).fetchone()
        if not u:
            res["reason"] = "user_not_found"
            return res
        email = (u["email"] or "").strip() if "email" in u.keys() else ""
        username = u["username"] or user_id
        # 未读通知（可选 lookback 天数）
        if EMAIL_DIGEST_LOOKBACK_DAYS > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=EMAIL_DIGEST_LOOKBACK_DAYS)).isoformat()
            rows = await (await db.execute(
                "SELECT id, type, detail, link, created_at FROM notifications "
                "WHERE user_id=? AND is_read=0 AND created_at>=? ORDER BY created_at DESC LIMIT ?",
                (user_id, cutoff, EMAIL_DIGEST_MAX_ITEMS))).fetchall()
            cnt_row = await (await db.execute(
                "SELECT COUNT(*) AS c FROM notifications WHERE user_id=? AND is_read=0 AND created_at>=?",
                (user_id, cutoff))).fetchone()
        else:
            rows = await (await db.execute(
                "SELECT id, type, detail, link, created_at FROM notifications "
                "WHERE user_id=? AND is_read=0 ORDER BY created_at DESC LIMIT ?",
                (user_id, EMAIL_DIGEST_MAX_ITEMS))).fetchall()
            cnt_row = await (await db.execute(
                "SELECT COUNT(*) AS c FROM notifications WHERE user_id=? AND is_read=0", (user_id,))).fetchone()
    unread = int(cnt_row["c"]) if cnt_row else 0
    res["unread"] = unread
    if unread == 0:
        res["reason"] = "no_unread"
        return res
    if not (SMTP_HOST and SMTP_FROM):
        res["reason"] = "smtp_not_configured"
        return res
    if not email:
        res["reason"] = "no_email"
        return res
    items = [
        {"detail": (r["detail"] or r["type"] or ""), "link": (r["link"] or "")}
        for r in rows
    ]
    more = max(0, unread - len(items))
    try:
        ok = await send_templated_email(email, "notification_digest", {
            "username": username, "unread_count": unread,
            "items": items, "more": more,
        })
        res["sent"] = bool(ok)
        if not ok:
            res["reason"] = "send_failed"
    except Exception as e:
        res["reason"] = f"error:{e}"
    return res


