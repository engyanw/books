@app.post("/api/admin/residency/assign")
async def residency_assign(req: ResidencyAssignRequest, user_id: str = Depends(_require_user)):
    """把某用户/团队重新分配到目标 region（仅管理员）。会迁移已存在的文档库文件到新 region 目录，
    并驱逐内存连接池（下次访问用新路径幂等重建）。"""
    import shutil as _sh
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    if req.scope not in ("user", "team"):
        raise HTTPException(400, "scope 需为 user/team")
    if req.region and req.region not in (RESIDENCY_REGIONS or {}):
        raise HTTPException(400, f"未知 region：{req.region}（未在 RESIDENCY_REGIONS 配置）")
    table = "users" if req.scope == "user" else "teams"
    key_col = "user_id" if req.scope == "user" else "team_id"
    # 关闭并驱逐旧连接池（确保文件可移动）
    if req.scope == "user":
        old = _user_db_pools.pop(req.scope_id, None)
        _user_db_initialized.discard(req.scope_id)
        if old:
            for c in old:
                try: await c.close()
                except Exception: pass
    else:
        old = _team_db_pools.pop(req.scope_id, None)
        _team_db_initialized.discard(req.scope_id)
        if old:
            for c in old:
                try: await c.close()
                except Exception: pass
    # 记录旧 region → 取旧路径（迁移前）
    old_region = _sync_read_region(table, req.scope_id, key_col=key_col)
    old_path = (_residency_dir(old_region) / ("users" if req.scope == "user" else "teams")
                / req.scope_id / "docs.db")
    # 写入新 region
    async with _registry_transaction() as db:
        r = await (await db.execute(f"SELECT {key_col} FROM {table} WHERE {key_col}=?", (req.scope_id,))).fetchone()
        if not r:
            raise HTTPException(404, f"{req.scope} 不存在")
        await db.execute(f"UPDATE {table} SET residency_region=? WHERE {key_col}=?",
                         (req.region, req.scope_id))
    # 迁移文件
    new_path = (_residency_dir(req.region) / ("users" if req.scope == "user" else "teams")
                / req.scope_id / "docs.db")
    moved = False
    if old_path.exists() and old_path.resolve() != new_path.resolve():
        new_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _sh.move(str(old_path), str(new_path))
            moved = True
        except Exception as e:
            logger.warning("驻留迁移失败 %s %s: %s", req.scope, req.scope_id, e)
    await _audit(user_id, None, "residency.assign", "residency", req.scope_id,
                 f"scope={req.scope} region={req.region or '(default)'} moved={moved}")
    return {"ok": True, "scope": req.scope, "scope_id": req.scope_id,
            "region": req.region or "(default)", "moved": moved}


# ==================== 后台任务 leader 选举（端点）====================
@app.get("/api/admin/leader")
async def leader_status(user_id: str = Depends(_require_user)):
    """当前 leader 实例与租约过期时间（运维观测用）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    enabled = bool(LEADER_ELECTION_ENABLED)
    me = _INSTANCE_ID
    holder, expires_at = None, None
    if enabled:
        if REDIS_URL:
            r = await get_redis()
            if r is not None:
                v = await r.get(LEADER_KEY)
                holder = (v.decode() if isinstance(v, (bytes, bytearray)) else v) if v else None
        if holder is None:
            async with _registry_transaction() as db:
                row = await (await db.execute("SELECT holder, expires_at FROM leader_lease WHERE id=1")).fetchone()
                if row:
                    holder, expires_at = row["holder"], row["expires_at"]
    return {"enabled": enabled, "instance_id": me, "leader": holder,
            "is_leader": (holder == me) if enabled else True, "expires_at": expires_at}


# ==================== 多实例一致性约束（P1-3）====================
def _storage_mode_info():
    """当前存储/部署模式与多实例一致性评估（运维观测 + 启动告警共用）。

    SQLite per-user 模式下请求路径写本地文件；多实例 active/active 无共享 FS
    则同用户 docs.db 被并发写损坏。leader 选举只护后台循环，不协调请求路径。
    """
    from pg_adapter import is_pg
    pg = is_pg()
    multi = bool(MULTI_INSTANCE_HA) or bool(LEADER_ELECTION_ENABLED)
    # 多实例 + SQLite + 非共享 FS → 请求路径不一致
    unsafe = multi and (not pg) and (not DOC_DATA_DIR_SHARED)
    recommendation = (
        "pg" if unsafe and not DOC_DATA_DIR_SHARED
        else ("shared_fs" if (multi and not pg and DOC_DATA_DIR_SHARED) else "ok")
    )
    # P1-6 多区域边界：本实例部署 region + PG 角色；active-active 写路径不支持
    region = DEPLOY_REGION or "default"
    pg_role = PG_REPLICA_ROLE or ("primary" if pg else "standalone")
    # 多区域 active-active 仅在显式声明 + PG 副本拓扑下"读"可水平扩展；写仍单一主区
    multi_region_aa = bool(MULTI_REGION_ACTIVE_ACTIVE)
    regions_cfg = [
        {"region": name, "dir": str(cfg.get("dir", "")) if isinstance(cfg, dict) else str(cfg)}
        for name, cfg in (RESIDENCY_REGIONS or {}).items()
    ]
    return {
        "backend": "postgresql" if pg else "sqlite_per_user",
        "multi_instance": multi,
        "data_dir_shared": bool(DOC_DATA_DIR_SHARED),
        "leader_election": bool(LEADER_ELECTION_ENABLED),
        "redis_required": bool(REDIS_REQUIRED) if REDIS_URL else False,
        "request_path_consistent": not unsafe,
        "unsafe": unsafe,
        "recommendation": recommendation,
        "strict_mode": bool(MULTI_INSTANCE_STRICT),
        # P1-6 多区域边界字段
        "region": region,
        "pg_role": pg_role,  # standalone / primary / replica（仅观测）
        "residency_enabled": bool(DATA_RESIDENCY_ENABLED),
        "residency_regions": regions_cfg,
        "multi_region_active_active": multi_region_aa,
        "multi_region_boundary": (
            "single_region_write"  # 写路径始终单一主区；active-active 写不支持
            if not multi_region_aa else "active_active_write_unsupported"
        ),
        "multi_region_supported_via": "pg_streaming_replica_read_scaling" if pg else "none",
    }


@app.get("/api/admin/storage-mode")
async def storage_mode(user_id: str = Depends(_require_user)):
    """存储/部署模式与多实例一致性评估（运维据此判断是否可安全水平扩展）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    info = _storage_mode_info()
    info["data_dir"] = str(_data_dir())
    return info


# ==================== P2 API 版本化 ====================
# 策略：未版本化 /api/* 路径继续可用（向后兼容）；/api/v1/* 为稳定版本化别名。
# 通过中间件在路由前重写 /api/v1/<path> → /api/<path>，复用全部既有端点实现，
# 避免重复定义；响应带 X-API-Version 头供客户端对齐。新集成建议用 /api/v1/*。
@app.get("/api/version")
async def api_version_manifest():
    """API 版本清单（公开）：当前版本、支持版本、版本化前缀、向后兼容策略。"""
    return {
        "current": "v1",
        "supported": ["v1"],
        "versioned_prefix": "/api/v1",
        "unversioned_prefix": "/api",
        "deprecation_policy": "未版本化 /api/* 继续可用（向后兼容）；新集成用 /api/v1/*。",
        "sunset": None,
    }


@app.middleware("http")
async def _api_versioning_middleware(request: Request, call_next):
    """将 /api/v1/<path> 在路由前透明重写为 /api/<path>，复用既有端点。
    响应头 X-API-Version 标识命中的版本化别名。
    已注册的真实 /api/v1/* 路由（如 /api/v1/openapi 发现端点）不重写，避免覆盖。"""
    path = request.url.path
    if path.startswith("/api/v1/") and path not in _real_v1_route_paths():
        new_path = "/api/" + path[len("/api/v1/"):]
        request.scope["path"] = new_path
        request.scope["raw_path"] = new_path.encode("ascii")
        resp = await call_next(request)
        resp.headers["X-API-Version"] = "v1"
        return resp
    return await call_next(request)


@lru_cache(maxsize=1)
def _real_v1_route_paths() -> frozenset:
    """已注册的真实 /api/v1/* 路由路径集合（静态路径）。这些路径有自身处理器，版本化别名不应覆盖。"""
    return frozenset(
        getattr(r, "path", "") for r in app.routes
        if getattr(r, "path", "").startswith("/api/v1/")
    )



# ==================== P2 合规框架控制映射 ====================
@app.get("/api/admin/compliance")
async def compliance_framework(fmt: str = "json", user_id: str = Depends(_require_user)):
    """SOC2 / ISO27001 / GDPR 控制项 → 系统功能映射（企业采购对照 + 证据包导出）。

    ?format=csv 返回 CSV；默认 JSON。仅管理员（暴露系统内部证据点）。
    """
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    import compliance_controls as _cc
    if fmt.lower() == "csv":
        csv_text = _cc.to_csv()
        return Response(csv_text.encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=compliance_controls.csv"})
    return _cc.FRAMEWORKS


# ==================== P2: 图片/附件上传 ====================
UPLOAD_DIR = _data_dir() / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), doc_id: str = "", user_id: str = Depends(_require_user)):
    """上传图片/附件，存 data/uploads/<uid>/<hash>.<ext>，返回 URL。
    可选 doc_id：关联到文档（便于按文档归集）。可读文本附件会被抽取并入 attachments_fts，
    使全文搜索能命中附件内容（docs-as-code 常见诉求）。"""
    if not await _check_endpoint_rate_limit(user_id, "/api/upload"):
        raise HTTPException(429, "上传过于频繁（每小时 100 次）")
    allowed = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".txt", ".md", ".docx", ".xlsx", ".zip", ".pptx"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件类型：{ext}")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "文件过大（>20MB）")
    import hashlib as _hl
    from storage import store_bytes, STORAGE_BACKEND as _SB
    h = _hl.sha256(content).hexdigest()[:16]
    fname = f"{h}{ext}"
    ctype = file.content_type or "application/octet-stream"
    url, _skey = store_bytes(user_id, fname, content, ctype)
    # 抽取可读文本并入库 attachments + attachments_fts
    text = ""
    try:
        import attach_index
        text = attach_index.extract_text(file.filename or fname, content)
    except Exception as e:
        logger.warning("附件文本抽取失败 %s: %s", fname, e)
    try:
        async with _db_transaction(user_id) as db:
            cur = await db.execute(
                "INSERT INTO attachments (doc_id, owner_user_id, filename, storage_url, content_type, size, extracted_text, created_at) "
                "VALUES (?,?,?,?,?,?,?,?) RETURNING id",
                (doc_id or None, user_id, file.filename or fname, url, ctype, len(content), text, _utcnow_iso()),
            )
            aid = (await cur.fetchone())["id"]
            # 入 FTS（分词后）；若 extracted_text 为空也入（仍可按文件名搜）
            tok = _fts_tokenize_text(text)
            await db.execute(
                "INSERT INTO attachments_fts(attachment_id, doc_id, filename, content) VALUES (?,?,?,?)",
                (str(aid), doc_id or "", file.filename or fname, tok),
            )
    except Exception as e:
        logger.warning("附件入库/索引失败 %s: %s", fname, e)
    await _audit(user_id, None, "upload", "file", fname, f"{file.filename} indexed={bool(text)}")
    return {"url": url, "filename": file.filename, "size": len(content), "storage": _SB,
            "indexed": bool(text), "extracted_chars": len(text)}


@app.get("/api/docs/{doc_id}/attachments")
async def list_doc_attachments(doc_id: str, user_id: str = Depends(_require_user)):
    """列出某文档关联的附件（含是否已索引、抽取字符数）。"""
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT id, doc_id, filename, storage_url, content_type, size, length(extracted_text) AS tlen, created_at "
            "FROM attachments WHERE doc_id=? ORDER BY created_at DESC",
            (doc_id,),
        )).fetchall()
    return {"items": [
        {"id": r["id"], "doc_id": r["doc_id"], "filename": r["filename"], "url": r["storage_url"],
         "content_type": r["content_type"], "size": r["size"],
         "indexed_chars": r["tlen"] or 0, "created_at": r["created_at"]} for r in rows
    ]}


@app.get("/api/attachments/search")
async def search_attachments(q: str = "", limit: int = 50, user_id: str = Depends(_require_scope("docs:read"))):
    """在当前用户个人库的附件全文索引中搜索（命中附件文件名/抽取内容）。"""
    q = (q or "").strip()
    if not q:
        return {"items": []}
    limit = max(1, min(limit, 200))
    like = f"%{q}%"
    fts_q = _fts_build_query(q)
    async with _db_transaction(user_id) as db:
        try:
            rows = await (await db.execute(
                "SELECT a.id, a.doc_id, a.filename, a.storage_url, substr(a.extracted_text,1,120) AS preview, a.created_at, "
                "bm25(attachments_fts, 0.0, 1.0, 2.0, 4.0) AS rel "
                "FROM attachments a JOIN attachments_fts f ON a.id = CAST(f.attachment_id AS INTEGER) "
                "WHERE attachments_fts MATCH ? ORDER BY bm25(attachments_fts, 0.0, 1.0, 2.0, 4.0) ASC LIMIT ?",
                (fts_q, limit),
            )).fetchall()
        except Exception:
            rows = await (await db.execute(
                "SELECT id, doc_id, filename, storage_url, substr(extracted_text,1,120) AS preview, created_at, 0 AS rel "
                "FROM attachments WHERE filename LIKE ? OR extracted_text LIKE ? ORDER BY created_at DESC LIMIT ?",
                (like, like, limit),
            )).fetchall()
    return {"items": [
        {"id": r["id"], "doc_id": r["doc_id"] or "", "filename": r["filename"], "url": r["storage_url"],
         "preview": r["preview"] or "", "kind": "attachment", "created_at": r["created_at"]} for r in rows
    ]}


# ==================== P2: 内容变更建议 ====================
class SuggestionCreate(BaseModel):
    original_text: str = ""
    proposed_text: str
    comment: str = ""


@app.post("/api/docs/{doc_id}/suggestions", status_code=201)
async def create_suggestion(doc_id: str, req: SuggestionCreate, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        if not await (await db.execute("SELECT 1 FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone():
            raise HTTPException(404, "文档不存在")
        cur = await db.execute(
            "INSERT INTO suggestions (doc_id, proposer_id, original_text, proposed_text, comment, status, created_at) VALUES (?,?,?,?,?, 'pending', ?) RETURNING id",
            (doc_id, user_id, req.original_text, req.proposed_text, req.comment, _utcnow_iso()),
        )
        sid = (await cur.fetchone())["id"]
    # 评注中的 @mention 通知（跳过作者自身）
    await _notify_mentions(req.comment or req.proposed_text, author_id=user_id, link=f"/?doc={doc_id}")
    return {"id": sid, "status": "pending"}


@app.get("/api/docs/{doc_id}/suggestions")
async def list_suggestions(doc_id: str, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT id, proposer_id, original_text, proposed_text, comment, status, created_at, decided_at FROM suggestions WHERE doc_id=? ORDER BY id DESC",
            (doc_id,),
        )).fetchall()
    return {"items": [
        {"id": r["id"], "proposer_id": r["proposer_id"], "original_text": r["original_text"],
         "proposed_text": r["proposed_text"], "comment": r["comment"], "status": r["status"],
         "created_at": r["created_at"], "decided_at": r["decided_at"]} for r in rows
    ]}


# ==================== C2：行锚点评论 + 线程 ====================
class CommentCreate(BaseModel):
    body: str
    parent_id: Optional[int] = None
    anchor_type: str = "line"
    anchor_start: Optional[int] = None
    anchor_end: Optional[int] = None
    selector: Optional[str] = None
    doc_version: Optional[int] = None


def _comment_tx(user_id: str, team_id: Optional[str]):
    """选择评论所在库：team_id 非空走团队库，否则个人库。"""
    if team_id:
        return _team_db_transaction(team_id)
    return _db_transaction(user_id)


async def _comment_row_to_dict(r) -> dict:
    return {
        "id": r["id"], "doc_id": r["doc_id"], "doc_version": r["doc_version"],
        "anchor_type": r["anchor_type"], "anchor_start": r["anchor_start"], "anchor_end": r["anchor_end"],
        "selector": r["selector"], "author_user_id": r["author_user_id"], "body": r["body"],
        "status": r["status"], "parent_id": r["parent_id"], "created_at": r["created_at"],
        "resolved_at": r["resolved_at"], "resolver_user_id": r["resolver_user_id"],
    }


@app.post("/api/docs/{doc_id}/comments", status_code=201)
async def create_comment(doc_id: str, req: CommentCreate, team_id: Optional[str] = None,
                        user_id: str = Depends(_require_user)):
    """在某文档创建评论/回复（支持行锚点）。team_id 非空时为团队文档评论。"""
    if team_id:
        await _require_team_role(team_id, user_id, "viewer")
    now = _utcnow_iso()
    async with _comment_tx(user_id, team_id) as db:
        cur = await db.execute(
            "INSERT INTO doc_comments (doc_id, doc_version, anchor_type, anchor_start, anchor_end, selector, "
            "author_user_id, body, status, parent_id, created_at) VALUES (?,?,?,?,?,?,?,?,'open',?,?) RETURNING id",
            (doc_id, req.doc_version, req.anchor_type, req.anchor_start, req.anchor_end, req.selector,
             user_id, req.body, req.parent_id, now),
        )
        cid = (await cur.fetchone())["id"]
    # 评论中的 @mention 通知
    await _notify_mentions(req.body, author_id=user_id, link=f"/?doc={doc_id}" + (f"&team={team_id}" if team_id else ""),
                           detail_prefix="评论中提及你")
    await _audit(user_id, team_id, "comment.create", "doc", doc_id, f"cid={cid}")
    async with _comment_tx(user_id, team_id) as db:
        row = await (await db.execute("SELECT * FROM doc_comments WHERE id=?", (cid,))).fetchone()
    return await _comment_row_to_dict(row)


@app.get("/api/docs/{doc_id}/comments")
async def list_comments(doc_id: str, team_id: Optional[str] = None,
                        user_id: str = Depends(_require_user)):
    """列出文档评论（按 parent_id 聚合线程）。"""
    if team_id:
        await _require_team_role(team_id, user_id, "viewer")
    async with _comment_tx(user_id, team_id) as db:
        rows = await (await db.execute(
            "SELECT * FROM doc_comments WHERE doc_id=? ORDER BY COALESCE(parent_id, id), created_at ASC",
            (doc_id,),
        )).fetchall()
    return {"items": [await _comment_row_to_dict(r) for r in rows]}


@app.put("/api/docs/{doc_id}/comments/{cid}")
async def update_comment(doc_id: str, cid: int, body: Optional[str] = None,
                         resolve: Optional[bool] = None, team_id: Optional[str] = None,
                         user_id: str = Depends(_require_user)):
    """编辑评论正文 或 解决/重开评论。仅作者可编辑正文；作者或属主可 resolve。"""
    if team_id:
        await _require_team_role(team_id, user_id, "viewer")
    now = _utcnow_iso()
    async with _comment_tx(user_id, team_id) as db:
        row = await (await db.execute("SELECT * FROM doc_comments WHERE id=? AND doc_id=?", (cid, doc_id))).fetchone()
        if not row:
            raise HTTPException(404, "评论不存在")
        if body is not None:
            if row["author_user_id"] != user_id:
                raise HTTPException(403, "只能编辑自己的评论")
            await db.execute("UPDATE doc_comments SET body=? WHERE id=?", (body, cid))
        if resolve is not None:
            await db.execute("UPDATE doc_comments SET status=?, resolved_at=?, resolver_user_id=? WHERE id=?",
                             ("resolved" if resolve else "open", now if resolve else None, user_id if resolve else None, cid))
    await _audit(user_id, team_id, "comment.resolve" if resolve else "comment.update", "doc", doc_id, f"cid={cid}")
    async with _comment_tx(user_id, team_id) as db:
        row = await (await db.execute("SELECT * FROM doc_comments WHERE id=?", (cid,))).fetchone()
    return await _comment_row_to_dict(row)


@app.delete("/api/docs/{doc_id}/comments/{cid}")
async def delete_comment(doc_id: str, cid: int, team_id: Optional[str] = None,
                         user_id: str = Depends(_require_user)):
    """删除评论（仅作者或属主）。"""
    if team_id:
        await _require_team_role(team_id, user_id, "viewer")
    async with _comment_tx(user_id, team_id) as db:
        row = await (await db.execute("SELECT author_user_id FROM doc_comments WHERE id=? AND doc_id=?", (cid, doc_id))).fetchone()
        if not row:
            raise HTTPException(404, "评论不存在")
        # 个人库：仅作者；团队库：作者或 member+
        if team_id:
            if row["author_user_id"] != user_id:
                await _require_team_role(team_id, user_id, "member")
        elif row["author_user_id"] != user_id:
            raise HTTPException(403, "只能删除自己的评论")
        await db.execute("DELETE FROM doc_comments WHERE id=?", (cid,))
    await _audit(user_id, team_id, "comment.delete", "doc", doc_id, f"cid={cid}")
    return {"ok": True}


@app.put("/api/docs/{doc_id}/suggestions/{sid}")
async def decide_suggestion(doc_id: str, sid: int, status: str, user_id: str = Depends(_require_user)):
    """接受/驳回建议。
    接受时：用 original_text 在文档内容中定位首次出现并原地替换为 proposed_text
    （未找到则回退追加到文末并提示）；同时版本号 +1、写版本快照与审计。"""
    if status not in ("accepted", "rejected"):
        raise HTTPException(400, "status 需为 accepted/rejected")
    replaced = False
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM suggestions WHERE id=? AND doc_id=?", (sid, doc_id))).fetchone()
        if not row:
            raise HTTPException(404, "建议不存在")
        if row["status"] != "pending":
            raise HTTPException(409, "该建议已处理")
        await db.execute("UPDATE suggestions SET status=?, decided_at=? WHERE id=?", (status, _utcnow_iso(), sid))
        if status == "accepted":
            doc = await (await db.execute("SELECT content, title, version FROM documents WHERE doc_id=?", (doc_id,))).fetchone()
            if doc:
                content = _doc_atrest_decrypt(doc["content"] or "")
                original_text = row["original_text"] or ""
                proposed_text = row["proposed_text"] or ""
                if original_text and original_text in content:
                    new_content = content.replace(original_text, proposed_text, 1)
                    replaced = True
                else:
                    # 未定位到原文：回退追加（带分隔），避免静默丢失修改意图
                    new_content = content + ("\n\n" if content else "") + proposed_text
                    replaced = False
                now = _utcnow_iso()
                new_version = doc["version"] + 1
                # 服务端版本快照：保存替换前的版本（沿用库内已存密文形态）
                await db.execute(
                    "INSERT INTO doc_versions (doc_id, version, title, content, created_at, created_by) VALUES (?,?,?,?,?,?)",
                    (doc_id, doc["version"], doc["title"], doc["content"], now, user_id),
                )
                await _prune_doc_versions(db, doc_id)
                await db.execute(
                    "UPDATE documents SET content=?, updated_at=?, version=? WHERE doc_id=?",
                    (_doc_atrest_encrypt(new_content), now, new_version, doc_id),
                )
    await _audit(user_id, None, "suggestion." + status, "doc", doc_id,
                 f"sid={sid} replaced={'yes' if replaced else 'fallback-append'}")
    return {"id": sid, "status": status, "replaced": replaced}


# ==================== 站内通知 ====================
@app.get("/api/notifications")
async def list_notifications(unread_only: int = 0, limit: int = 50, user_id: str = Depends(_require_user)):
    limit = max(1, min(limit, 200))
    async with _registry_transaction() as db:
        if unread_only:
            rows = await (await db.execute(
                "SELECT id, type, detail, link, is_read, created_at FROM notifications WHERE user_id=? AND is_read=0 ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT id, type, detail, link, is_read, created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )).fetchall()
        unread_count = (await (await db.execute("SELECT COUNT(*) AS c FROM notifications WHERE user_id=? AND is_read=0", (user_id,))).fetchone())["c"]
    return {"unread": unread_count, "items": [
        {"id": r["id"], "type": r["type"], "detail": r["detail"], "link": r["link"],
         "is_read": bool(r["is_read"]), "created_at": r["created_at"]} for r in rows
    ]}


@app.put("/api/notifications/{nid}/read")
async def mark_notification_read(nid: int, user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        await db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (nid, user_id))
    return {"ok": True}


@app.post("/api/notifications/read-all")
async def mark_all_read(user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        await db.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (user_id,))
    return {"ok": True}


@app.post("/api/notifications/digest/send")
async def send_my_digest_now(user_id: str = Depends(_require_user)):
    """立即给自己发送一封未读通知摘要（自助触发，不依赖后台循环与 EMAIL_DIGEST_ENABLED）。
    无 SMTP/无 email/无未读时返回原因而非报错。"""
    res = await _send_digest_to_user(user_id)
    await _audit(user_id, None, "digest.send_self", "user", user_id, res.get("reason") or "sent")
    return res


@app.post("/api/admin/notifications/digest")
async def admin_trigger_digest_scan(user_id: str = Depends(_require_user)):
    """管理员手动触发一次全局未读通知摘要扫描（用于预览/排障，不等后台循环周期）。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    results = await _digest_scan_once()
    sent = sum(1 for r in results if r.get("sent"))
    await _audit(user_id, None, "digest.admin_scan", "system", None, f"attempted={len(results)} sent={sent}")
    return {"attempted": len(results), "sent": sent, "results": results}


# ==================== 文档评审流 ====================
class ReviewRequest(BaseModel):
    reviewer_username: str = ""
    reviewers: Optional[list[str]] = None  # 多评审人用户名列表
    mode: str = "serial"  # serial(串行) | parallel(并行会签：同步骤多人全部通过才推进)
    team_id: Optional[str] = None
    comment: Optional[str] = None


class ReviewDecision(BaseModel):
    status: str  # approved/rejected
    comment: Optional[str] = None


@app.post("/api/docs/{doc_id}/review", status_code=201)
async def request_review(doc_id: str, req: ReviewRequest, user_id: str = Depends(_require_user)):
    """请求评审文档。支持多级审批链：reviewers 数组按顺序串行审批。
    机密文档自动追加系统管理员为额外审批步。"""
    # 构建评审人列表
    reviewer_names = []
    if req.reviewers:
        reviewer_names = [r.strip() for r in req.reviewers if r.strip()]
    elif req.reviewer_username:
        reviewer_names = [req.reviewer_username.strip()]
    if not reviewer_names:
        raise HTTPException(400, "至少需要一个评审人")

    # 查询评审人 user_id
    reviewer_ids = []
    async with _registry_transaction() as db:
        for name in reviewer_names:
            row = await (await db.execute("SELECT user_id FROM users WHERE username=?", (name,))).fetchone()
            if not row:
                raise HTTPException(404, f"评审人不存在：{name}")
            if row["user_id"] == user_id:
                raise HTTPException(400, "不能评审自己的文档")
            reviewer_ids.append(row["user_id"])

    # 校验文档存在 + 检查是否机密 → 追加 admin 审批步
    classification = "internal"
    if req.team_id:
        # 团队文档：在团队库中查找
        await _require_team_role(req.team_id, user_id, "member")
        async with _team_db_transaction(req.team_id) as db:
            doc = await (await db.execute("SELECT classification FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
            if not doc:
                raise HTTPException(404, "文档不存在")
            classification = doc["classification"] if "classification" in doc.keys() else "internal"
    else:
        # 个人文档
        async with _db_transaction(user_id) as db:
            doc = await (await db.execute("SELECT classification FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
            if not doc:
                raise HTTPException(404, "文档不存在")
            classification = doc["classification"] if "classification" in doc.keys() else "internal"
    # 机密文档：追加一名系统管理员作为额外审批步
    if classification == "confidential":
        async with _registry_transaction() as db:
            admin = await (await db.execute("SELECT user_id FROM users WHERE is_admin=1 LIMIT 1")).fetchone()
            if admin and admin["user_id"] not in reviewer_ids:
                reviewer_ids.append(admin["user_id"])
                reviewer_names.append("(admin)")

    now = _utcnow_iso()
    review_mode = req.mode if req.mode in ("serial", "parallel") else "serial"
    async with _registry_transaction() as db:
        cur = await db.execute(
            "INSERT INTO reviews (doc_id, team_id, requester_user_id, reviewer_user_id, status, comment, created_at) VALUES (?,?,?,?, 'pending', ?, ?) RETURNING id",
            (doc_id, req.team_id, user_id, reviewer_ids[0], req.comment, now),
        )
        rid = (await cur.fetchone())["id"]
        if review_mode == "parallel":
            # 并行会签：所有评审人在同一 step=1，需全部通过
            for uid in reviewer_ids:
                await db.execute(
                    "INSERT INTO review_steps (review_id, step, reviewer_user_id, status, mode) VALUES (?,?,?, 'pending', 'parallel')",
                    (rid, 1, uid),
                )
        else:
            # 串行：每个评审人一个 step
            for i, rid_uid in enumerate(reviewer_ids):
                await db.execute(
                    "INSERT INTO review_steps (review_id, step, reviewer_user_id, status, mode) VALUES (?,?,?, 'pending', 'serial')",
                    (rid, i + 1, rid_uid),
                )
    # 通知所有第一步评审人（并行模式通知所有人；串行只通知第一个）
    notify_ids = reviewer_ids if review_mode == "parallel" else [reviewer_ids[0]]
    for uid in notify_ids:
        step_desc = f"并行会签（{len(reviewer_ids)} 人）" if review_mode == "parallel" else f"第 1/{len(reviewer_ids)} 步"
        await _notify(uid, "review.request", detail=f"你被请求评审文档 {doc_id}（{step_desc}）", link=f"/?review={rid}")
    # 评审评注中的 @mention 通知
    await _notify_mentions(req.comment, author_id=user_id, link=f"/?review={rid}", detail_prefix="评审中提及你")
    await _audit(user_id, req.team_id, "review.request", "doc", doc_id, f"reviewers={reviewer_names},steps={len(reviewer_ids)},mode={review_mode}")
    return {"id": rid, "status": "pending", "steps": len(reviewer_ids), "current_step": 1, "mode": review_mode}


# ==================== P2: 通用工作流引擎（可配置多阶段审批）====================
class WorkflowDefCreate(BaseModel):
    name: str
    team_id: Optional[str] = None
    definition: dict  # {"steps":[{"reviewers":[...],"mode":"serial|parallel"}, ...]}


@app.post("/api/workflows", status_code=201)
async def create_workflow_def(req: WorkflowDefCreate, user_id: str = Depends(_require_user)):
    """创建工作流定义。definition.steps 为有序阶段列表，每阶段 reviewers + mode。
    团队工作流需 member+ 角色。"""
    if req.team_id:
        await _require_team_role(req.team_id, user_id, "member")
    steps = req.definition.get("steps")
    if not isinstance(steps, list) or not steps:
        raise HTTPException(400, "definition.steps 必须是非空数组")
    for s in steps:
        if not isinstance(s, dict) or not s.get("reviewers"):
            raise HTTPException(400, "每个 step 需含 reviewers")
        if s.get("mode") not in ("serial", "parallel", None):
            raise HTTPException(400, "mode 必须为 serial/parallel")
        if s.get("sla_hours") is not None:
            try:
                if float(s["sla_hours"]) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise HTTPException(400, "sla_hours 需为非负数")
        if s.get("escalate_to") is not None and not isinstance(s.get("escalate_to"), str):
            raise HTTPException(400, "escalate_to 需为用户名字符串")
    wfd_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO workflow_definitions (id, name, team_id, definition_json, created_by, created_at) VALUES (?,?,?,?,?,?)",
            (wfd_id, req.name, req.team_id, json.dumps(req.definition, ensure_ascii=False), user_id, now),
        )
    await _audit(user_id, req.team_id, "workflow.def.create", "workflow", wfd_id, req.name)
    return {"id": wfd_id, "name": req.name, "team_id": req.team_id, "definition": req.definition}


@app.get("/api/workflows")
async def list_workflow_defs(team_id: Optional[str] = None, user_id: str = Depends(_require_user)):
    """列出工作流定义。团队需 member+。"""
    async with _registry_transaction() as db:
        if team_id:
            sql = "SELECT id, name, team_id, definition_json, created_by, created_at FROM workflow_definitions WHERE team_id=? ORDER BY created_at DESC"
            rows = await (await db.execute(sql, (team_id,))).fetchall()
        else:
            sql = "SELECT id, name, team_id, definition_json, created_by, created_at FROM workflow_definitions ORDER BY created_at DESC"
            rows = await (await db.execute(sql)).fetchall()
    return {"items": [{"id": r["id"], "name": r["name"], "team_id": r["team_id"],
                        "definition": json.loads(r["definition_json"]), "created_by": r["created_by"],
                        "created_at": r["created_at"]} for r in rows]}


@app.post("/api/docs/{doc_id}/workflow/{wfd_id}/start", status_code=201)
async def start_workflow(doc_id: str, wfd_id: str, user_id: str = Depends(_require_user)):
    """在文档上启动一个工作流实例：按定义的多阶段创建 review + review_steps。
    每个阶段独立串行/并行；阶段间串行推进（阶段内并行需全部通过才进入下一阶段）。
    复用 review_steps 表（mode 列标记每步的串/并行，step 编号跨阶段递增）。"""
    async with _registry_transaction() as db:
        wfd = await (await db.execute("SELECT definition_json, team_id FROM workflow_definitions WHERE id=?", (wfd_id,))).fetchone()
    if not wfd:
        raise HTTPException(404, "工作流定义不存在")
    team_id = wfd["team_id"]
    if team_id:
        await _require_team_role(team_id, user_id, "member")
    definition = json.loads(wfd["definition_json"])
    steps = definition.get("steps", [])
    # 解析全部评审人 username → user_id
    all_names = []
    for s in steps:
        for n in s["reviewers"]:
            if n not in all_names:
                all_names.append(n)
    name_to_uid = {}
    async with _registry_transaction() as db:
        for name in all_names:
            row = await (await db.execute("SELECT user_id FROM users WHERE username=?", (name,))).fetchone()
            if not row:
                raise HTTPException(404, f"评审人不存在：{name}")
            name_to_uid[name] = row["user_id"]
    # 校验文档存在
    if team_id:
        async with _team_db_transaction(team_id) as db:
            doc = await (await db.execute("SELECT doc_id FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
    else:
        async with _db_transaction(user_id) as db:
            doc = await (await db.execute("SELECT doc_id FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
    if not doc:
        raise HTTPException(404, "文档不存在")
    # 建 review（reviewer_user_id 记首阶段首位）
    first_reviewers = steps[0]["reviewers"]
    first_uid = name_to_uid[first_reviewers[0]]
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        cur = await db.execute(
            "INSERT INTO reviews (doc_id, team_id, requester_user_id, reviewer_user_id, status, comment, created_at) VALUES (?,?,?,?, 'pending', ?, ?) RETURNING id",
            (doc_id, team_id, user_id, first_uid, f"workflow:{wfd_id}", now),
        )
        rid = (await cur.fetchone())["id"]
        # 建实例
        inst_id = secrets.token_urlsafe(12)
        await db.execute(
            "INSERT INTO workflow_instances (id, workflow_def_id, review_id, doc_id, team_id, status, created_at) VALUES (?,?,?,?,?, 'running', ?)",
            (inst_id, wfd_id, rid, doc_id, team_id, now),
        )
        # 按阶段建 steps：同阶段并行（step=阶段号），跨阶段递增；stage 列标记所属阶段
        for stage_idx, s in enumerate(steps):
            mode = s.get("mode", "serial")
            uids = [name_to_uid[n] for n in s["reviewers"]]
            if mode == "parallel":
                for uid in uids:
                    await db.execute(
                        "INSERT INTO review_steps (review_id, step, reviewer_user_id, status, mode, stage) VALUES (?,?,?, 'pending', 'parallel', ?)",
                        (rid, stage_idx + 1, uid, stage_idx),
                    )
            else:
                # 串行阶段内：多人在同 step 串行？语义上串行阶段通常 1 人；
                # 多人时按顺序拆成同阶段连续 step。简化：每阶段多人串行 → 同 step 号但顺序处理（review_steps 需区分）
                # 为保持与 decide_review 兼容（按 step 升序取 pending），给每人一个递增 step
                for j, uid in enumerate(uids):
                    await db.execute(
                        "INSERT INTO review_steps (review_id, step, reviewer_user_id, status, mode, stage) VALUES (?,?,?, 'pending', 'serial', ?)",
                        (rid, stage_idx * 100 + j + 1, uid, stage_idx),  # 阶段内留 100 档位避免与并行阶段号冲突
                    )
            # 记录该阶段 SLA 截止时间（sla_hours 缺省=0 表示不限时）
            sla_hours = float(s.get("sla_hours") or 0)
            if sla_hours > 0:
                deadline = (datetime.fromisoformat(now) + timedelta(hours=sla_hours)).isoformat()
            else:
                deadline = "9999-12-31T23:59:59+00:00"  # 不限时：远期占位
            await db.execute(
                "INSERT INTO workflow_sla (instance_id, stage, deadline, escalated) VALUES (?,?,?,0)",
                (inst_id, stage_idx, deadline),
            )
    # 通知第一阶段评审人
    first_mode = steps[0].get("mode", "serial")
    notify_uids = [name_to_uid[n] for n in first_reviewers] if first_mode == "parallel" else [first_uid]
    for uid in notify_uids:
        await _notify(uid, "review.request", detail=f"工作流评审文档 {doc_id}（阶段 1/{len(steps)}）", link=f"/?review={rid}")
    await _audit(user_id, team_id, "workflow.start", "doc", doc_id, f"wfd={wfd_id},stages={len(steps)}")
    return {"instance_id": inst_id, "review_id": rid, "stages": len(steps), "status": "running"}


@app.get("/api/reviews/incoming")
async def list_incoming_reviews(user_id: str = Depends(_require_user)):
    """待我评审的列表（含多步审批进度）。"""
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT id, doc_id, team_id, requester_user_id, status, comment, created_at, decided_at "
            "FROM reviews WHERE id IN (SELECT review_id FROM review_steps WHERE reviewer_user_id=? AND status='pending') "
            "OR reviewer_user_id=? ORDER BY created_at DESC",
            (user_id, user_id),
        )).fetchall()
        # 查每个 review 的步骤进度
        items = []
        for r in rows:
            steps = await (await db.execute(
                "SELECT step, reviewer_user_id, status, decided_at FROM review_steps WHERE review_id=? ORDER BY step",
                (r["id"],),
            )).fetchall()
            # 当前待我审批的步骤
            my_step = next((s for s in steps if s["reviewer_user_id"] == user_id and s["status"] == "pending"), None)
            items.append({
                "id": r["id"], "doc_id": r["doc_id"], "team_id": r["team_id"], "requester": r["requester_user_id"],
                "status": r["status"], "comment": r["comment"], "created_at": r["created_at"], "decided_at": r["decided_at"],
                "total_steps": len(steps), "current_step": my_step["step"] if my_step else None,
                "my_step_pending": my_step is not None,
                "steps_progress": [{"step": s["step"], "status": s["status"]} for s in steps],
            })
    return {"items": items}


@app.put("/api/reviews/{rid}")
async def decide_review(rid: int, req: ReviewDecision, user_id: str = Depends(_require_user)):
    """评审人裁决（approved/rejected）。多步审批：通过则推进下一步；全部通过→approved；驳回→关闭。"""
    if req.status not in ("approved", "rejected"):
        raise HTTPException(400, "status 需为 approved/rejected")
    # 先在事务中做 DB 操作，收集通知参数
    notify_list = []  # [(user_id, type, detail, link)]
    audit_list = []  # [(user_id, team_id, action, target_type, target_id, detail)]
    doc_status_update = None  # (requester_uid, doc_id, 'approved')
    step_num = 0
    total_steps = 0
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM reviews WHERE id=?", (rid,))).fetchone()
        if not row:
            raise HTTPException(404, "评审不存在")
        step = await (await db.execute(
            "SELECT * FROM review_steps WHERE review_id=? AND reviewer_user_id=? AND status='pending' ORDER BY step LIMIT 1",
            (rid, user_id),
        )).fetchone()
        if not step:
            raise HTTPException(403, "没有待你审批的步骤（或已审批）")
        # 阶段门控：若存在更早阶段(step 更小)仍 pending，则本步尚未到时，禁止裁决
        earlier_pending = await (await db.execute(
            "SELECT COUNT(*) AS c FROM review_steps WHERE review_id=? AND status='pending' AND step < ?",
            (rid, step["step"]),
        )).fetchone()
        if earlier_pending["c"] > 0:
            raise HTTPException(403, "前置阶段尚未完成，暂不可裁决")
        now = _utcnow_iso()
        step_num = step["step"]
        await db.execute("UPDATE review_steps SET status=?, comment=?, decided_at=? WHERE id=?",
                         (req.status, req.comment, now, step["id"]))
        requester = row["requester_user_id"]
        total_steps = (await (await db.execute("SELECT COUNT(*) AS c FROM review_steps WHERE review_id=?", (rid,))).fetchone())["c"]
        if req.status == "rejected":
            await db.execute("UPDATE reviews SET status='rejected', decided_at=? WHERE id=?", (now, rid))
            await db.execute("UPDATE review_steps SET status='skipped', decided_at=? WHERE review_id=? AND status='pending'", (now, rid))
        else:
            # 通过：检查同步骤是否还有未决的（并行模式：同 step 多人需全部通过）
            step_mode = step["mode"] if "mode" in step.keys() else "serial"
            pending_same_step = await (await db.execute(
                "SELECT COUNT(*) AS c FROM review_steps WHERE review_id=? AND step=? AND status='pending'",
                (rid, step["step"]),
            )).fetchone()
            if step_mode == "parallel" and pending_same_step["c"] > 0:
                # 并行模式：同步骤还有人没审完，不推进
                notify_list.append((requester, "review.decided",
                    f"文档评审已通过（{step['step']} 步骤剩余 {pending_same_step['c']} 人未审）", f"/?review={rid}"))
            else:
                # 检查是否有下一步
                next_step = await (await db.execute(
                    "SELECT * FROM review_steps WHERE review_id=? AND status='pending' ORDER BY step LIMIT 1", (rid,)
                )).fetchone()
                if next_step:
                    await db.execute("UPDATE reviews SET reviewer_user_id=? WHERE id=?", (next_step["reviewer_user_id"], rid))
                    notify_list.append((next_step["reviewer_user_id"], "review.request",
                        f"你被请求评审文档 {row['doc_id']}（第 {next_step['step']}/{total_steps} 步）", f"/?review={rid}"))
                    audit_list.append((user_id, row["team_id"], f"review.step.{step['step']}.approved", "review", str(rid), None))
                else:
                    await db.execute("UPDATE reviews SET status='approved', decided_at=? WHERE id=?", (now, rid))
                    doc_status_update = (requester, row["doc_id"], "approved")
                    audit_list.append((user_id, row["team_id"], "review.all_approved", "review", str(rid), None))
        notify_list.append((requester, "review.decided",
            f"文档评审步骤已{req.status}（第 {step_num}/{total_steps} 步）", f"/?review={rid}"))
    # 事务结束后发通知/审计（避免嵌套事务死锁）
    if doc_status_update:
        req_uid, doc_id, status = doc_status_update
        async with _db_transaction(req_uid) as udb:
            await udb.execute("UPDATE documents SET status=? WHERE doc_id=?", (status, doc_id))
    for uid, ntype, detail, link in notify_list:
        await _notify(uid, ntype, detail=detail, link=link)
    for uid, tid, action, ttype, tid_val, detail in audit_list:
        await _audit(uid, tid, action, ttype, tid_val, detail)
    # 裁决评注中的 @mention 通知
    await _notify_mentions(req.comment, author_id=user_id, link=f"/?review={rid}", detail_prefix="评审裁决中提及你")
    return {"id": rid, "status": req.status, "step": step_num, "total_steps": total_steps}


# ==================== 文档 CRUD API ====================
@app.post("/api/docs", status_code=201)
async def create_doc(req: DocCreateRequest, user_id: str = Depends(_require_scope("docs:write"))):
    if len(req.content.encode("utf-8")) > DOC_MAX_CONTENT_BYTES:
        raise HTTPException(413, f"文档内容超过 {DOC_MAX_CONTENT_BYTES} 字节限制")
    qerr = await _doc_quota_check_user(user_id, len(req.content.encode("utf-8")))
    if qerr:
        raise HTTPException(429, qerr)
    doc_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    is_enc = 1 if req.is_encrypted else 0
    enc_content = _doc_atrest_encrypt(req.content)
    etag = _compute_doc_etag(1, req.title, req.content)
    async with _db_transaction(user_id) as db:
        await db.execute(
            "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, is_encrypted, enc_salt, enc_iv, enc_iters, user_id, etag) VALUES (?, ?, ?, ?, ?, 'file', ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, req.title, enc_content, now, now, req.path or "", is_enc, req.enc_salt, req.enc_iv, req.enc_iters or 0, user_id, etag),
        )
    logger.info("创建文档 doc_id=%s title=%s path=%s enc=%d user=%s", doc_id, req.title[:30], req.path, is_enc, user_id)
    await _audit(user_id, None, "doc.create", "doc", doc_id, req.title)
    # 触发保存搜索订阅通知
    await _notify_saved_search_matches(req.title, req.content, user_id)
    return {"doc_id": doc_id, "title": req.title, "version": 1, "path": req.path or "", "is_encrypted": bool(is_enc), "etag": etag}


@app.get("/api/docs")
async def list_docs(limit: int = 500, include_archived: bool = False, user_id: str = Depends(_require_scope("docs:read"))):
    # 列出当前用户的云端节点（文件+文件夹，仅元数据）。排除已软删除。
    # 归档文档默认从列表隐藏（include_archived=true 时返回）。
    # 文件夹是目录树骨架：必须先于文件返回，否则一旦节点数超过 limit，
    # 被截断的根/中间文件夹会让 buildCloudTree 找不到父节点，整棵子树"消失"。
    limit = max(1, min(limit, 500))
    archived_clause = "" if include_archived else "AND archived=0"
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            f"SELECT doc_id, title, substr(content, 1, 60) AS preview, updated_at, version, share_code, kind, path, tags, starred, last_opened_at, is_encrypted, archived FROM documents WHERE deleted_at IS NULL AND user_id=? {archived_clause} ORDER BY (kind='folder') DESC, starred DESC, updated_at DESC LIMIT ?",
            (user_id, limit),
        )).fetchall()
    return {
        "items": [
            {
                "doc_id": r["doc_id"],
                "kind": r["kind"] or "file",
                "title": r["title"],
                "path": r["path"] or "",
                "preview": r["preview"] or "",
                "updated_at": r["updated_at"],
                "version": r["version"],
                "shared": bool(r["share_code"]),
                "tags": r["tags"] or "",
                "starred": bool(r["starred"]),
                "last_opened_at": r["last_opened_at"],
                "is_encrypted": bool(r["is_encrypted"]),
                "archived": bool(r["archived"]) if "archived" in r.keys() else False,
            }
            for r in rows
        ],
    }


@app.get("/api/docs/search")
async def search_docs(q: str = "", tag: str = "", starred: Optional[int] = None,
                      date: str = "all", sort: str = "updated", limit: int = 50,
                      user_id: str = Depends(_require_user)):
    """全文搜索 / 按标签 / 按收藏 / 按日期筛选，支持多种排序。

    路由必须定义在 /api/docs/{doc_id} 之前，否则会被路径参数捕获。
    """
    limit = max(1, min(limit, 200))
    sql = ("SELECT doc_id, title, substr(content, 1, 120) AS preview, "
           "updated_at, created_at, tags, starred, last_opened_at "
           "FROM documents WHERE deleted_at IS NULL AND user_id=?")
    params = [user_id]
    if q:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if tag:
        sql += " AND (tags LIKE ? OR tags = ?)"
        params += [f"%{tag}%", tag]
    if starred is not None:
        sql += " AND starred=?"
        params.append(1 if starred else 0)
    # 日期筛选（基于 updated_at）
    since = None
    if date and date != "all":
        now = datetime.now(timezone.utc)
        if date == "today":
            since = now - timedelta(days=1)
        elif date == "7d":
            since = now - timedelta(days=7)
        elif date == "30d":
            since = now - timedelta(days=30)
    if since:
        sql += " AND updated_at >= ?"
        params.append(since.isoformat())
    # 排序：opened=最近打开，created=创建时间，updated=更新时间
    order = {
        "opened": "last_opened_at DESC",
        "created": "created_at DESC",
        "updated": "updated_at DESC",
    }.get(sort, "updated_at DESC")
    sql += f" ORDER BY {order} LIMIT ?"
    params.append(limit)
    with span("search.docs", q=q, tag=tag, limit=limit):
        async with _db_transaction(user_id) as db:
            rows = await (await db.execute(sql, params)).fetchall()
    return {"items": [
        {
            "doc_id": r["doc_id"],
            "title": r["title"],
            "preview": r["preview"] or "",
            "updated_at": r["updated_at"],
            "created_at": r["created_at"],
            "tags": r["tags"] or "",
            "starred": bool(r["starred"]),
            "last_opened_at": r["last_opened_at"],
        } for r in rows
    ]}


@app.get("/api/docs/tags")
async def list_tags(user_id: str = Depends(_require_user)):
    """列出当前用户的所有标签及使用计数（路由须在 /api/docs/{doc_id} 之前）。"""
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT tags FROM documents WHERE deleted_at IS NULL AND user_id=? AND tags != ''",
            (user_id,)
        )).fetchall()
    counter = {}
    for r in rows:
        for t in (r["tags"] or "").split(','):
            t = t.strip()
            if t:
                counter[t] = counter.get(t, 0) + 1
    return {"items": [{"tag": k, "count": v} for k, v in sorted(counter.items())]}


@app.get("/api/docs/{doc_id}")
async def get_doc(doc_id: str, user_id: str = Depends(_require_scope("docs:read"))):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id = ? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
    if not row:
        raise HTTPException(404, "文档不存在")
    plain = _doc_atrest_decrypt(row["content"])
    # etag 列为空（旧数据）则惰性补算并落库，保证后续 PUT If-Match 可用
    etag = row["etag"] if "etag" in row.keys() and row["etag"] else _compute_doc_etag(row["version"], row["title"], plain)
    if "etag" not in row.keys() or not row["etag"]:
        async with _db_transaction(user_id) as db:
            await db.execute("UPDATE documents SET etag=? WHERE doc_id=?", (etag, doc_id))
    resp = {
        "doc_id": row["doc_id"],
        "title": row["title"],
        "content": plain,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "version": row["version"],
        "share_code": row["share_code"],
        "path": row["path"] or "",
        "kind": row["kind"] or "file",
        "tags": row["tags"] or "",
        "starred": bool(row["starred"]),
        "last_opened_at": row["last_opened_at"],
        "is_encrypted": bool(row["is_encrypted"]),
        "enc_salt": row["enc_salt"],
        "enc_iv": row["enc_iv"],
        "enc_iters": row["enc_iters"],
        "etag": etag,
        "status": row["status"] if "status" in row.keys() and row["status"] else "draft",
    }
    return resp


# ==================== E4：Transclusion（!include 复用） ====================
_INCLUDE_RE = re.compile(r"!include\[\[(.+?)\]\]|!include\[doc:(.+?)\]")
_TRANSCLUSION_MAX_DEPTH = 5


def _extract_section(content: str, section: str) -> str:
    """从 content 中提取某标题下的内容（到下一个同级或更高级标题前）。无该标题则返回全文。"""
    if not section:
        return content
    lines = content.split("\n")
    start = None
    level = None
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m and m.group(2).strip().lower() == section.strip().lower():
            start = i + 1
            level = len(m.group(1))
            break
    if start is None:
        return content
    out = []
    for ln in lines[start:]:
        m = re.match(r"^(#{1,6})\s+", ln)
        if m and len(m.group(1)) <= level:
            break
        out.append(ln)
    return "\n".join(out).strip("\n")


async def _resolve_transclusion(content: str, user_id: str, seen: set, depth: int = 0) -> str:
    """递归展开 !include 指令：!include[[target]] 与 !include[doc:target]，支持 #section。
    带循环检测（seen）与深度上限（_TRANSCLUSION_MAX_DEPTH）。"""
    if depth > _TRANSCLUSION_MAX_DEPTH or not content:
        return content

    def _expand(m):
        target = m.group(1) or m.group(2) or ""
        section = ""
        if "#" in target:
            target, section = target.split("#", 1)
        target = target.strip()
        return target, section

    # 因为替换需异步查库，先收集所有匹配，再逐个解析
    matches = list(_INCLUDE_RE.finditer(content))
    if not matches:
        return content
    # 构建 doc_id/title → 内容的映射
    resolved: dict[str, str] = {}
    targets = []
    for m in matches:
        t, sec = _expand(m)
        targets.append((t, sec))
    # 一次性查询用户库中所有候选文档（按 doc_id 或 title 命中）
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute("SELECT doc_id, title, content FROM documents WHERE deleted_at IS NULL AND user_id=?", (user_id,))).fetchall()
    by_id = {r["doc_id"]: r for r in rows}
    by_title = {(r["title"] or "").lower(): r for r in rows}

    def _lookup(t: str):
        if t in by_id:
            return by_id[t]
        return by_title.get(t.lower())

    # 逐匹配替换（递归展开被包含内容中的嵌套 include）
    def repl(m):
        t, sec = _expand(m)
        key = f"{t}#{sec}"
        if key in resolved:
            sub = resolved[key]
        else:
            doc = _lookup(t)
            if not doc:
                return f"<!-- transclusion: 未找到文档 {t} -->"
            if doc["doc_id"] in seen:
                return f"<!-- transclusion: 检测到循环引用 {t} -->"
            seen.add(doc["doc_id"])
            sub = _extract_section(_doc_atrest_decrypt(doc["content"] or ""), sec)
            # 递归展开嵌套 include（同步调用异步结果已预计算——这里用已查的 rows 再解析一次）
            # 简化：嵌套 include 在本层用同一 rows 池解析
            sub = _resolve_sync(sub, by_id, by_title, set(seen), depth + 1)
            seen.discard(doc["doc_id"])
            resolved[key] = sub
        return sub

    return _INCLUDE_RE.sub(repl, content)


def _resolve_sync(content: str, by_id: dict, by_title: dict, seen: set, depth: int) -> str:
    """同步递归展开（复用已查库结果，避免在替换回调里 await）。"""
    if depth > _TRANSCLUSION_MAX_DEPTH or not content:
        return content

    def repl(m):
        target = m.group(1) or m.group(2) or ""
        section = ""
        if "#" in target:
            target, section = target.split("#", 1)
        target = target.strip()
        doc = by_id.get(target) or by_title.get(target.lower())
        if not doc:
            return f"<!-- transclusion: 未找到文档 {target} -->"
        if doc["doc_id"] in seen:
            return f"<!-- transclusion: 检测到循环引用 {target} -->"
        seen.add(doc["doc_id"])
        sub = _extract_section(_doc_atrest_decrypt(doc["content"] or ""), section)
        sub = _resolve_sync(sub, by_id, by_title, seen, depth + 1)
        seen.discard(doc["doc_id"])
        return sub

    return _INCLUDE_RE.sub(repl, content)


@app.get("/api/docs/{doc_id}/resolved")
async def get_doc_resolved(doc_id: str, user_id: str = Depends(_require_user)):
    """返回展开 !include 后的内容（transclusion）。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT content FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
    if not row:
        raise HTTPException(404, "文档不存在")
    expanded = await _resolve_transclusion(_doc_atrest_decrypt(row["content"] or ""), user_id, {doc_id}, 0)
    return {"doc_id": doc_id, "content": expanded}


# ==================== E5：结构化链接图 + 断链检测 ====================
async def _recompute_doc_links(db, doc_id: str, user_id: str):
    """解析文档的结构化链接（复用 C5 _parse_doc_links），逐条核对目标存在性，写 doc_links 表。"""
    row = await (await db.execute("SELECT content FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
    if not row:
        await db.execute("DELETE FROM doc_links WHERE source_doc_id=?", (doc_id,))
        return
    refs = _parse_doc_links(_doc_atrest_decrypt(row["content"] or ""))
    now = _utcnow_iso()
    await db.execute("DELETE FROM doc_links WHERE source_doc_id=?", (doc_id,))
    if not refs:
        return
    # 候选：按 doc_id 或标题匹配（与 backlinks 一致）
    all_docs = await (await db.execute("SELECT doc_id, title FROM documents WHERE deleted_at IS NULL AND user_id=?", (user_id,))).fetchall()
    by_id = {r["doc_id"]: r for r in all_docs}
    by_title = {(r["title"] or "").lower(): r for r in all_docs}
    for ref in refs:
        kind = "wikilink"
        target_doc = by_id.get(ref) or by_title.get(ref.lower())
        broken = 0 if target_doc else 1
        target_id = target_doc["doc_id"] if target_doc else None
        await db.execute(
            "INSERT INTO doc_links (source_doc_id, target_ref, target_doc_id, kind, broken, checked_at) VALUES (?,?,?,?,?,?)",
            (doc_id, ref, target_id, kind, broken, now),
        )


@app.get("/api/docs/{doc_id}/links")
async def get_doc_links(doc_id: str, user_id: str = Depends(_require_user)):
    """返回文档的结构化链接图（实时校验断链）。"""
    async with _db_transaction(user_id) as db:
        if not await (await db.execute("SELECT 1 FROM documents WHERE doc_id=? AND user_id=? AND deleted_at IS NULL", (doc_id, user_id))).fetchone():
            raise HTTPException(404, "文档不存在")
        await _recompute_doc_links(db, doc_id, user_id)
        rows = await (await db.execute(
            "SELECT source_doc_id, target_ref, target_doc_id, kind, broken, checked_at FROM doc_links WHERE source_doc_id=? ORDER BY broken DESC, target_ref",
            (doc_id,),
        )).fetchall()
    return {"doc_id": doc_id, "items": [
        {"target_ref": r["target_ref"], "target_doc_id": r["target_doc_id"],
         "kind": r["kind"], "broken": bool(r["broken"]), "checked_at": r["checked_at"]}
        for r in rows
    ]}


@app.get("/api/admin/links/broken")
async def admin_broken_links(user_id: str = Depends(_require_user)):
    """全局断链报告（仅管理员）：遍历所有用户的文档库，收集结构化链接中断链。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    broken_items = []
    async with _registry_transaction() as rdb:
        users = await (await rdb.execute("SELECT user_id, username FROM users WHERE active=1 OR active IS NULL")).fetchall()
    for u in users:
        uid = u["user_id"]
        try:
            async with _db_transaction(uid) as db:
                docs = await (await db.execute("SELECT doc_id FROM documents WHERE deleted_at IS NULL AND user_id=?", (uid,))).fetchall()
                for d in docs:
                    await _recompute_doc_links(db, d["doc_id"], uid)
                rows = await (await db.execute(
                    "SELECT source_doc_id, target_ref, kind, checked_at FROM doc_links WHERE broken=1"
                )).fetchall()
                for r in rows:
                    broken_items.append({"user_id": uid, "username": u["username"],
                                         "source_doc_id": r["source_doc_id"], "target_ref": r["target_ref"],
                                         "kind": r["kind"], "checked_at": r["checked_at"]})
        except Exception as e:
            logger.warning("断链扫描用户 %s 失败: %s", uid, e)
    return {"broken_count": len(broken_items), "items": broken_items}


async def _link_check_loop():
    """后台周期性重建所有文档的链接图（LINK_CHECK_INTERVAL_HOURS=0 关闭）。"""
    while True:
        try:
            await asyncio.sleep(int(LINK_CHECK_INTERVAL_HOURS * 3600))
            if not await _am_leader():
                continue
            async with _registry_transaction() as rdb:
                users = await (await rdb.execute("SELECT user_id FROM users WHERE active=1 OR active IS NULL")).fetchall()
            for u in users:
                try:
                    async with _db_transaction(u["user_id"]) as db:
                        docs = await (await db.execute("SELECT doc_id FROM documents WHERE deleted_at IS NULL AND user_id=?", (u["user_id"],))).fetchall()
                        for d in docs:
                            await _recompute_doc_links(db, d["doc_id"], u["user_id"])
                except Exception as e:
                    logger.warning("链接检查用户 %s 失败: %s", u["user_id"], e)
            logger.info("断链检查扫描完成")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("断链检查循环异常: %s", e)
@app.put("/api/docs/{doc_id}")
async def update_doc(doc_id: str, req: DocUpdateRequest, if_match: Optional[str] = Header(None, alias="If-Match"), user_id: str = Depends(_require_scope("docs:write"))):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id = ? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        # 归档文档只读：禁止修改内容（冷存储）
        if "archived" in row.keys() and row["archived"]:
            raise HTTPException(403, "文档已归档（只读），请先取消归档或另存为新文档")
        # 冻结不可变性：被已冻结 release 引用的文档禁止修改
        frozen_by = await _doc_in_frozen_release(doc_id)
        if frozen_by:
            raise HTTPException(409, f"文档被已冻结的 release 引用（{frozen_by}），禁止修改（先解冻该 release）")
        # 文档级乐观锁：If-Match 失配 → 409（早于版本号检查，避免并发覆盖）
        cur_etag = row["etag"] if "etag" in row.keys() and row["etag"] else _compute_doc_etag(row["version"], row["title"], _doc_atrest_decrypt(row["content"]))
        if if_match is not None and if_match != cur_etag:
            raise HTTPException(409, "文档已被他人修改（ETag 失配），请刷新后重试")
        if req.version is not None and req.version != row["version"]:
            raise HTTPException(409, "版本冲突，请先拉取最新版本")
        title = req.title if req.title is not None else row["title"]
        # 正文：客户端传入则为明文（落库前静态加密）；未传则沿用库内已存形态（已加密/明文，勿重复加密）
        if req.content is not None:
            content = _doc_atrest_encrypt(req.content)
            new_plain = req.content
        else:
            content = row["content"]
            new_plain = _doc_atrest_decrypt(row["content"])
        old_plain = _doc_atrest_decrypt(row["content"])
        path = req.path if req.path is not None else row["path"]
        # 重命名（title 变化）时检查同目录下重名：同一 user+path 下不得有其他同名（未删除）节点
        if req.title is not None and title != row["title"]:
            dup = await (await db.execute(
                "SELECT 1 FROM documents WHERE user_id=? AND path=? AND title=? AND doc_id<>? AND deleted_at IS NULL",
                (user_id, path, title, doc_id),
            )).fetchone()
            if dup:
                raise HTTPException(409, "当前目录下已存在同名文档")
        if len(new_plain.encode("utf-8")) > DOC_MAX_CONTENT_BYTES:
            raise HTTPException(413, f"文档内容超过 {DOC_MAX_CONTENT_BYTES} 字节限制")
        now = _utcnow_iso()
        new_version = row["version"] + 1
        # 加密字段：显式传入 is_encrypted 时按其真假设置；取消加密时清空密文元数据。
        # 注意不能用 "is not None" 作为置 1 的条件——is_encrypted=False 时它 is not None 也为真，
        # 旧逻辑会错误地置 is_enc=1，导致取消加密后重新打开仍要求输入密码解密。
        if req.is_encrypted is not None:
            is_enc = 1 if req.is_encrypted else 0
            if is_enc:
                enc_salt = req.enc_salt if req.enc_salt is not None else row["enc_salt"]
                enc_iv = req.enc_iv if req.enc_iv is not None else row["enc_iv"]
                enc_iters = req.enc_iters if req.enc_iters is not None else row["enc_iters"]
            else:
                # 取消加密：清掉盐/IV/迭代数，避免残留导致误判为加密
                # （enc_iters 列为 NOT NULL，用 0 占位）
                enc_salt, enc_iv, enc_iters = None, None, 0
        else:
            is_enc = row["is_encrypted"]
            enc_salt, enc_iv, enc_iters = row["enc_salt"], row["enc_iv"], row["enc_iters"]
        new_etag = _compute_doc_etag(new_version, title, new_plain)
        await db.execute(
            "UPDATE documents SET title=?, content=?, updated_at=?, version=?, path=?, is_encrypted=?, enc_salt=?, enc_iv=?, enc_iters=?, etag=? WHERE doc_id=?",
            (title, content, now, new_version, path, is_enc, enc_salt, enc_iv, enc_iters, new_etag, doc_id),
        )
        # 服务端版本快照：存储更新前的版本，便于 diff/恢复（沿用库内已存正文形态）
        await db.execute(
            "INSERT INTO doc_versions (doc_id, version, title, content, created_at, created_by) VALUES (?,?,?,?,?,?)",
            (doc_id, row["version"], row["title"], row["content"], now, user_id),
        )
        await _prune_doc_versions(db, doc_id)
        # 贡献统计：计算增删行数（基于明文，避免对密文做无意义 diff）
        old_lines = (old_plain or "").split("\n")
        new_lines = (new_plain or "").split("\n")
        added = max(0, len(new_lines) - len(old_lines)) if len(new_lines) > len(old_lines) else 0
        deleted = max(0, len(old_lines) - len(new_lines)) if len(old_lines) > len(new_lines) else 0
        await db.execute(
            "INSERT INTO doc_contributions (doc_id, user_id, lines_added, lines_deleted, ts) VALUES (?,?,?,?,?)",
            (doc_id, user_id, added, deleted, now),
        )
    logger.info("更新文档 doc_id=%s version=%d enc=%d", doc_id, new_version, is_enc)
    await _audit(user_id, None, "doc.update", "doc", doc_id, f"v{new_version}")
    # 内容中的 @mention 通知（基于明文解析，密文无法匹配）
    await _notify_mentions(new_plain, author_id=user_id, link=f"/?doc={doc_id}", detail_prefix="文档中提及你")
    return {"doc_id": doc_id, "version": new_version, "updated_at": now, "is_encrypted": bool(is_enc), "etag": new_etag}


@app.delete("/api/docs/{doc_id}")
async def delete_doc(doc_id: str, permanent: int = 0, user_id: str = Depends(_require_user)):
    """软删除（默认）。permanent=1 时永久删除（回收站二次确认）。正在分享的文档禁止删除。"""
    # 法务保留：阻断删除（含软删/硬删）
    hold = await _doc_legal_hold(user_id=user_id)
    if hold:
        raise HTTPException(409, f"文档处于法务保留，禁止删除：{hold}")
    # 冻结不可变性：被已冻结 release 引用的文档禁止删除
    frozen_by = await _doc_in_frozen_release(doc_id)
    if frozen_by:
        raise HTTPException(409, f"文档被已冻结的 release 引用（{frozen_by}），禁止删除（先解冻该 release）")
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT doc_id, kind, share_code FROM documents WHERE doc_id = ? AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        # 正在分享的文档禁止删除：先取消分享
        if row["share_code"]:
            raise HTTPException(409, "该文档正在分享，请先取消分享后再删除")
        if permanent:
            await db.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            logger.info("永久删除文档 doc_id=%s", doc_id)
        else:
            await db.execute("UPDATE documents SET deleted_at=?, updated_at=? WHERE doc_id=?", (now, now, doc_id))
            logger.info("软删除文档 doc_id=%s", doc_id)
    await _audit(user_id, None, "doc.delete", "doc", doc_id, "permanent" if permanent else "soft")
    return {"deleted": True, "permanent": bool(permanent)}


# ==================== 服务端版本历史 ====================
async def _prune_doc_versions(db, doc_id: str):
    """C4：按 created_at DESC 保留前 MAX_VERSIONS_PER_DOC 条快照，删除多余的旧版本。
    幂等、方言无关（SQLite/PG 均支持子查询 DELETE）。失败仅告警不影响主流程。"""
    try:
        cap = MAX_VERSIONS_PER_DOC
        if cap <= 0:
            return
        await db.execute(
            "DELETE FROM doc_versions WHERE doc_id=? AND id NOT IN ("
            "  SELECT id FROM doc_versions WHERE doc_id=? ORDER BY id DESC LIMIT ?)",
            (doc_id, doc_id, cap),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("版本轮转清理失败 doc_id=%s err=%s", doc_id, e)


@app.get("/api/docs/{doc_id}/versions")
async def list_doc_versions(doc_id: str, limit: int = 50, user_id: str = Depends(_require_user)):
    """列出文档的服务端版本快照（最新在前）。"""
    limit = max(1, min(limit, 200))
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT id, version, title, content, created_at, created_by "
            "FROM doc_versions WHERE doc_id=? ORDER BY id DESC LIMIT ?",
            (doc_id, limit),
        )).fetchall()
    return {"items": [
        {"id": r["id"], "version": r["version"], "title": r["title"],
         "preview": (_doc_atrest_decrypt(r["content"]) or "")[:80], "created_at": r["created_at"], "created_by": r["created_by"]}
        for r in rows
    ]}


@app.get("/api/docs/{doc_id}/versions/{vid}")
async def get_doc_version(doc_id: str, vid: int, user_id: str = Depends(_require_user)):
    """获取某个版本快照的完整内容。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT id, version, title, content, created_at, created_by FROM doc_versions WHERE id=? AND doc_id=?",
            (vid, doc_id),
        )).fetchone()
    if not row:
        raise HTTPException(404, "版本不存在")
    return {"id": row["id"], "version": row["version"], "title": row["title"],
            "content": _doc_atrest_decrypt(row["content"]), "created_at": row["created_at"], "created_by": row["created_by"]}


def _version_diff_payload(old_content: str, new_content: str) -> dict:
    """计算两个文本的行级 diff，返回结构化结果 + unified 文本。

    结构化字段：added / removed / modified（行号对，1-based，基于 old 视图）。
    """
    old_lines = (old_content or "").splitlines()
    new_lines = (new_content or "").splitlines()
    # ndiff 标记：'  ' 同 / '- ' 仅旧 / '+ ' 仅新 / '? ' 指示行（忽略）
    seq = difflib.ndiff(old_lines, new_lines)
    unified = "\n".join(difflib.unified_diff(
        old_lines, new_lines, fromfile="v1", tofile="v2", lineterm=""))
    added, removed, modified = [], [], []
    old_idx = 0   # 1-based 行号（旧视图）
    new_idx = 0
    for line in seq:
        tag = line[:2]
        body = line[2:]
        if tag == "  ":
            old_idx += 1
            new_idx += 1
        elif tag == "- ":
            removed.append({"line": old_idx + 1, "content": body})
            old_idx += 1
        elif tag == "+ ":
            added.append({"line": new_idx + 1, "content": body})
            new_idx += 1
        elif tag == "? ":
            # ndiff 指示行，跳过
            continue
        # 连续的 - / + 对视为 modify（同一逻辑位置替换）
    # 近似 modified：成对的 (-)/(+) 数量取较小者
    pair = min(len(removed), len(added))
    for i in range(pair):
        modified.append({
            "old_line": removed[i]["line"],
            "old_content": removed[i]["content"],
            "new_line": added[i]["line"],
            "new_content": added[i]["content"],
        })
    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unified": unified,
        "added_count": len(added),
        "removed_count": len(removed),
        "modified_count": len(modified),
    }


@app.get("/api/docs/{doc_id}/versions/{v1}/diff/{v2}")
async def diff_doc_versions(doc_id: str, v1: int, v2: str, user_id: str = Depends(_require_user)):
    """对比两个文档版本（v1→v2）的行级 diff。

    v1 为 doc_versions.id（整数）；v2 为 doc_versions.id 或字符串 "current"
    （表示对比文档当前内容，即最新未快照版本）。
    """
    async with _db_transaction(user_id) as db:
        # 权限：文档需属于当前用户
        cur = await (await db.execute(
            "SELECT content, title, version FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?",
            (doc_id, user_id),
        )).fetchone()
        if not cur:
            raise HTTPException(404, "文档不存在")
        old = await (await db.execute(
            "SELECT id, version, title, content, created_at, created_by FROM doc_versions WHERE id=? AND doc_id=?",
            (v1, doc_id),
        )).fetchone()
        if not old:
            raise HTTPException(404, "版本 v1 不存在")
        if v2 == "current":
            new = {"id": None, "version": cur["version"], "title": cur["title"],
                   "content": cur["content"], "created_at": None, "created_by": None}
        else:
            try:
                v2_id = int(v2)
            except (TypeError, ValueError):
                raise HTTPException(400, "v2 需为版本 id 或 'current'")
            new_row = await (await db.execute(
                "SELECT id, version, title, content, created_at, created_by FROM doc_versions WHERE id=? AND doc_id=?",
                (v2_id, doc_id),
            )).fetchone()
            if not new_row:
                raise HTTPException(404, "版本 v2 不存在")
            new = new_row
    diff = _version_diff_payload(_doc_atrest_decrypt(old["content"]), _doc_atrest_decrypt(new["content"]))
    return {
        "doc_id": doc_id,
        "v1": {"id": old["id"], "version": old["version"], "title": old["title"],
               "created_at": old["created_at"], "created_by": old["created_by"]},
        "v2": {"id": new["id"], "version": new["version"], "title": new["title"],
               "created_at": new["created_at"], "created_by": new["created_by"]},
        "diff": diff,
    }


