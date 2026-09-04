@app.get("/api/proxy-image")
async def proxy_image(url: str):
    if not IMAGE_PROXY_ENABLED:
        raise HTTPException(403, "图片代理已禁用")
    if not url:
        raise HTTPException(400, "缺少 url 参数")

    allowed_schemes = ("http://", "https://")
    if not any(url.startswith(s) for s in allowed_schemes):
        raise HTTPException(400, "仅支持 HTTP/HTTPS 图片")

    # SSRF 防护：默认禁止内网/回环地址；自建内网部署渲染内网图片时设 IMAGE_PROXY_ALLOW_PRIVATE=true 放开
    if not IMAGE_PROXY_ALLOW_PRIVATE and is_ssrf_url(url):
        raise HTTPException(400, "目标地址不可达（内网/回环地址禁止代理；如需渲染内网图片请设 IMAGE_PROXY_ALLOW_PRIVATE=true）")

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, max_redirects=3) as client:
            resp = await client.get(url, headers={"User-Agent": "MarkdownEditor/2.0"})
            if resp.status_code >= 400:
                raise HTTPException(502, f"图片获取失败: HTTP {resp.status_code}")

            content_type = resp.headers.get("content-type", "application/octet-stream")
            if not content_type.startswith(("image/", "application/octet-stream")):
                raise HTTPException(400, f"非图片类型: {content_type}")

            body = resp.content
            if len(body) > IMAGE_PROXY_MAX_BYTES:
                raise HTTPException(413, "图片过大")

            return Response(content=body, media_type=content_type)
    except httpx.RequestError as e:
        logger.error("图片代理请求失败: %s", e)
        raise HTTPException(502, f"图片代理请求失败: {e}")


@app.get("/api/plantuml")
async def proxy_plantuml(url: str = "", format: str = "svg"):
    if not PLANTUML_PROXY_ENABLED:
        raise HTTPException(403, "PlantUML 代理已禁用")

    if url:
        target = url
    else:
        raise HTTPException(400, "缺少 url 参数")

    if not any(target.startswith(s) for s in ("http://", "https://")):
        raise HTTPException(400, "仅支持 HTTP/HTTPS 地址")

    if is_ssrf_url(target):
        raise HTTPException(400, "目标地址不可达（内网/回环地址禁止代理）")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, max_redirects=3) as client:
            resp = await client.get(target, headers={"User-Agent": "MarkdownEditor/2.0"})
            if resp.status_code >= 400:
                raise HTTPException(502, f"PlantUML 渲染失败: HTTP {resp.status_code}")
            content_type = resp.headers.get("content-type", "image/svg+xml")
            return Response(content=resp.content, media_type=content_type)
    except httpx.RequestError as e:
        logger.error("PlantUML 代理请求失败: %s", e)
        raise HTTPException(502, f"PlantUML 代理请求失败: {e}")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "judge0": JUDGE0_API_BASE,
        "plantuml_proxy": PLANTUML_PROXY_ENABLED,
        "image_proxy": IMAGE_PROXY_ENABLED,
        "image_proxy_allow_private": IMAGE_PROXY_ALLOW_PRIVATE,
        "rate_limit": RATE_LIMIT_ENABLED,
        "auth": bool(API_TOKEN),
        "doc_sync": True,
        "teams": True,
        "database": "postgresql" if (DATABASE_URL and _asyncpg_available) else "sqlite",
    }


@app.get("/ready")
async def readiness():
    """就绪探针：校验关键依赖（DB / Redis）是否真正可达。
    /health 仅反映进程存活；/ready 才用于路由流量（不可达时返回 503）。
    Redis 未配置视为非必需依赖（单实例可就绪）。
    """
    checks = {"db": False, "redis": None}  # redis: None=未配置/非必需
    try:
        from pg_adapter import is_pg, acquire_conn, release_conn
        if is_pg():
            conn = await acquire_conn()
            try:
                await conn.fetchval("SELECT 1")
            finally:
                await release_conn(conn)
        else:
            db = await _get_registry_db()
            try:
                await (await db.execute("SELECT 1")).fetchone()
            finally:
                await _put_registry_db(db)
        checks["db"] = True
    except Exception as e:
        checks["db_error"] = str(e)
    # Redis：配置了才校验（ping 失败→not ready）；未配置→视为就绪
    if REDIS_URL:
        try:
            r = await get_redis()
            checks["redis"] = bool(r)
            if r:
                await r.ping()
        except Exception as e:
            checks["redis"] = False
            checks["redis_error"] = str(e)
    ok = checks["db"] and checks["redis"] is not False
    if not ok:
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus 格式指标（text/plain）。无需 prometheus_client，纯文本输出。"""
    import sqlite3 as _s
    lines = []
    # 全局计数（registry.db）
    reg_path = REGISTRY_DB_PATH
    try:
        conn = _s.connect(reg_path); conn.row_factory = _s.Row
        for table in ("users", "teams", "audit_log", "notifications", "reviews", "api_tokens", "webhooks", "templates", "template_versions"):
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                lines.append(f"md_{table}_total {cnt}")
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
    # 连接池 gauge
    lines.append(f"md_user_db_pool_count {sum(len(p) for p in _user_db_pools.values())}")
    lines.append(f"md_team_db_pool_count {sum(len(p) for p in _team_db_pools.values())}")
    lines.append(f"md_collab_rooms_count {len(_collab_rooms)}")
    lines.append(f"md_registry_pool_count {len(_registry_pool)}")
    # LRU 池数量（不同用户/团队缓存的池）与上限，用于观测淘汰压力
    lines.append(f"md_user_pool_entries {len(_user_db_pools)}")
    lines.append(f"md_team_pool_entries {len(_team_db_pools)}")
    lines.append(f"md_user_pool_entries_limit {MAX_USER_POOLS}")
    lines.append(f"md_team_pool_entries_limit {MAX_TEAM_POOLS}")
    lines.append(f"md_total_idle_connections {_total_idle_connections()}")
    lines.append(f"md_total_idle_connections_limit {MAX_TOTAL_IDLE_CONNECTIONS}")
    # 运维状态：备份成功/失败时间戳（unix epoch）+ 累计失败数；leader 身份与抢主次数
    lines.append(f"md_backup_last_success_timestamp {_ops_state['backup_last_success']}")
    lines.append(f"md_backup_last_failure_timestamp {_ops_state['backup_last_failure']}")
    lines.append(f"md_backup_failures_total {_ops_state['backup_failures']}")
    lines.append(f"md_leader_is_leader {_ops_state['leader_is_leader']}")
    lines.append(f"md_leader_changes_total {_ops_state['leader_changes']}")
    # RED 指标（Rate/Errors/Duration 直方图，observability 模块）
    return Response(content="\n".join(lines) + "\n" + render_prometheus(), media_type="text/plain")


# ==================== 审计日志查询 ====================
@app.get("/api/audit")
async def query_audit(team_id: Optional[str] = None, limit: int = 100, user_id: str = Depends(_require_user)):
    """查询审计日志。指定 team_id 时需该团队 admin+；否则需系统管理员。"""
    limit = max(1, min(limit, 500))
    if team_id:
        await _require_team_role(team_id, user_id, "admin")
    else:
        if not await _is_admin(user_id):
            raise HTTPException(403, "仅系统管理员可查看全局审计")
    async with _registry_transaction() as db:
        if team_id:
            rows = await (await db.execute(
                "SELECT id, ts, user_id, team_id, action, target_type, target_id, detail "
                "FROM audit_log WHERE team_id=? ORDER BY id DESC LIMIT ?",
                (team_id, limit),
            )).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT id, ts, user_id, team_id, action, target_type, target_id, detail "
                "FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            )).fetchall()
    return {"items": [
        {"id": r["id"], "ts": r["ts"], "user_id": r["user_id"], "team_id": r["team_id"],
         "action": r["action"], "target_type": r["target_type"], "target_id": r["target_id"], "detail": r["detail"]}
        for r in rows
    ]}


# ==================== SCIM 2.0 用户/组同步（企业 IdP 入站）====================
async def _require_scim(request: Request) -> str:
    """SCIM 鉴权：专用 SCIM_TOKEN 或管理员 API Token。返回调用者标识（system 或 uid）。"""
    auth = request.headers.get("Authorization", "")
    tok = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
    if not tok:
        raise HTTPException(401, "缺少 SCIM 授权令牌")
    if SCIM_TOKEN and hmac.compare_digest(tok, SCIM_TOKEN):
        return "system"
    uid = await _api_token_user(tok)
    if uid and await _is_admin(uid):
        return uid
    raise HTTPException(403, "无 SCIM 权限（需 SCIM_TOKEN 或管理员 API Token）")


def _scim_user_resource(row) -> dict:
    """把 users 行映射为 SCIM User 资源。"""
    emails = []
    if "email" in row.keys() and row["email"]:
        emails = [{"value": row["email"], "type": "work", "primary": True}]
    active = bool(row["active"]) if "active" in row.keys() else True
    return {
        "id": row["user_id"],
        "userName": row["username"],
        "displayName": (row["display_name"] if "display_name" in row.keys() else None) or row["username"],
        "emails": emails,
        "active": active,
        "meta": {"resourceType": "User", "created": row["created_at"]},
    }


def _scim_filter_to_sql(filter_str: str) -> tuple[str, list]:
    """极简 SCIM filter → SQL where（仅支持 userName eq / emails.value eq / active eq）。
    不支持的过滤器返回（"1=1", []）即全表。"""
    import re as _re
    if not filter_str:
        return ("1=1", [])
    m = _re.match(r'\s*(userName|emails\.value|active)\s+eq\s+"?([^"]+)"?\s*$', filter_str)
    if not m:
        return ("1=1", [])
    attr, val = m.groups()
    if attr == "userName":
        return ("username=?", [val])
    if attr == "emails.value":
        return ("email=?", [val])
    if attr == "active":
        return ("active=?", [1 if val.lower() in ("true", "1") else 0])
    return ("1=1", [])


@app.get("/api/scim/v2/Users")
async def scim_list_users(request: Request, startIndex: int = 1, count: int = 100,
                          filter: str = "", caller: str = Depends(_require_scim)):
    where, params = _scim_filter_to_sql(filter)
    async with _registry_transaction() as db:
        total = await (await db.execute(f"SELECT COUNT(*) AS c FROM users WHERE {where}", params)).fetchone()
        rows = await (await db.execute(
            f"SELECT * FROM users WHERE {where} ORDER BY created_at LIMIT ? OFFSET ?",
            params + [max(1, count), max(0, startIndex - 1)],
        )).fetchall()
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": total["c"],
        "startIndex": startIndex,
        "itemsPerPage": len(rows),
        "Resources": [_scim_user_resource(r) for r in rows],
    }


@app.post("/api/scim/v2/Users")
async def scim_create_user(request: Request, caller: str = Depends(_require_scim)):
    body = await request.json()
    username = (body.get("userName") or "").strip()
    if not username or not re.match(r"^[A-Za-z0-9_.\-]+$", username):
        raise HTTPException(400, "userName 非法")
    emails = body.get("emails") or []
    email = next((e.get("value") for e in emails if e.get("value")), None) if emails else None
    user_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        existing = await (await db.execute("SELECT user_id FROM users WHERE username=?", (username,))).fetchone()
        if existing:
            raise HTTPException(409, "userName 已存在")
        await db.execute(
            "INSERT INTO users (user_id, username, password_hash, created_at, is_admin, email, display_name, active, is_guest) "
            "VALUES (?,?,?,?,0,?,?,1,1)",
            (user_id, username, _hash_password(secrets.token_urlsafe(16)), now, email,
             body.get("displayName") or username),
        )
    await _audit(caller, None, "scim.user.create", "user", user_id, username)
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))).fetchone()
    return JSONResponse(_scim_user_resource(row), status_code=201)


@app.get("/api/scim/v2/Users/{user_id}")
async def scim_get_user(user_id: str, caller: str = Depends(_require_scim)):
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))).fetchone()
    if not row:
        raise HTTPException(404, "User 不存在")
    return _scim_user_resource(row)


@app.put("/api/scim/v2/Users/{user_id}")
async def scim_replace_user(user_id: str, request: Request, caller: str = Depends(_require_scim)):
    body = await request.json()
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))).fetchone()
        if not row:
            raise HTTPException(404, "User 不存在")
        emails = body.get("emails") or []
        email = next((e.get("value") for e in emails if e.get("value")), None) if emails else row["email"]
        await db.execute(
            "UPDATE users SET display_name=?, email=?, active=? WHERE user_id=?",
            (body.get("displayName") or row["display_name"] or row["username"], email,
             1 if body.get("active", True) else 0, user_id),
        )
    await _audit(caller, None, "scim.user.update", "user", user_id, None)
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))).fetchone()
    return _scim_user_resource(row)


@app.patch("/api/scim/v2/Users/{user_id}")
async def scim_patch_user(user_id: str, request: Request, caller: str = Depends(_require_scim)):
    body = await request.json()
    ops = body.get("Operations") or body.get("operations") or []
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))).fetchone()
        if not row:
            raise HTTPException(404, "User 不存在")
        display_name = row["display_name"] if "display_name" in row.keys() else None
        email = row["email"] if "email" in row.keys() else None
        active = row["active"] if "active" in row.keys() else 1
        for op in ops:
            path = (op.get("path") or "").split(".")[0]
            val = op.get("value")
            if isinstance(val, list) and val:
                val = val[0]
            if isinstance(val, dict):
                val = val.get("value")
            if path == "displayName":
                display_name = val or display_name
            elif path == "emails":
                email = val or email
            elif path == "active":
                active = 1 if val in (True, "true", 1, "1") else 0
        await db.execute("UPDATE users SET display_name=?, email=?, active=? WHERE user_id=?",
                         (display_name, email, active, user_id))
    await _audit(caller, None, "scim.user.patch", "user", user_id, None)
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))).fetchone()
    return _scim_user_resource(row)


@app.delete("/api/scim/v2/Users/{user_id}")
async def scim_delete_user(user_id: str, caller: str = Depends(_require_scim)):
    # SCIM DELETE = 停用（保留文档与审计，符合 GDPR 保留义务）
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))).fetchone()
        if not row:
            raise HTTPException(404, "User 不存在")
        await db.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
    await _audit(caller, None, "scim.user.deactivate", "user", user_id, None)
    return Response(status_code=204)


@app.get("/api/scim/v2/Groups")
async def scim_list_groups(caller: str = Depends(_require_scim)):
    async with _registry_transaction() as db:
        rows = await (await db.execute("SELECT * FROM scim_groups ORDER BY created_at")).fetchall()
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(rows),
        "Resources": [
            {"id": r["group_id"], "displayName": r["display_name"], "members": await _scim_group_members(r["group_id"])}
            for r in rows
        ],
    }


async def _scim_group_members(group_id: str) -> list:
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT u.user_id, u.username FROM scim_group_members m JOIN users u ON m.user_id=u.user_id WHERE m.group_id=?",
            (group_id,),
        )).fetchall()
    return [{"value": r["user_id"], "display": r["username"]} for r in rows]


@app.post("/api/scim/v2/Groups")
async def scim_create_group(request: Request, caller: str = Depends(_require_scim)):
    body = await request.json()
    name = (body.get("displayName") or "").strip()
    if not name:
        raise HTTPException(400, "displayName 必填")
    gid = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute("INSERT INTO scim_groups (group_id, display_name, created_at) VALUES (?,?,?)", (gid, name, now))
        for m in body.get("members") or []:
            await db.execute("INSERT OR IGNORE INTO scim_group_members (group_id, user_id) VALUES (?,?)",
                             (gid, m.get("value")))
    await _audit(caller, None, "scim.group.create", "scim_group", gid, name)
    return JSONResponse({"id": gid, "displayName": name, "members": await _scim_group_members(gid)}, status_code=201)


@app.get("/api/scim/v2/Groups/{group_id}")
async def scim_get_group(group_id: str, caller: str = Depends(_require_scim)):
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM scim_groups WHERE group_id=?", (group_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Group 不存在")
    return {"id": row["group_id"], "displayName": row["display_name"], "members": await _scim_group_members(group_id)}


@app.delete("/api/scim/v2/Groups/{group_id}")
async def scim_delete_group(group_id: str, caller: str = Depends(_require_scim)):
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT group_id FROM scim_groups WHERE group_id=?", (group_id,))).fetchone()
        if not row:
            raise HTTPException(404, "Group 不存在")
        await db.execute("DELETE FROM scim_groups WHERE group_id=?", (group_id,))
        await db.execute("DELETE FROM scim_group_members WHERE group_id=?", (group_id,))
    await _audit(caller, None, "scim.group.delete", "scim_group", group_id, None)
    return Response(status_code=204)


# ==================== 审计日志留存与合规导出 ====================
def _siem_line(r: dict, fmt: str) -> str:
    """把一条审计记录渲染为 SIEM 采集行（cef/jsonl/syslog）。

    - CEF：CEF:0|md-docs|audit|1.0|<action>|<action>|<sev>|ts=... user=... ...
    - jsonl：单行紧凑 JSON（application/x-ndjson）。
    - syslog：RFC 3164 行，PRI=auth/security facility(4)*8 + notice(5)=37。
    detail 中的换行/竖线做转义，避免破坏 CEF/单行语义。
    """
    action = str(r.get("action") or "")
    detail = str(r.get("detail") or "").replace("\n", "\\n").replace("|", "\\|")
    ts = str(r.get("ts") or "")
    user = str(r.get("user_id") or "")
    team = str(r.get("team_id") or "")
    if fmt == "cef":
        # action 作为 Name 与 SignatureID；严重度固定 3（低，审计事件非告警），可由下游按需提升
        ext = (f"ts={ts} user={user} team={team} "
               f"target_type={r.get('target_type') or ''} target_id={r.get('target_id') or ''} "
               f"detail={detail} record_id={r.get('id') or ''}")
        return f"CEF:0|md-docs|audit|1.0|{action}|{action}|3|{ext}"
    if fmt == "jsonl":
        return json.dumps(r, ensure_ascii=False)
    if fmt == "syslog":
        # PRI=37 (facility=4 security/auth, severity=5 notice)；hostname 取 host 简化
        host = os.environ.get("SIEM_HOSTNAME", "md-docs")
        return f"<37>{ts} {host} md-docs[audit]: id={r.get('id')} action={action} user={user} team={team} detail={detail}"
    return json.dumps(r, ensure_ascii=False)


@app.get("/api/admin/audit/export")
async def export_audit(team_id: Optional[str] = None, date_from: str = "", date_to: str = "",
                       fmt: str = "json", user_id: str = Depends(_require_user)):
    """按时间范围导出审计日志（CSV/JSON/JSONL/CEF/Syslog），供合规存档与 SIEM 接入。
    date_from/date_to 格式 YYYY-MM-DD 或 ISO。指定 team_id 需团队 admin+，否则系统管理员。
    SIEM 格式（fmt=cef|jsonl|syslog）按事件逐行输出，便于 Splunk/ELK/Filebeat 采集。"""
    if team_id:
        await _require_team_role(team_id, user_id, "admin")
    else:
        if not await _is_admin(user_id):
            raise HTTPException(403, "仅系统管理员可导出全局审计")
    sql = ("SELECT id, ts, user_id, team_id, action, target_type, target_id, detail FROM audit_log WHERE 1=1")
    params: list = []
    if team_id:
        sql += " AND team_id=?"; params.append(team_id)
    if date_from:
        sql += " AND ts>=?"; params.append(date_from)
    if date_to:
        sql += " AND ts<=?"; params.append(date_to + "Z" if len(date_to) == 10 else date_to)
    sql += " ORDER BY id ASC LIMIT 100000"
    async with _registry_transaction() as db:
        rows = await (await db.execute(sql, params)).fetchall()
    import csv, io as _io
    fields = ["id", "ts", "user_id", "team_id", "action", "target_type", "target_id", "detail"]

    def _row_dict(r):
        return {k: (r[k] if k in r.keys() else "") for k in fields}

    fmt = (fmt or "json").lower()
    if fmt == "csv":
        buf = _io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(_row_dict(r))
        await _audit(user_id, team_id, "admin.audit.export", "audit", None, f"fmt=csv rows={len(rows)}")
        return Response(content=buf.getvalue(), media_type="text/csv",
                         headers={"Content-Disposition": "attachment; filename=audit.csv"})
    if fmt in ("cef", "jsonl", "syslog"):
        lines = [_siem_line(_row_dict(r), fmt) for r in rows]
        out = "\n".join(lines)
        await _audit(user_id, team_id, "admin.audit.export", "audit", None, f"fmt={fmt} rows={len(rows)}")
        media = {"cef": "text/plain", "jsonl": "application/x-ndjson", "syslog": "application/syslog"}[fmt]
        fname = {"cef": "audit.cef", "jsonl": "audit.jsonl", "syslog": "audit.syslog"}[fmt]
        return Response(content=out, media_type=media,
                        headers={"Content-Disposition": f"attachment; filename={fname}"})
    # json
    out = [_row_dict(r) for r in rows]
    await _audit(user_id, team_id, "admin.audit.export", "audit", None, f"fmt=json rows={len(out)}")
    return Response(content=json.dumps(out, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=audit.json"})


@app.post("/api/admin/audit/retention")
async def purge_audit_retention(user_id: str = Depends(_require_user)):
    """按 AUDIT_RETENTION_DAYS 清理过期审计日志（合规留存策略执行）。

    删除旧行会断裂 hash 链（最早存活行的 prev_hash 指向已删记录），故删除后从
    GENESIS 重新锚定存活链（re-anchor 检查点压缩）——管理员操作、自身审计、
    re-anchor 前可先调 /api/audit/verify 留证。保留窗内的链仍可连续校验。
    """
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    if AUDIT_IMMUTABLE:
        # 不可变模式：清理会 DELETE+re-anchor(UPDATE)，二者均被触发器拦截。
        # 审计必须完整保留，留存期清理应改由外置不可变存储（S3 Object Lock 等）承担。
        raise HTTPException(409, "审计已启用不可变模式（AUDIT_IMMUTABLE=1），禁止清理与 re-anchor；"
                                "如需归档/转出请走 SIEM 导出或外置不可变存储")
    if AUDIT_RETENTION_DAYS <= 0:
        return {"retention_days": 0, "purged": 0, "note": "AUDIT_RETENTION_DAYS=0 表示永久保留"}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=AUDIT_RETENTION_DAYS)).isoformat()
    async with _registry_transaction() as db:
        cur = await db.execute("DELETE FROM audit_log WHERE ts<?", (cutoff,))
        purged = cur.rowcount
        # re-anchor：从 GENESIS 重算存活链的 prev_hash / record_hash
        rows = await (await db.execute(
            "SELECT id, ts, user_id, action, target_id, detail FROM audit_log ORDER BY id ASC"
        )).fetchall()
        prev_hash = "GENESIS"
        for r in rows:
            content = f"{prev_hash}|{r['ts']}|{r['user_id'] or ''}|{r['action']}|{r['target_id'] or ''}|{r['detail'] or ''}"
            rh = hashlib.sha256(content.encode("utf-8")).hexdigest()
            await db.execute(
                "UPDATE audit_log SET prev_hash=?, record_hash=? WHERE id=?",
                (prev_hash, rh, r["id"]),
            )
            prev_hash = rh
    await _audit(user_id, None, "admin.audit.purge", "audit", None, f"purged={purged} cutoff={cutoff}")
    return {"retention_days": AUDIT_RETENTION_DAYS, "purged": purged}


# ==================== D1: 备份导出/导入 API ====================
def _backup_module():
    """惰性导入 scripts/backup.py（复用 create_backup/restore_backup/list_backups/drill）。"""
    import sys
    from pathlib import Path
    scripts_dir = str(Path(__file__).parent / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import backup as _bk
    return _bk


@app.get("/api/admin/backup")
async def admin_list_backups(user_id: str = Depends(_require_user)):
    """列出可恢复备份点（仅管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    bk = _backup_module()
    loop = asyncio.get_event_loop()
    points = await loop.run_in_executor(None, bk.list_backups, BACKUP_DIR)
    return {"items": points, "backup_dir": BACKUP_DIR}


@app.post("/api/admin/backup")
async def admin_create_backup(user_id: str = Depends(_require_user)):
    """立即触发一次备份（仅管理员），返回新备份点。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    bk = _backup_module()
    loop = asyncio.get_event_loop()
    archive = await loop.run_in_executor(None, bk.create_backup, str(_data_dir()), BACKUP_DIR, BACKUP_KEEP)
    await _audit(user_id, None, "admin.backup.create", "backup", archive.name if hasattr(archive, "name") else str(archive), "")
    points = await loop.run_in_executor(None, bk.list_backups, BACKUP_DIR)
    entry = next((p for p in points if p["archive"] == (archive.name if hasattr(archive, "name") else str(archive))), points[0] if points else None)
    return {"ok": True, "point": entry}


@app.get("/api/admin/backup/{archive_name}/download")
async def admin_download_backup(archive_name: str, user_id: str = Depends(_require_user)):
    """下载指定备份归档（仅管理员）。归档名做安全校验禁止路径穿越。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    from pathlib import Path as _P
    from fastapi.responses import FileResponse
    base = _P(BACKUP_DIR).resolve()
    # 仅允许文件名，禁止目录分隔/绝对路径
    safe = _P(archive_name).name
    if safe != archive_name or "/" in archive_name or "\\" in archive_name or archive_name.startswith("."):
        raise HTTPException(400, "非法归档名")
    target = (base / safe).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        raise HTTPException(404, "备份不存在")
    return FileResponse(str(target), media_type="application/gzip", filename=safe)


@app.post("/api/admin/backup/restore")
async def admin_restore_backup(payload: dict = Body(...), user_id: str = Depends(_require_user)):
    """从指定归档恢复数据目录（仅管理员，高危操作，需 force=true 确认）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    from pathlib import Path as _P
    archive_name = (payload.get("archive") or "").strip()
    force = bool(payload.get("force"))
    if not archive_name:
        raise HTTPException(400, "archive 必填")
    safe = _P(archive_name).name
    if safe != archive_name or "/" in archive_name or "\\" in archive_name:
        raise HTTPException(400, "非法归档名")
    base = _P(BACKUP_DIR).resolve()
    archive = (base / safe).resolve()
    if not str(archive).startswith(str(base)) or not archive.is_file():
        raise HTTPException(404, "备份不存在")
    if not force:
        raise HTTPException(409, "恢复为高危操作，需显式 force=true 确认")
    bk = _backup_module()
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, bk.restore_backup, str(archive), str(_data_dir()), True)
    except Exception as e:
        raise HTTPException(500, f"恢复失败: {e}")
    await _audit(user_id, None, "admin.backup.restore", "backup", safe, f"force={force}")
    return {"ok": True, "restored_from": safe, "note": "数据目录已恢复，建议重启服务以重新打开连接池"}


@app.post("/api/admin/backup/drill")
async def admin_drill_backup(user_id: str = Depends(_require_user)):
    """P2-13 DR：立即触发恢复演练（不覆盖运行数据），返回报告 + RTO/RPO 量化。
    RTO=实测恢复耗时（秒）；RPO=距最近成功备份秒数。无备份点→404。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    bk = _backup_module()
    loop = asyncio.get_event_loop()
    try:
        rep = await loop.run_in_executor(None, bk.drill, BACKUP_DIR, str(_data_dir()))
    except RuntimeError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"演练失败: {e}")
    await _audit(user_id, None, "admin.backup.drill", "backup",
                 rep.get("point", {}).get("archive", ""), f"ok={rep.get('ok')} rto={rep.get('rto_seconds')} rpo={rep.get('rpo_seconds')}")
    return rep


@app.get("/api/admin/kms/atrest-status")
async def admin_kms_atrest_status(user_id: str = Depends(_require_user)):
    """P1-5 at-rest KMS 状态：at-rest 加密开关 + 当前密钥 kid（非敏感哈希，用于运维对齐当前密钥）。
    不返回任何密钥原文。与 KMS/Vault 提供者状态（/api/admin/kms/status）解耦。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    cipher = _doc_atrest_build_cipher()
    mat = _doc_atrest_current_key_material or (DOC_ATREST_KEY or AI_ENC_KEY)
    return {
        "atrest_enabled": bool(DOC_ATREST_ENCRYPTION),
        "current_kid": _atrest_kid(mat) if mat else None,
        "history_keys": len(_doc_atrest_old_ciphers),
        "cipher_ready": cipher is not None,
    }


@app.post("/api/admin/kms/rotate-master")
async def admin_kms_rotate_master(payload: dict = Body(...), user_id: str = Depends(_require_user)):
    """P1-5 at-rest 主密钥轮换：提供 new_key（≥16 字符，运维经密管下发）→
    旧 current 入历史 → sweep 全库 atrestv1 密文用旧密钥解密、用新密钥重加密 → 切换 current。
    不返回密钥原文，仅回 kid 与重加密行数（运维凭 kid 对齐密管中的当前密钥）。
    轮换后，运维须将 new_key 同步到 DOC_ATREST_KEY 环境变量，保证重启后仍用新密钥。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    if not DOC_ATREST_ENCRYPTION:
        raise HTTPException(409, "DOC_ATREST_ENCRYPTION 未启用，无需轮换（正文为明文落库）")
    new_key = (payload or {}).get("new_key")
    if not new_key or not isinstance(new_key, str) or len(new_key) < 16:
        raise HTTPException(400, "new_key 必填且 ≥16 字符（运维经密管下发，勿硬编码）")
    try:
        result = await _rotate_doc_atrest_master(new_key)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("at-rest 主密钥轮换失败：%s", e)
        raise HTTPException(500, f"轮换失败: {e}")
    await _audit(user_id, None, "admin.kms.rotate", "kms", "atrest",
                 f"rows={result['reencrypted_rows']} kid={result['kid_new']}")
    return result


@app.get("/api/admin/backup/pitr")
async def admin_pitr_lookup(target_epoch: int, user_id: str = Depends(_require_user)):
    """P2-13 PITR：给定目标时间戳（epoch 秒），返回不晚于该时刻的最近可恢复点。
    SQLite 维度为完整快照基线；连续 WAL 重放（任意时刻）需外部 wal-g/pgBackRest。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    bk = _backup_module()
    loop = asyncio.get_event_loop()
    pt = await loop.run_in_executor(None, bk.find_restore_point, BACKUP_DIR, target_epoch)
    if not pt:
        raise HTTPException(404, "无满足条件的恢复点")
    return {"point": pt, "target_epoch": target_epoch, "note": "恢复到该基线快照；连续 WAL 归档需 wal-g/pgBackRest"}


@app.post("/api/admin/replica/ship")
async def admin_replica_ship(user_id: str = Depends(_require_user)):
    """P2-13 跨区复制：把本地最新备份投递到 REPLICA_DIR（模拟异地归档副本）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    if not REPLICA_DIR:
        raise HTTPException(400, "REPLICA_DIR 未配置")
    bk = _backup_module()
    loop = asyncio.get_event_loop()
    rep = await loop.run_in_executor(None, bk.replicate_latest, BACKUP_DIR, REPLICA_DIR)
    if not rep.get("ok"):
        raise HTTPException(409, rep.get("reason", "复制失败"))
    await _audit(user_id, None, "admin.replica.ship", "backup", rep.get("replicated", ""), f"lag={rep.get('lag_seconds')}")
    return rep


@app.get("/api/admin/replica/status")
async def admin_replica_status(user_id: str = Depends(_require_user)):
    """P2-13 跨区副本健康度：本地/副本最新时间戳、lag、RPO，超 DR_RPO_ALERT_SECONDS 标 stale。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    bk = _backup_module()
    loop = asyncio.get_event_loop()
    st = await loop.run_in_executor(None, bk.replica_status, BACKUP_DIR, REPLICA_DIR)
    rpo = st.get("rpo_seconds", 0)
    st["rpo_alert"] = rpo > DR_RPO_ALERT_SECONDS
    return st


@app.post("/api/admin/collab/{room}/compact")
async def admin_collab_compact(room: str, user_id: str = Depends(_require_user)):
    """协同：强制对某 room 做服务端 CRDT 合并（ypy 可用时 apply 增量→落快照→清增量）。
    ypy 不可用时回退为请求在线客户端推全量快照。返回合并报告。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    rep = await _collab_server_merge(room)
    if not rep.get("merged") and rep.get("reason") == "ypy_unavailable":
        conns = _collab_rooms.get(room)
        if conns:
            await _collab_broadcast_text(room, json.dumps({"type": "request_snapshot", "room": room}))
            rep["fallback"] = "requested_client_snapshot"
        else:
            rep["fallback"] = "no_online_clients"
    await _audit(user_id, None, "admin.collab.compact", "collab", room, f"merged={rep.get('merged')}")
    return rep


# ==================== E1: Git 双向同步（docs-as-code） ====================
# 实现：直接调用 git 二进制（与 scripts/git_sync.py 一致），不引入 GitPython 依赖。
# 本地仓库（file:// 路径）与远端 https 仓库均支持；token 经 Fernet 加密落库、明文不回传。
_GIT_AUTHOR = os.environ.get("GIT_SYNC_AUTHOR", "doc-sync-bot <noreply@localhost>")


async def _git_run(args: list[str], cwd: str, env: dict | None = None) -> tuple[int, str, str]:
    """异步执行 git 子进程，返回 (returncode, stdout, stderr)。失败不抛，由调用方决策。"""
    import asyncio as _aio
    try:
        proc = await _aio.create_subprocess_exec(
            *args, cwd=cwd, env=env,
            stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return proc.returncode, (out or b"").decode("utf-8", "ignore"), (err or b"").decode("utf-8", "ignore")
    except FileNotFoundError:
        return 127, "", "git 二进制未安装"
    except Exception as e:
        return 1, "", str(e)


def _git_authed_url(repo_url: str, token: str) -> str:
    """https 仓库注入 token 鉴权（file:// 与本地路径不动）。"""
    if not token or not repo_url:
        return repo_url
    if repo_url.startswith("https://"):
        return "https://" + token + "@" + repo_url[len("https://"):]
    return repo_url


def _git_workdir(doc_id: str) -> Path:
    d = _data_dir() / "_git" / doc_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _git_file_path(binding: dict, doc_title: str) -> str:
    fp = (binding.get("file_path") or "").strip()
    if not fp:
        fp = doc_title or "doc"
        if not fp.endswith((".md", ".markdown", ".txt")):
            fp += ".md"
    return fp


async def _git_pull_to_doc(binding: dict, doc_id: str, user_id: str) -> dict:
    """从远端拉取仓库到工作树，读 file_path 内容回写文档。返回 {ok, commit, error?}。"""
    token = _ai_decrypt(binding["auth_token_enc"]) if binding.get("auth_token_enc") else ""
    url = _git_authed_url(binding["repo_url"], token)
    work = _git_workdir(doc_id)
    # 克隆或拉取
    if not (work / ".git").exists():
        rc, _, err = await _git_run(["git", "clone", "--quiet", "--branch", binding["branch"] or "main", url, str(work)], str(_data_dir()))
        if rc != 0:
            # 目标分支不存在时回退默认分支克隆
            rc2, _, err2 = await _git_run(["git", "clone", "--quiet", url, str(work)], str(_data_dir()))
            if rc2 != 0:
                return {"ok": False, "error": err or err2 or "clone 失败"}
            await _git_run(["git", "checkout", "--quiet", binding["branch"] or "main"], str(work))
    else:
        await _git_run(["git", "fetch", "--quiet", "origin"], str(work))
        # 尝试切到目标分支
        await _git_run(["git", "checkout", "--quiet", binding["branch"] or "main"], str(work))
        await _git_run(["git", "pull", "--quiet", "--ff-only"], str(work))
    # 读文件
    async with _db_transaction(user_id) as db:
        d = await (await db.execute("SELECT title FROM documents WHERE doc_id=?", (doc_id,))).fetchone()
        doc_title = d["title"] if d else "doc"
    fp = _git_file_path(binding, doc_title)
    target = work / fp
    if not target.is_file():
        return {"ok": False, "error": f"仓库中无文件 {fp}"}
    content = target.read_text(encoding="utf-8")
    # 回写文档（复用版本快照机制）
    async with _db_transaction(user_id) as db:
        cur = await (await db.execute("SELECT version, title, content FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not cur:
            return {"ok": False, "error": "文档不存在"}
        now = _utcnow_iso()
        new_version = cur["version"] + 1
        await db.execute("INSERT INTO doc_versions (doc_id, version, title, content, created_at, created_by) VALUES (?,?,?,?,?,?)",
                         (doc_id, cur["version"], cur["title"], cur["content"], now, user_id))
        await _prune_doc_versions(db, doc_id)
        await db.execute("UPDATE documents SET content=?, updated_at=?, version=? WHERE doc_id=?", (_doc_atrest_encrypt(content), now, new_version, doc_id))
    # 记录 commit
    rc, out, _ = await _git_run(["git", "rev-parse", "--short", "HEAD"], str(work))
    commit = out.strip()
    async with _registry_transaction() as rdb:
        await rdb.execute("UPDATE doc_git_repos SET last_commit=?, updated_at=? WHERE id=?", (commit, _utcnow_iso(), binding["id"]))
    await _audit(user_id, None, "git.pull", "doc", doc_id, f"commit={commit}")
    return {"ok": True, "commit": commit, "content_preview": content[:80]}


async def _git_push_from_doc(binding: dict, doc_id: str, user_id: str, message: str = "sync doc") -> dict:
    """将文档内容写入工作树 file_path，commit 并 push。返回 {ok, commit, error?}。"""
    token = _ai_decrypt(binding["auth_token_enc"]) if binding.get("auth_token_enc") else ""
    url = _git_authed_url(binding["repo_url"], token)
    work = _git_workdir(doc_id)
    # 确保工作树存在
    if not (work / ".git").exists():
        rc, _, err = await _git_run(["git", "clone", "--quiet", url, str(work)], str(_data_dir()))
        if rc != 0:
            # 本地无远端仓库：在工作树 init 并尝试关联 origin（便于纯本地测试）
            await _git_run(["git", "init", "--quiet"], str(work))
        await _git_run(["git", "checkout", "--quiet", "-B", binding["branch"] or "main"], str(work))
    # 读文档内容
    async with _db_transaction(user_id) as db:
        d = await (await db.execute("SELECT title, content FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not d:
            return {"ok": False, "error": "文档不存在"}
        doc_title, content = d["title"], _doc_atrest_decrypt(d["content"] or "")
    fp = _git_file_path(binding, doc_title)
    target = work / fp
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    env = dict(os.environ); env["GIT_AUTHOR_NAME"] = _GIT_AUTHOR.split("<")[0].strip() or "doc-sync"
    env["GIT_AUTHOR_EMAIL"] = (_GIT_AUTHOR.split("<")[1].rstrip("> ") if "<" in _GIT_AUTHOR else "noreply@localhost")
    await _git_run(["git", "add", "--", fp], str(work), env=env)
    # 无变更则跳过
    rc, out, _ = await _git_run(["git", "diff", "--cached", "--quiet"], str(work))
    if rc == 0:
        return {"ok": True, "commit": binding.get("last_commit") or "", "changed": False}
    rc, _, err = await _git_run(["git", "commit", "--quiet", "-m", message], str(work), env=env)
    if rc != 0:
        return {"ok": False, "error": f"commit 失败: {err}"}
    rc, out, _ = await _git_run(["git", "rev-parse", "--short", "HEAD"], str(work))
    commit = out.strip()
    # push（本地 file 仓库也支持；无 origin 时跳过且不报错）
    has_origin = (await _git_run(["git", "remote", "get-url", "origin"], str(work)))[0] == 0
    push_err = ""
    if has_origin:
        prc, _, perr = await _git_run(["git", "push", "--quiet", "origin", binding["branch"] or "main"], str(work))
        if prc != 0:
            push_err = perr
    async with _registry_transaction() as rdb:
        await rdb.execute("UPDATE doc_git_repos SET last_commit=?, updated_at=? WHERE id=?", (commit, _utcnow_iso(), binding["id"]))
    await _audit(user_id, None, "git.push", "doc", doc_id, f"commit={commit}")
    return {"ok": True, "commit": commit, "push_error": push_err}


class GitBindingRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    file_path: str = ""
    token: str = ""
    auto_publish: bool = False
    webhook_secret: str = ""  # 留空则自动生成；用于校验 push-to-publish webhook 签名


@app.post("/api/docs/{doc_id}/git", status_code=201)
async def bind_doc_git(doc_id: str, req: GitBindingRequest, user_id: str = Depends(_require_user)):
    """绑定文档到 Git 仓库（docs-as-code）。token 加密落库，明文不回传；
    webhook_secret 若未提供则自动生成并仅本次返回明文（供配置 GitHub Webhook）。"""
    async with _db_transaction(user_id) as db:
        if not await (await db.execute("SELECT 1 FROM documents WHERE doc_id=? AND user_id=? AND deleted_at IS NULL", (doc_id, user_id))).fetchone():
            raise HTTPException(404, "文档不存在")
    gid = "git-" + secrets.token_urlsafe(8)
    now = _utcnow_iso()
    enc = _ai_encrypt(req.token) if req.token else ""
    # webhook 密钥：未提供则生成（32 字节 url-safe），落库明文（仅用于 HMAC 校验，非敏感凭证）
    wh_secret = req.webhook_secret.strip() or secrets.token_urlsafe(32)
    async with _registry_transaction() as db:
        # 每文档仅一个绑定：先删旧
        await db.execute("DELETE FROM doc_git_repos WHERE scope='doc' AND scope_id=?", (doc_id,))
        await db.execute(
            "INSERT INTO doc_git_repos (id, scope, scope_id, repo_url, branch, file_path, auth_token_enc, auto_publish, webhook_secret, owner_user_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (gid, "doc", doc_id, req.repo_url, req.branch or "main", req.file_path, enc, 1 if req.auto_publish else 0, wh_secret, user_id, now, now),
        )
    await _audit(user_id, None, "git.bind", "doc", doc_id, f"repo={req.repo_url}")
    return {"id": gid, "doc_id": doc_id, "repo_url": req.repo_url, "branch": req.branch or "main",
            "file_path": req.file_path, "auto_publish": req.auto_publish,
            "webhook_secret": wh_secret, "token_hint": _ai_key_hint(req.token)}


@app.get("/api/docs/{doc_id}/git")
async def get_doc_git(doc_id: str, user_id: str = Depends(_require_user)):
    """查询文档的 Git 绑定（token 仅返回末 4 位提示）。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM doc_git_repos WHERE scope='doc' AND scope_id=?", (doc_id,))).fetchone()
    if not row:
        return {"bound": False}
    return {"bound": True, "id": row["id"], "repo_url": row["repo_url"], "branch": row["branch"],
            "file_path": row["file_path"], "auto_publish": bool(row["auto_publish"]),
            "last_commit": row["last_commit"], "token_bound": bool(row["auth_token_enc"]),
            "webhook_bound": bool(row["webhook_secret"])}


@app.delete("/api/docs/{doc_id}/git")
async def unbind_doc_git(doc_id: str, user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        await db.execute("DELETE FROM doc_git_repos WHERE scope='doc' AND scope_id=?", (doc_id,))
    # 清理工作树
    import shutil as _sh
    wd = _git_workdir(doc_id)
    if wd.exists():
        _sh.rmtree(wd, ignore_errors=True)
    await _audit(user_id, None, "git.unbind", "doc", doc_id, "")
    return {"ok": True}


@app.post("/api/docs/{doc_id}/git/pull")
async def pull_doc_git(doc_id: str, user_id: str = Depends(_require_user)):
    """从 Git 仓库拉取并更新文档内容。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM doc_git_repos WHERE scope='doc' AND scope_id=?", (doc_id,))).fetchone()
    if not row:
        raise HTTPException(404, "未绑定 Git 仓库")
    res = await _git_pull_to_doc(dict(row), doc_id, user_id)
    if not res["ok"]:
        raise HTTPException(502, res.get("error", "pull 失败"))
    return res


@app.post("/api/docs/{doc_id}/git/push")
async def push_doc_git(doc_id: str, user_id: str = Depends(_require_user)):
    """将当前文档内容推送到 Git 仓库（commit_on_save 手动触发）。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM doc_git_repos WHERE scope='doc' AND scope_id=?", (doc_id,))).fetchone()
    if not row:
        raise HTTPException(404, "未绑定 Git 仓库")
    res = await _git_push_from_doc(dict(row), doc_id, user_id, message=f"sync doc {doc_id}")
    if not res["ok"]:
        raise HTTPException(502, res.get("error", "push 失败"))
    return res


@app.post("/api/docs/{doc_id}/git/webhook")
async def git_push_webhook(doc_id: str, request: Request):
    """Git push-to-publish webhook（GitHub 兼容）。

    第三方 push 触发 → 校验 HMAC-SHA256 签名（`X-Hub-Signature-256`，密钥为绑定时生成的 webhook_secret）
    → 拉取远端最新内容回写文档 → 若绑定 auto_publish 则置 status=published 并审计。
    不走 _require_user：以 webhook 密钥为准入，签名失败一律 401。
    """
    import hmac as _hmac
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM doc_git_repos WHERE scope='doc' AND scope_id=?", (doc_id,))).fetchone()
    if not row or not row["webhook_secret"]:
        raise HTTPException(404, "未配置 webhook")
    secret = row["webhook_secret"]
    raw = await request.body()
    # 签名校验：X-Hub-Signature-256: sha256=<hex>
    sig = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Hub-Signature") or ""
    if sig.startswith("sha256="):
        mac = _hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not _hmac.compare_digest(sig, f"sha256={mac}"):
            raise HTTPException(401, "webhook 签名校验失败")
    elif sig.startswith("sha1="):
        mac = _hmac.new(secret.encode("utf-8"), raw, hashlib.sha1).hexdigest()
        if not _hmac.compare_digest(sig, f"sha1={mac}"):
            raise HTTPException(401, "webhook 签名校验失败")
    else:
        raise HTTPException(401, "缺少 webhook 签名头")
    # 取文档属主（pull 需以属主身份回写 + 审计；属主在绑定时落库）
    owner = row["owner_user_id"]
    if not owner:
        raise HTTPException(500, "绑定缺少属主信息，请重新绑定")
    async with _db_transaction(owner) as db:
        d = await (await db.execute("SELECT status FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
    if not d:
        raise HTTPException(404, "文档不存在")
    res = await _git_pull_to_doc(dict(row), doc_id, owner)
    if not res["ok"]:
        raise HTTPException(502, res.get("error", "pull 失败"))
    published = False
    if row["auto_publish"] and d["status"] != "published":
        async with _db_transaction(owner) as db:
            await db.execute("UPDATE documents SET status='published', updated_at=? WHERE doc_id=?", (_utcnow_iso(), doc_id))
        await _audit(owner, None, "git.webhook_publish", "doc", doc_id, f"commit={res.get('commit','')}")
        published = True
    else:
        await _audit(owner, None, "git.webhook_pull", "doc", doc_id, f"commit={res.get('commit','')}")
    return {"ok": True, "commit": res.get("commit", ""), "published": published}


@app.post("/api/admin/git/sync")
async def admin_git_sync(user_id: str = Depends(_require_user)):
    """触发所有 auto_publish 绑定的文档 push 到 Git（仅管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        rows = await (await db.execute("SELECT * FROM doc_git_repos WHERE auto_publish=1")).fetchall()
    results = []
    for r in rows:
        if r["scope"] == "doc":
            res = await _git_push_from_doc(dict(r), r["scope_id"], user_id, message=f"auto sync doc {r['scope_id']}")
            results.append({"doc_id": r["scope_id"], "ok": res["ok"], "commit": res.get("commit"), "error": res.get("error") or res.get("push_error", "")})
    return {"synced": len(results), "items": results}


# ==================== E3：文档集 release（打包版本快照） ====================
class ReleaseCreateRequest(BaseModel):
    name: str
    version: str = "1.0"
    doc_ids: list[str] = []


@app.post("/api/releases", status_code=201)
async def create_release(req: ReleaseCreateRequest, user_id: str = Depends(_require_user)):
    """创建文档集 release：对每个属主文档快照当前版本与内容，打包进 manifest。"""
    if not req.doc_ids:
        raise HTTPException(400, "doc_ids 至少一个")
    manifest = []
    async with _db_transaction(user_id) as db:
        for did in req.doc_ids:
            row = await (await db.execute("SELECT doc_id, version, title, content FROM documents WHERE doc_id=? AND user_id=? AND deleted_at IS NULL", (did, user_id))).fetchone()
            if not row:
                raise HTTPException(404, f"文档不存在或无权: {did}")
            manifest.append({"doc_id": row["doc_id"], "version": row["version"],
                              "title": row["title"], "owner": user_id, "content": row["content"] or ""})
    rid = "rel-" + secrets.token_urlsafe(8)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute("INSERT INTO doc_releases (release_id, name, version, manifest, frozen, created_by, created_at) VALUES (?,?,?,?,0,?,?)",
                          (rid, req.name[:120], req.version[:32], json.dumps(manifest, ensure_ascii=False), user_id, now))
    await _audit(user_id, None, "release.create", "release", rid, f"docs={len(manifest)} v={req.version}")
    return {"release_id": rid, "name": req.name, "version": req.version, "doc_count": len(manifest)}


@app.get("/api/releases")
async def list_releases(user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        rows = await (await db.execute("SELECT release_id, name, version, frozen, created_by, created_at, manifest FROM doc_releases ORDER BY created_at DESC")).fetchall()
    items = []
    for r in rows:
        try:
            mf = json.loads(r["manifest"]) if r["manifest"] else []
        except Exception:
            mf = []
        items.append({"release_id": r["release_id"], "name": r["name"], "version": r["version"],
                       "frozen": bool(r["frozen"]), "created_by": r["created_by"], "created_at": r["created_at"], "doc_count": len(mf)})
    return {"items": items}


@app.get("/api/releases/{rid}")
async def get_release(rid: str, user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM doc_releases WHERE release_id=?", (rid,))).fetchone()
    if not row:
        raise HTTPException(404, "release 不存在")
    try:
        manifest = json.loads(row["manifest"]) if row["manifest"] else []
    except Exception:
        manifest = []
    # release 内容在库内为静态加密形态，展示前解密
    for m in manifest:
        if isinstance(m, dict) and "content" in m:
            m["content"] = _doc_atrest_decrypt(m["content"])
    return {"release_id": row["release_id"], "name": row["name"], "version": row["version"],
            "frozen": bool(row["frozen"]), "created_by": row["created_by"], "created_at": row["created_at"],
            "manifest": manifest}


@app.post("/api/releases/{rid}/freeze")
async def freeze_release(rid: str, user_id: str = Depends(_require_user)):
    """冻结 release（版本指针不可再改）。仅创建者可冻结。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT created_by, frozen FROM doc_releases WHERE release_id=?", (rid,))).fetchone()
        if not row:
            raise HTTPException(404, "release 不存在")
        if row["created_by"] != user_id:
            raise HTTPException(403, "仅创建者可冻结")
        await db.execute("UPDATE doc_releases SET frozen=1 WHERE release_id=?", (rid,))
    await _audit(user_id, None, "release.freeze", "release", rid, "")
    return {"release_id": rid, "frozen": True}


@app.post("/api/releases/{rid}/unfreeze")
async def unfreeze_release(rid: str, user_id: str = Depends(_require_user)):
    """解冻 release（恢复引用文档可修改）。仅创建者可解冻。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT created_by, frozen FROM doc_releases WHERE release_id=?", (rid,))).fetchone()
        if not row:
            raise HTTPException(404, "release 不存在")
        if row["created_by"] != user_id:
            raise HTTPException(403, "仅创建者可解冻")
        if not row["frozen"]:
            raise HTTPException(409, "release 未冻结")
        await db.execute("UPDATE doc_releases SET frozen=0 WHERE release_id=?", (rid,))
    await _audit(user_id, None, "release.unfreeze", "release", rid, "")
    return {"release_id": rid, "frozen": False}


async def _doc_in_frozen_release(doc_id: str) -> str | None:
    """返回引用该 doc 的任一已冻结 release 的 release_id（无则 None）。
    用于冻结不可变性：冻结后引用文档不得修改/删除，直至解冻。"""
    async with _registry_transaction() as db:
        rows = await (await db.execute("SELECT release_id, manifest FROM doc_releases WHERE frozen=1")).fetchall()
    for r in rows:
        try:
            mf = json.loads(r["manifest"]) if r["manifest"] else []
        except Exception:
            continue
        for m in mf:
            if isinstance(m, dict) and m.get("doc_id") == doc_id:
                return r["release_id"]
    return None


@app.get("/api/releases/{rid}/download")
async def download_release(rid: str, user_id: str = Depends(_require_user)):
    """打包下载 release 快照（zip）：每个 manifest 文档按快照内容/标题落为 .md。"""
    import io, zipfile, re as _re
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM doc_releases WHERE release_id=?", (rid,))).fetchone()
    if not row:
        raise HTTPException(404, "release 不存在")
    try:
        manifest = json.loads(row["manifest"]) if row["manifest"] else []
    except Exception:
        manifest = []
    buf = io.BytesIO()
    seen = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 索引文件
        index_lines = [f"# {row['name']} v{row['version']}", f"created_at: {row['created_at']}", f"frozen: {bool(row['frozen'])}", ""]
        for m in manifest:
            if not isinstance(m, dict):
                continue
            title = m.get("title") or m.get("doc_id") or "doc"
            safe = _re.sub(r"[^A-Za-z0-9_\-]+", "_", title)[:60] or "doc"
            seen[safe] = seen.get(safe, 0) + 1
            fname = f"{safe}.md" if seen[safe] == 1 else f"{safe}_{seen[safe]}.md"
            content = _doc_atrest_decrypt(m.get("content", "") or "")
            zf.writestr(f"{fname}", content)
            index_lines.append(f"- {fname}  (doc_id={m.get('doc_id')}, v={m.get('version')})")
        zf.writestr("INDEX.md", "\n".join(index_lines))
    data = buf.getvalue()
    safe_name = _re.sub(r"[^A-Za-z0-9_\-]+", "_", row["name"])[:40] or "release"
    return Response(
        content=data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_{row["version"]}.zip"'},
    )


async def _audit_retention_cleanup():
    """启动时按留存策略清理一次过期审计（静默）。"""
    if AUDIT_IMMUTABLE:
        # 不可变模式：禁止 DELETE/UPDATE audit_log，启动期不再做留存清理。
        # 审计转出/归档应由外置不可变存储（S3 Object Lock、独立 SIEM）承担。
        logger.info("AUDIT_IMMUTABLE=1：跳过启动期审计留存清理（不可变模式）")
        return
    if AUDIT_RETENTION_DAYS <= 0:
        return
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=AUDIT_RETENTION_DAYS)).isoformat()
        async with _registry_transaction() as db:
            await db.execute("DELETE FROM audit_log WHERE ts<?", (cutoff,))
    except Exception as e:
        logger.warning("审计留存清理失败: %s", e)


# ==================== 管理后台 ====================
@app.get("/api/admin/users")
async def admin_list_users(user_id: str = Depends(_require_user)):
    """系统用户列表（仅管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT user_id, username, created_at, is_admin FROM users ORDER BY created_at DESC"
        )).fetchall()
    return {"items": [
        {"user_id": r["user_id"], "username": r["username"], "created_at": r["created_at"], "is_admin": bool(r["is_admin"])}
        for r in rows
    ]}


@app.get("/api/admin/kms/status")
async def admin_kms_status(user_id: str = Depends(_require_user)):
    """KMS/Vault 密钥提供者状态（仅管理员；不泄露密钥明文）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    import kms as _kms
    return _kms.status()


@app.get("/api/admin/deps")
async def admin_deps(user_id: str = Depends(_require_user)):
    """已安装依赖清单（仅管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    import depscan
    return {"items": depscan.installed_packages(), "count": len(depscan.installed_packages())}


@app.get("/api/admin/deps/scan")
async def admin_deps_scan(user_id: str = Depends(_require_user)):
    """依赖漏洞扫描（仅管理员）。对照本地 advisory DB 匹配已安装依赖版本。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    import depscan
    hits = depscan.scan_vulns()
    return {"vulnerable": hits, "count": len(hits),
            "high_severity": sum(1 for h in hits if h["severity"] == "high")}


@app.get("/api/admin/sbom")
async def admin_sbom(user_id: str = Depends(_require_user)):
    """导出 CycloneDX SBOM（仅管理员）。query ?download=1 返回文件下载。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    import depscan
    bom = depscan.generate_sbom()
    return JSONResponse(bom)


@app.post("/api/admin/rotate-ai-keys")
async def admin_rotate_ai_keys(user_id: str = Depends(_require_user)):
    """密钥轮换：用当前主密钥重新加密所有已存储的 AI key。
    遍历每个用户库 + 团队库的 ai_configs.enc_key，解密（旧密钥仍可用）
    后用当前密钥重写并标注 kid。轮换完成后可安全下线旧密钥。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    reencrypted = 0
    failed = 0
    now = _utcnow_iso()
    from pg_adapter import is_pg

    async def _rotate_db(db, db_label: str):
        nonlocal reencrypted, failed
        try:
            rows = await (await db.execute("SELECT id, enc_key FROM ai_configs")).fetchall()
        except Exception:
            return
        for r in rows:
            enc = r["enc_key"]
            if not enc:
                continue
            plain = _ai_decrypt(enc)
            if not plain:
                # 无法解密（旧密钥已下线/损坏）
                failed += 1
                continue
            new_enc = _ai_encrypt(plain)
            if new_enc != enc:
                await db.execute("UPDATE ai_configs SET enc_key=?, updated_at=? WHERE id=?", (new_enc, now, r["id"]))
                reencrypted += 1

    if is_pg():
        # PG 共享库：一次性遍历（按 user_id/team_id 不影响 ai_configs 的物理表，但此处 PG 单表共享）
        async with _db_transaction("__rotate__") as db:
            await _rotate_db(db, "pg")
    else:
        users_dir = _data_dir() / "users"
        if users_dir.exists():
            for udb_path in users_dir.glob("*/docs.db"):
                try:
                    uid = udb_path.parent.name
                    async with _db_transaction(uid) as db:
                        await _rotate_db(db, uid)
                except Exception as e:
                    logger.warning("轮换用户库失败 %s: %s", uid, e)
        teams_dir = _data_dir() / "teams"
        if teams_dir.exists():
            for tdb_path in teams_dir.glob("*/docs.db"):
                try:
                    tid = tdb_path.parent.name
                    async with _team_db_transaction(tid) as db:
                        await _rotate_db(db, tid)
                except Exception as e:
                    logger.warning("轮换团队库失败 %s: %s", tid, e)
    await _audit(user_id, None, "admin.rotate_ai_keys", "system", None, f"reencrypted={reencrypted} failed={failed}")
    return {"reencrypted": reencrypted, "failed": failed}


# ==================== 多租户：组织（organization）隔离 ====================
class OrgCreate(BaseModel):
    name: str
    slug: str = ""


class OrgMemberAssign(BaseModel):
    username: str


@app.post("/api/admin/orgs", status_code=201)
async def admin_create_org(req: OrgCreate, user_id: str = Depends(_require_user)):
    """创建组织（仅系统管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    org_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO organizations (org_id, name, slug, created_at) VALUES (?,?,?,?)",
            (org_id, req.name, req.slug, now),
        )
    await _audit(user_id, None, "admin.org.create", "org", org_id, req.name)
    return {"org_id": org_id, "name": req.name, "slug": req.slug}


@app.get("/api/admin/orgs")
async def admin_list_orgs(user_id: str = Depends(_require_user)):
    """列出全部组织（仅系统管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT o.org_id, o.name, o.slug, o.created_at, "
            "(SELECT COUNT(*) FROM users u WHERE u.org_id=o.org_id) AS user_count, "
            "(SELECT COUNT(*) FROM teams t WHERE t.org_id=o.org_id) AS team_count "
            "FROM organizations o ORDER BY o.created_at DESC"
        )).fetchall()
    return {"items": [{"org_id": r["org_id"], "name": r["name"], "slug": r["slug"],
                        "created_at": r["created_at"], "user_count": r["user_count"],
                        "team_count": r["team_count"]} for r in rows]}


@app.post("/api/admin/orgs/{org_id}/members")
async def admin_assign_org_member(org_id: str, req: OrgMemberAssign, user_id: str = Depends(_require_user)):
    """把用户分配到组织（仅系统管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        org = await (await db.execute("SELECT 1 FROM organizations WHERE org_id=?", (org_id,))).fetchone()
        if not org:
            raise HTTPException(404, "组织不存在")
        u = await (await db.execute("SELECT user_id FROM users WHERE username=?", (req.username,))).fetchone()
        if not u:
            raise HTTPException(404, "用户不存在")
        await db.execute("UPDATE users SET org_id=? WHERE user_id=?", (org_id, u["user_id"]))
    await _audit(user_id, org_id, "admin.org.assign_member", "user", u["user_id"], req.username)
    return {"org_id": org_id, "user_id": u["user_id"], "username": req.username}


async def _user_org(user_id: str) -> str | None:
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT org_id FROM users WHERE user_id=?", (user_id,))).fetchone()
    return row["org_id"] if row else None


@app.get("/api/org/{org_id}/users")
async def org_list_users(org_id: str, user_id: str = Depends(_require_user)):
    """组织内用户列表（仅同组织成员可见，实现租户隔离）。"""
    my_org = await _user_org(user_id)
    if not await _is_admin(user_id) and my_org != org_id:
        raise HTTPException(403, "无权访问该组织（租户隔离）")
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT user_id, username, created_at, is_admin FROM users WHERE org_id=? ORDER BY created_at DESC",
            (org_id,),
        )).fetchall()
    return {"items": [{"user_id": r["user_id"], "username": r["username"],
                        "created_at": r["created_at"], "is_admin": bool(r["is_admin"])} for r in rows]}


@app.get("/api/org/{org_id}/teams")
async def org_list_teams(org_id: str, user_id: str = Depends(_require_user)):
    """组织内团队列表（仅同组织成员可见）。"""
    my_org = await _user_org(user_id)
    if not await _is_admin(user_id) and my_org != org_id:
        raise HTTPException(403, "无权访问该组织（租户隔离）")
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT team_id, name, slug, owner_user_id, created_at FROM teams WHERE org_id=? ORDER BY created_at DESC",
            (org_id,),
        )).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.get("/api/admin/teams")
async def admin_list_teams(user_id: str = Depends(_require_user)):
    """全部团队列表（仅管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT t.team_id, t.name, t.slug, t.owner_user_id, t.created_at, "
            "(SELECT username FROM users u WHERE u.user_id=t.owner_user_id) AS owner_name, "
            "(SELECT COUNT(*) FROM team_members m WHERE m.team_id=t.team_id) AS member_count "
            "FROM teams t ORDER BY t.created_at DESC"
        )).fetchall()
    return {"items": [
        {"team_id": r["team_id"], "name": r["name"], "slug": r["slug"],
         "owner_user_id": r["owner_user_id"], "owner_name": r["owner_name"],
         "member_count": r["member_count"], "created_at": r["created_at"]}
        for r in rows
    ]}


@app.put("/api/admin/users/{uid}/admin")
async def admin_set_admin(uid: str, value: int, user_id: str = Depends(_require_user)):
    """设置/取消系统管理员（仅管理员）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    if value not in (0, 1):
        raise HTTPException(400, "value 需为 0 或 1")
    async with _registry_transaction() as db:
        if not await (await db.execute("SELECT 1 FROM users WHERE user_id=?", (uid,))).fetchone():
            raise HTTPException(404, "用户不存在")
        await db.execute("UPDATE users SET is_admin=? WHERE user_id=?", (value, uid))
    await _audit(user_id, None, "admin.set_admin", "user", uid, f"is_admin={value}")
    return {"user_id": uid, "is_admin": bool(value)}


@app.get("/api/audit/verify")
async def verify_audit_chain(user_id: str = Depends(_require_user)):
    """校验审计日志 hash 链完整性。仅管理员。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT id, ts, user_id, action, target_id, detail, prev_hash, record_hash FROM audit_log ORDER BY id ASC"
        )).fetchall()
    prev_hash = "GENESIS"
    broken = []
    for r in rows:
        # 1) 链式 prev_hash 字段必须等于上一条的 record_hash（防篡改 prev_hash 字段）
        if r["prev_hash"] != prev_hash:
            broken.append({"id": r["id"], "kind": "prev_hash_link",
                            "expected": (prev_hash or "")[:16], "got": (r["prev_hash"] or "")[:16]})
        # 2) record_hash 必须可由 (prev_hash|ts|user_id|action|target_id|detail) 重算
        content = f"{prev_hash}|{r['ts']}|{r['user_id'] or ''}|{r['action']}|{r['target_id'] or ''}|{r['detail'] or ''}"
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if r["record_hash"] != expected:
            broken.append({"id": r["id"], "kind": "record_hash",
                            "expected": expected[:16], "got": (r["record_hash"] or "")[:16]})
        prev_hash = r["record_hash"] or expected
    return {"total": len(rows), "broken_count": len(broken), "intact": len(broken) == 0,
            "immutable": bool(AUDIT_IMMUTABLE), "broken": broken[:20]}


# ==================== API Token（REST 自动化）====================
class ApiTokenCreate(BaseModel):
    name: str = ""


@app.post("/api/tokens", status_code=201)
async def create_api_token(req: ApiTokenCreate, user_id: str = Depends(_require_user)):
    """创建 API token：明文仅返回一次，服务端只存哈希。可用于自动化访问 /api/docs 等。"""
    raw = "pat_" + secrets.token_urlsafe(32)
    tid = "tok-" + secrets.token_urlsafe(8)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO api_tokens (id, user_id, name, token_hash, created_at) VALUES (?,?,?,?,?)",
            (tid, user_id, (req.name or "").strip()[:64] or "default", _hash_api_token(raw), now),
        )
    await _audit(user_id, None, "token.create", "token", tid, req.name or "")
    return {"id": tid, "name": req.name or "default", "token": raw, "created_at": now}


@app.get("/api/tokens")
async def list_api_tokens(user_id: str = Depends(_require_user)):
    """列出我的 API token（不含明文）。"""
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT id, name, created_at, last_used FROM api_tokens WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        )).fetchall()
    return {"items": [
        {"id": r["id"], "name": r["name"], "created_at": r["created_at"], "last_used": r["last_used"]} for r in rows
    ]}


@app.delete("/api/tokens/{tid}")
async def delete_api_token(tid: str, user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        if not await (await db.execute("SELECT 1 FROM api_tokens WHERE id=? AND user_id=?", (tid, user_id))).fetchone():
            raise HTTPException(404, "token 不存在")
        await db.execute("DELETE FROM api_tokens WHERE id=?", (tid,))
    await _audit(user_id, None, "token.delete", "token", tid, None)
    return {"ok": True}


