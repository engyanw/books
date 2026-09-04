async def _digest_scan_once() -> list:
    """单次扫描：对所有有未读通知的用户发送摘要。供 loop 与测试/管理端点调用。
    返回每个用户的发送结果列表（仅含被尝试的用户）。"""
    if not EMAIL_DIGEST_ENABLED and not (SMTP_HOST and SMTP_FROM):
        # 既未启用又无 SMTP：直接空返回（测试可临时设 EMAIL_DIGEST_ENABLED=1 + SMTP_* 触发）
        return []
    async with _registry_transaction() as db:
        # 仅取有未读通知的用户，避免全表扫描
        if EMAIL_DIGEST_LOOKBACK_DAYS > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=EMAIL_DIGEST_LOOKBACK_DAYS)).isoformat()
            rows = await (await db.execute(
                "SELECT DISTINCT user_id FROM notifications WHERE is_read=0 AND created_at>=?",
                (cutoff,))).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT DISTINCT user_id FROM notifications WHERE is_read=0")).fetchall()
    results = []
    for r in rows:
        try:
            results.append(await _send_digest_to_user(r["user_id"]))
        except Exception as e:
            results.append({"user_id": r["user_id"], "unread": 0, "sent": False, "reason": f"error:{e}"})
    return results


async def _digest_loop():
    """每日未读通知邮件摘要后台循环（间隔 EMAIL_DIGEST_INTERVAL_SECONDS）。
    多实例下仅 leader 执行；无 SMTP 配置时空转。"""
    while True:
        try:
            await asyncio.sleep(EMAIL_DIGEST_INTERVAL_SECONDS)
            if not await _am_leader():
                continue
            if not EMAIL_DIGEST_ENABLED:
                continue
            await _digest_scan_once()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("通知摘要循环异常: %s", e)


@app.get("/api/guests/accept")
async def accept_guest_invite(token: str, password: str = ""):
    """Guest 接受邀请：设密码完成注册（首次需带 password）。"""
    async with _registry_transaction() as db:
        inv = await (await db.execute("SELECT * FROM guest_invites WHERE token=? AND status='pending'", (token,))).fetchone()
        if not inv:
            raise HTTPException(404, "邀请不存在或已使用")
        if not password or len(password) < 6:
            return {"status": "pending", "guest_username": inv["guest_username"], "message": "请设置密码（≥6 位）"}
        # 创建 Guest 账号
        guest_id = secrets.token_urlsafe(12)
        now = _utcnow_iso()
        try:
            await db.execute(
                "INSERT INTO users (user_id, username, password_hash, created_at, is_admin, is_guest, email) VALUES (?,?,?,?,0,1,?)",
                (guest_id, inv["guest_username"], _hash_password(password), now, inv["email"]),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "用户名已被占用")
        await db.execute("UPDATE guest_invites SET status='accepted', accepted_at=? WHERE token=?", (now, token))
    await _audit(inv["owner_user_id"], None, "guest.accept", "user", guest_id, inv["guest_username"])
    return {"status": "accepted", "user_id": guest_id, "username": inv["guest_username"]}


# Guest 登录后可访问的文档列表
@app.get("/api/guest/docs")
async def guest_docs(user_id: str = Depends(_require_user)):
    """Guest 账号专属：列出被 ACL 授权可访问的文档。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT is_guest FROM users WHERE user_id=?", (user_id,))).fetchone()
    if not row or not row["is_guest"]:
        raise HTTPException(403, "仅 Guest 账号可访问")
    # 遍历所有用户库，找有该 guest 的 ACL 记录
    results = []
    users_dir = _data_dir() / "users"
    if users_dir.exists():
        for udb_path in users_dir.glob("*/docs.db"):
            try:
                import sqlite3 as _s
                conn = _s.connect(str(udb_path)); conn.row_factory = _s.Row
                owner_uid = udb_path.parent.name
                acl_rows = conn.execute("SELECT doc_id, permission FROM doc_acl WHERE user_id=?", (user_id,)).fetchall()
                for acl in acl_rows:
                    doc = conn.execute("SELECT doc_id, title, updated_at FROM documents WHERE doc_id=? AND deleted_at IS NULL", (acl["doc_id"],)).fetchone()
                    if doc:
                        results.append({"doc_id": doc["doc_id"], "title": doc["title"], "permission": acl["permission"], "owner_uid": owner_uid, "updated_at": doc["updated_at"]})
                conn.close()
            except Exception:
                pass
    return {"items": results}


@app.get("/api/guest/docs/{owner_uid}/{doc_id}")
async def guest_get_doc(owner_uid: str, doc_id: str, user_id: str = Depends(_require_user)):
    """Guest 访问被授权的文档内容。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT is_guest FROM users WHERE user_id=?", (user_id,))).fetchone()
    if not row or not row["is_guest"]:
        raise HTTPException(403, "仅 Guest 账号可访问")
    async with _db_transaction(owner_uid) as db:
        acl = await (await db.execute("SELECT permission, expires_at FROM doc_acl WHERE doc_id=? AND user_id=?", (doc_id, user_id))).fetchone()
        if not acl:
            raise HTTPException(403, "无权访问该文档")
        # 检查 ACL 过期
        if acl["expires_at"] and acl["expires_at"] < _utcnow_iso():
            raise HTTPException(403, "访问权限已过期")
        doc = await (await db.execute("SELECT doc_id, title, content, updated_at FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
    if not doc:
        raise HTTPException(404, "文档不存在")
    return {"doc_id": doc["doc_id"], "title": doc["title"], "content": _doc_atrest_decrypt(doc["content"]), "updated_at": doc["updated_at"], "permission": acl["permission"]}


# ==================== P1: 批量操作 ====================
class BatchOpRequest(BaseModel):
    doc_ids: list[str]
    action: str  # tag/star/unstar/delete/move
    value: Optional[str] = None  # tag=value, move=path


@app.post("/api/docs/batch")
async def batch_op_docs(req: BatchOpRequest, user_id: str = Depends(_require_user)):
    """批量操作个人文档：加标签/收藏/取消收藏/删除/移动。"""
    if not req.doc_ids or len(req.doc_ids) > 500:
        raise HTTPException(400, "doc_ids 需为非空数组（≤500）")
    action = req.action
    if action not in ("tag", "star", "unstar", "delete", "move"):
        raise HTTPException(400, f"不支持的操作：{action}")
    placeholders = ",".join("?" * len(req.doc_ids))
    now = _utcnow_iso()
    affected = 0
    async with _db_transaction(user_id) as db:
        for doc_id in req.doc_ids:
            doc = await (await db.execute(f"SELECT 1 FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
            if not doc:
                continue
            if action == "tag":
                await db.execute("UPDATE documents SET tags=? WHERE doc_id=?", (req.value or "", doc_id))
            elif action == "star":
                await db.execute("UPDATE documents SET starred=1 WHERE doc_id=?", (doc_id,))
            elif action == "unstar":
                await db.execute("UPDATE documents SET starred=0 WHERE doc_id=?", (doc_id,))
            elif action == "delete":
                await db.execute("UPDATE documents SET deleted_at=? WHERE doc_id=?", (now, doc_id))
            elif action == "move":
                await db.execute("UPDATE documents SET path=? WHERE doc_id=?", (req.value or "", doc_id))
            affected += 1
    await _audit(user_id, None, f"doc.batch.{action}", "doc", None, f"count={affected}")
    return {"action": action, "affected": affected}


@app.post("/api/teams/{tid}/docs/batch")
async def batch_op_team_docs(tid: str, req: BatchOpRequest, user_id: str = Depends(_require_user)):
    """批量操作团队文档（member+）。"""
    await _require_team_role(tid, user_id, "member")
    if not req.doc_ids or len(req.doc_ids) > 500:
        raise HTTPException(400, "doc_ids 需为非空数组（≤500）")
    action = req.action
    if action not in ("tag", "star", "unstar", "delete", "move"):
        raise HTTPException(400, f"不支持的操作：{action}")
    now = _utcnow_iso()
    affected = 0
    async with _team_db_transaction(tid) as db:
        for doc_id in req.doc_ids:
            doc = await (await db.execute("SELECT 1 FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
            if not doc:
                continue
            if action == "tag":
                await db.execute("UPDATE documents SET tags=? WHERE doc_id=?", (req.value or "", doc_id))
            elif action == "star":
                await db.execute("UPDATE documents SET starred=1 WHERE doc_id=?", (doc_id,))
            elif action == "unstar":
                await db.execute("UPDATE documents SET starred=0 WHERE doc_id=?", (doc_id,))
            elif action == "delete":
                # 团队文档正在分享的仍拦截
                sc = await (await db.execute("SELECT share_code FROM documents WHERE doc_id=?", (doc_id,))).fetchone()
                if sc and sc["share_code"]:
                    continue
                await db.execute("UPDATE documents SET deleted_at=? WHERE doc_id=?", (now, doc_id))
            elif action == "move":
                await db.execute("UPDATE documents SET path=? WHERE doc_id=?", (req.value or "", doc_id))
            affected += 1
    await _audit(user_id, tid, f"team.doc.batch.{action}", "doc", None, f"count={affected}")
    return {"action": action, "affected": affected}


# ==================== P1: 文档 Backlinks ====================
_WIKILINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
_DOCLINK_RE = re.compile(r"\[[^\]]*?\]\(doc:([^)\s]+)\)")


def _parse_doc_links(content: str) -> list[str]:
    """C5：结构化解析文档链接，而非全文 substring 扫描 doc_id。
    支持两种语法：[[target]]（wikilink，可带 |alias 或 #section）与 [text](doc:target)。
    返回去重后（保留出现顺序）的 target 引用列表。
    """
    if not content:
        return []
    refs: list[str] = []
    seen: set = set()
    for m in _WIKILINK_RE.finditer(content):
        t = m.group(1).split("|")[0].split("#")[0].strip()
        if t and t not in seen:
            seen.add(t)
            refs.append(t)
    for m in _DOCLINK_RE.finditer(content):
        t = m.group(1).strip()
        if t and t not in seen:
            seen.add(t)
            refs.append(t)
    return refs


def _ref_matches(ref: str, doc_id: str, title: str) -> bool:
    """判断一个结构化引用是否指向给定文档（按 doc_id 或标题精确匹配，大小写不敏感）。"""
    ref = (ref or "").strip()
    if not ref:
        return False
    rl = ref.lower()
    if rl == (doc_id or "").lower():
        return True
    if title and rl == title.lower():
        return True
    return False


@app.get("/api/docs/{doc_id}/backlinks")
async def get_doc_backlinks(doc_id: str, user_id: str = Depends(_require_user)):
    """查找哪些文档引用了当前文档（结构化 wikilink/doc:link 精确匹配）。
    先用 LIKE 缩小候选集，再用 _parse_doc_links 确认，避免 substring 误报。"""
    results = []
    cur_title = None
    # 当前文档标题（用于按标题匹配 wikilink）
    async with _db_transaction(user_id) as db:
        c = await (await db.execute("SELECT title FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if c:
            cur_title = c["title"]

    async def _scan_db(db, q_user):
        # 先用 LIKE 缩小候选集（命中 doc_id 或标题），再结构化确认
        if cur_title:
            sql = ("SELECT doc_id, title, path, content FROM documents WHERE deleted_at IS NULL "
                   + ("AND user_id=? " if q_user else "") +
                   "AND (content LIKE ? OR content LIKE ?)")
            base = [f"%{doc_id}%", f"%{cur_title}%"]
        else:
            sql = ("SELECT doc_id, title, path, content FROM documents WHERE deleted_at IS NULL "
                   + ("AND user_id=? " if q_user else "") +
                   "AND content LIKE ?")
            base = [f"%{doc_id}%"]
        params = ([user_id] + base) if q_user else base
        rows = await (await db.execute(sql, params)).fetchall()
        out = []
        for r in rows:
            if r["doc_id"] == doc_id:
                continue
            refs = _parse_doc_links(r["content"])
            if any(_ref_matches(x, doc_id, cur_title) for x in refs):
                out.append(r)
        return out

    # 个人库
    async with _db_transaction(user_id) as db:
        for r in await _scan_db(db, True):
            results.append({"doc_id": r["doc_id"], "title": r["title"], "path": r["path"] or "", "team_id": None, "team_name": None})
    # 团队库
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
                for r in await _scan_db(db, False):
                    results.append({"doc_id": r["doc_id"], "title": r["title"], "path": r["path"] or "", "team_id": tid, "team_name": tname})
        except Exception:
            pass
    return {"items": results}


# ==================== P2: 保存搜索/订阅 ====================
class SavedSearchRequest(BaseModel):
    name: str
    query: str


# ==================== P2: 依赖图可视化 ====================
@app.get("/api/docs/{doc_id}/dependency-graph")
async def get_dependency_graph(doc_id: str, user_id: str = Depends(_require_user)):
    """返回文档依赖图数据：节点=文档，边=引用关系。
    入边/出边均基于结构化 wikilink/doc:link 解析（_parse_doc_links）精确匹配，
    不再全文 substring 扫 doc_id，杜绝误报。"""
    nodes = set()
    edges = []
    nodes.add(doc_id)
    async with _db_transaction(user_id) as db:
        cur = await (await db.execute("SELECT content, title FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        cur_title = cur["title"] if cur else None
        cur_content = _doc_atrest_decrypt(cur["content"]) if cur else ""
        # 入边：哪些文档的结构化链接指向当前文档
        in_rows = await (await db.execute(
            "SELECT doc_id, title, content FROM documents WHERE deleted_at IS NULL AND user_id=? "
            "AND (content LIKE ? OR content LIKE ?) AND doc_id<>?",
            (user_id, f"%{doc_id}%", f"%{cur_title}%" if cur_title else "%", doc_id),
        )).fetchall()
        for r in in_rows:
            refs = _parse_doc_links(_doc_atrest_decrypt(r["content"]))
            if any(_ref_matches(x, doc_id, cur_title) for x in refs):
                nodes.add(r["doc_id"])
                edges.append({"from": r["doc_id"], "to": doc_id})
        # 出边：当前文档的结构化链接指向哪些文档（按 doc_id 或标题匹配）
        if cur:
            out_refs = _parse_doc_links(cur_content)
            all_docs = await (await db.execute("SELECT doc_id, title FROM documents WHERE deleted_at IS NULL AND user_id=?", (user_id,))).fetchall()
            for d in all_docs:
                if d["doc_id"] == doc_id:
                    continue
                if any(_ref_matches(x, d["doc_id"], d["title"]) for x in out_refs):
                    nodes.add(d["doc_id"])
                    edges.append({"from": doc_id, "to": d["doc_id"]})
        # 节点元数据
        node_ids = list(nodes)
        placeholders = ",".join("?" * len(node_ids))
        node_rows = await (await db.execute(
            f"SELECT doc_id, title FROM documents WHERE doc_id IN ({placeholders})", node_ids
        )).fetchall()
    return {
        "nodes": [{"id": r["doc_id"], "title": r["title"], "is_current": r["doc_id"] == doc_id} for r in node_rows],
        "edges": edges,
    }


@app.post("/api/saved-searches", status_code=201)
async def create_saved_search(req: SavedSearchRequest, user_id: str = Depends(_require_user)):
    sid = "ss-" + secrets.token_urlsafe(8)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute("INSERT INTO saved_searches (id, user_id, name, query, created_at) VALUES (?,?,?,?,?)",
                         (sid, user_id, req.name[:64], req.query[:200], now))
    return {"id": sid, "name": req.name, "query": req.query}


@app.get("/api/saved-searches")
async def list_saved_searches(user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        rows = await (await db.execute("SELECT id, name, query, created_at FROM saved_searches WHERE user_id=? ORDER BY created_at DESC", (user_id,))).fetchall()
    return {"items": [{"id": r["id"], "name": r["name"], "query": r["query"], "created_at": r["created_at"]} for r in rows]}


@app.delete("/api/saved-searches/{sid}")
async def delete_saved_search(sid: str, user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        if not await (await db.execute("SELECT 1 FROM saved_searches WHERE id=? AND user_id=?", (sid, user_id))).fetchone():
            raise HTTPException(404, "搜索不存在")
        await db.execute("DELETE FROM saved_searches WHERE id=?", (sid,))
    return {"ok": True}


# ==================== P2: 多语言文档变体 ====================
class LinkVariantRequest(BaseModel):
    target_doc_id: str
    target_lang: str  # zh/en/...


@app.post("/api/docs/{doc_id}/link-variant")
async def link_variant(doc_id: str, req: LinkVariantRequest, user_id: str = Depends(_require_user)):
    """将当前文档与另一文档关联为多语言变体。"""
    group_id = "var-" + secrets.token_urlsafe(8)
    # 确定语言：当前文档用 query param lang（默认 zh）
    cur_lang = "zh"  # 简化：默认中文
    async with _registry_transaction() as db:
        # 两个文档都加入变体组
        await db.execute("INSERT OR REPLACE INTO doc_variants (group_id, doc_id, lang, owner_user_id) VALUES (?,?,?,?)",
                         (group_id, doc_id, cur_lang, user_id))
        await db.execute("INSERT OR REPLACE INTO doc_variants (group_id, doc_id, lang, owner_user_id) VALUES (?,?,?,?)",
                         (group_id, req.target_doc_id, req.target_lang, user_id))
    return {"group_id": group_id, "doc_id": doc_id, "lang": cur_lang, "target": req.target_doc_id, "target_lang": req.target_lang}


@app.get("/api/docs/{doc_id}/variants")
async def list_variants(doc_id: str, user_id: str = Depends(_require_user)):
    """列出文档的多语言变体。"""
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT v.group_id, v.doc_id, v.lang FROM doc_variants v WHERE v.group_id IN "
            "(SELECT group_id FROM doc_variants WHERE doc_id=?)",
            (doc_id,),
        )).fetchall()
    return {"items": [{"doc_id": r["doc_id"], "lang": r["lang"], "group_id": r["group_id"]} for r in rows if r["doc_id"] != doc_id]}


# ==================== P2: i18n UI 文案 + 离线移动端同步 ====================
@app.get("/api/i18n/{locale}")
async def get_i18n_strings(locale: str):
    """返回某 locale 的 UI 文案表（前端按语言拉取，缓存进 Service Worker）。"""
    import i18n as _i18n
    return {"locale": locale, "default": _i18n.DEFAULT_LOCALE,
            "locales": _i18n.locales(), "strings": _i18n.strings_for(locale)}


@app.get("/api/i18n")
async def list_i18n_locales():
    """列出可用 UI 语言。"""
    import i18n as _i18n
    return {"locales": _i18n.locales(), "default": _i18n.DEFAULT_LOCALE}


@app.get("/api/sync/bundle")
async def sync_bundle(since: str = "", limit: int = 500, user_id: str = Depends(_require_scope("docs:read"))):
    """离线移动端增量同步：返回当前用户自 since 之后变更的文档快照 + 新游标。

    客户端用 cursor（updated_at）下次传入 since，仅拉增量。
    删除（软删）也一并返回 deleted 标记，便于客户端清理本地副本。
    """
    limit = max(1, min(limit, 2000))
    async with _db_transaction(user_id) as db:
        if since:
            rows = await (await db.execute(
                "SELECT doc_id, title, content, path, kind, version, status, updated_at, deleted_at "
                "FROM documents WHERE updated_at > ? ORDER BY updated_at ASC LIMIT ?",
                (since, limit),
            )).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT doc_id, title, content, path, kind, version, status, updated_at, deleted_at "
                "FROM documents ORDER BY updated_at ASC LIMIT ?",
                (limit,),
            )).fetchall()
    items = [{"doc_id": r["doc_id"], "title": r["title"], "content": r["content"],
              "path": r["path"], "kind": r["kind"], "version": r["version"],
              "status": r["status"], "updated_at": r["updated_at"],
              "deleted": bool(r["deleted_at"])} for r in rows]
    cursor = max((r["updated_at"] for r in rows), default=since) if rows else since
    return {"items": items, "cursor": cursor, "count": len(items), "has_more": len(items) >= limit}


# PWA：离线移动端外壳（manifest + service worker）
_PWA_MANIFEST = {
    "name": "Markdown 文档编辑器",
    "short_name": "MDE",
    "description": "企业团队 Markdown 文档协同编辑（支持离线）",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#2563eb",
    "icons": [{"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"}],
}

_PWA_SW = """// MDE Service Worker —— 离线移动端
const CACHE = 'mde-shell-v1';
const ASSETS = ['/','/index.html','/styles.css','/app.js','/manifest.webmanifest'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(()=>{}));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // API 走 network-first（断网回退缓存）
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  // 静态外壳走 cache-first
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
    const copy = resp.clone(); caches.open(CACHE).then(c => c.put(e.request, copy));
    return resp;
  }).catch(() => caches.match(e.request))));
});
"""


@app.get("/manifest.webmanifest")
async def pwa_manifest():
    return JSONResponse(_PWA_MANIFEST, media_type="application/manifest+json")


@app.get("/sw.js")
async def pwa_service_worker():
    return Response(content=_PWA_SW, media_type="application/javascript")


# ==================== P2: 定时发布 ====================
class SchedulePublishRequest(BaseModel):
    publish_at: str  # ISO 时间


@app.post("/api/docs/{doc_id}/schedule-publish")
async def schedule_publish(doc_id: str, req: SchedulePublishRequest, user_id: str = Depends(_require_user)):
    """安排文档在指定时间自动发布（approved→published）。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT status FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        # 存储发布计划到 doc_acl 表的 meta（简化：用 documents 的 updated_at 字段旁加 meta）
        # 简化实现：直接在 documents 表加 scheduled_publish_at 列（已通过 ALTER 兼容）
        try:
            await db.execute("ALTER TABLE documents ADD COLUMN scheduled_publish_at TEXT")
        except sqlite3.OperationalError:
            pass
        await db.execute("UPDATE documents SET scheduled_publish_at=? WHERE doc_id=?", (req.publish_at, doc_id))
    await _audit(user_id, None, "doc.schedule_publish", "doc", doc_id, req.publish_at)
    return {"doc_id": doc_id, "scheduled_publish_at": req.publish_at}


@app.get("/api/docs/scheduled-publish/check")
async def check_scheduled_publish(user_id: str = Depends(_require_user)):
    """检查并执行到期的定时发布（approved→published）。"""
    now = _utcnow_iso()
    published = []
    async with _db_transaction(user_id) as db:
        try:
            rows = await (await db.execute(
                "SELECT doc_id, scheduled_publish_at FROM documents WHERE deleted_at IS NULL AND user_id=? AND scheduled_publish_at IS NOT NULL AND scheduled_publish_at <= ? AND status='approved'",
                (user_id, now),
            )).fetchall()
        except sqlite3.OperationalError:
            return {"published": []}
        for r in rows:
            await db.execute("UPDATE documents SET status='published', scheduled_publish_at=NULL WHERE doc_id=?", (r["doc_id"],))
            published.append(r["doc_id"])
    return {"published": published, "count": len(published)}


# ==================== P1: 文档分析 ====================
@app.get("/api/analytics/dashboard")
async def content_dashboard(team_id: Optional[str] = None, user_id: str = Depends(_require_user)):
    """P1-9 内容分析仪表盘：跨个人/团队聚合——状态分布、类型分布、14 天活跃趋势、
    贡献榜、待审瓶颈。不逐篇解密正文，开销可控。"""
    from datetime import datetime, timezone, timedelta
    if team_id:
        await _require_team_role(team_id, user_id, "viewer")
    # 个人库聚合（team_id 暂按个人维度；团队库后续扩展）
    async with _db_transaction(user_id) as db:
        sc = await (await db.execute(
            "SELECT status, COUNT(*) AS c FROM documents WHERE deleted_at IS NULL GROUP BY status"
        )).fetchall()
        kc = await (await db.execute(
            "SELECT kind, COUNT(*) AS c FROM documents WHERE deleted_at IS NULL GROUP BY kind"
        )).fetchall()
        tot = await (await db.execute(
            "SELECT COUNT(*) AS c, SUM(CASE WHEN archived=1 THEN 1 ELSE 0 END) AS archived "
            "FROM documents WHERE deleted_at IS NULL"
        )).fetchone()
        # 近 14 天按天活跃（按 updated_at 日期分桶）
        since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        act = await (await db.execute(
            "SELECT substr(updated_at,1,10) AS d, COUNT(*) AS c FROM documents "
            "WHERE deleted_at IS NULL AND updated_at>=? GROUP BY d ORDER BY d", (since,)
        )).fetchall()
        # 贡献榜（doc_contributions 已落库）
        leaders = await (await db.execute(
            "SELECT user_id, SUM(lines_added) AS added, COUNT(*) AS edits "
            "FROM doc_contributions GROUP BY user_id ORDER BY added DESC LIMIT 10"
        )).fetchall()
    # 待审瓶颈（registry：当前用户作为请求人或评审人且 pending）
    pending_reviews = 0
    try:
        async with _registry_transaction() as rdb:
            r = await (await rdb.execute(
                "SELECT COUNT(*) AS c FROM reviews WHERE status='pending' "
                "AND (requester_user_id=? OR reviewer_user_id=?)", (user_id, user_id)
            )).fetchone()
            pending_reviews = r["c"] if r else 0
    except Exception:
        pass
    status_counts = {row["status"] or "draft": row["c"] for row in sc}
    kind_counts = {row["kind"] or "file": row["c"] for row in kc}
    return {
        "total_docs": tot["c"] if tot else 0,
        "archived": tot["archived"] if tot else 0,
        "status_counts": status_counts,
        "kind_counts": kind_counts,
        "activity_14d": [{"date": a["d"], "count": a["c"]} for a in act],
        "contribution_leaders": [{"user_id": l["user_id"], "lines_added": l["added"], "edits": l["edits"]}
                                 for l in leaders],
        "pending_reviews": pending_reviews,
    }


@app.get("/api/docs/{doc_id}/analytics")
async def doc_analytics(doc_id: str, user_id: str = Depends(_require_user)):
    """文档贡献统计：各作者贡献占比。"""
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT user_id, SUM(lines_added) AS added, SUM(lines_deleted) AS deleted, COUNT(*) AS edits "
            "FROM doc_contributions WHERE doc_id=? GROUP BY user_id ORDER BY added DESC",
            (doc_id,),
        )).fetchall()
        # 总行数
        doc = await (await db.execute("SELECT content FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
    total_lines = len((_doc_atrest_decrypt(doc["content"]) if doc else "").split("\n")) if doc else 0
    contributors = []
    total_added = sum(r["added"] for r in rows)
    for r in rows:
        pct = round(r["added"] / total_added * 100, 1) if total_added else 0
        contributors.append({
            "user_id": r["user_id"], "lines_added": r["added"], "lines_deleted": r["deleted"],
            "edits": r["edits"], "share_pct": pct,
        })
    return {"total_lines": total_lines, "total_edits": sum(r["edits"] for r in rows),
            "contributors": contributors, "contributor_count": len(contributors)}


# ==================== P0: 内容 Lint（死链/死图/风格）====================
def _lint_content(content: str, doc_ids: set = None) -> list:
    """扫描文档内容质量：死链/死图/风格问题。返回 [{type, message, line}]。"""
    import re as _re
    findings = []
    if not content:
        return findings
    lines = content.split("\n")
    in_code_block = False
    headings = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # 代码块状态跟踪
        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
            else:
                in_code_block = True
                if len(stripped) == 3:
                    findings.append({"type": "style", "message": "代码块未指定语言", "line": i})
            continue
        if in_code_block:
            continue  # 代码块内不检查
        # 死链：markdown 链接到不存在的 doc_id
        for m in _re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', line):
            link = m.group(2)
            if doc_ids and link in doc_ids:
                continue
            if link.startswith(('http', '#', 'mailto:')):
                continue
            if doc_ids and not link.startswith('http') and '/' not in link:
                findings.append({"type": "dead_link", "message": f"链接目标可能不存在: {link}", "line": i})
        # 死图/alt 检查
        for m in _re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', line):
            alt = m.group(1)
            if not alt:
                findings.append({"type": "style", "message": f"图片无 alt 文本: {m.group(2)[:30]}", "line": i})
        # 标题层级
        m = _re.match(r'^(#{1,6})\s', line)
        if m:
            headings.append({"level": len(m.group(1)), "line": i})
    # 标题跳跃检测
    for j in range(1, len(headings)):
        if headings[j]["level"] > headings[j-1]["level"] + 1:
            findings.append({"type": "style", "message": f"标题层级跳跃: H{headings[j-1]['level']}→H{headings[j]['level']}（行 {headings[j]['line']}）", "line": headings[j]["line"]})
    return findings


@app.post("/api/docs/{doc_id}/lint")
async def lint_doc(doc_id: str, user_id: str = Depends(_require_user)):
    """检查文档内容质量：死链/死图/风格。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT content FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        content = _doc_atrest_decrypt(row["content"])
        # 获取所有 doc_id 用于死链检查
        all_docs = await (await db.execute("SELECT doc_id FROM documents WHERE deleted_at IS NULL AND user_id=?", (user_id,))).fetchall()
    doc_ids = {r["doc_id"] for r in all_docs}
    findings = _lint_content(content, doc_ids)
    return {"findings": findings, "count": len(findings)}


# ==================== P1: 密钥扫描（DLP）====================
import re as _re_mod

_SECRET_PATTERNS = [
    ("OpenAI API Key", _re_mod.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("AWS Access Key", _re_mod.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub Token", _re_mod.compile(r"gh[pousr]_[A-Za-z0-9]{36}")),
    ("Private Key", _re_mod.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("Slack Token", _re_mod.compile(r"xox[baprs]-[a-zA-Z0-9-]{10,}")),
    ("Google API Key", _re_mod.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Generic Secret", _re_mod.compile(r"(?:secret|password|token|passwd|pwd)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?", _re_mod.IGNORECASE)),
]


def _scan_secrets(content: str) -> list:
    """扫描内容中疑似密钥/凭证，返回 [{type, snippet, line}]。"""
    findings = []
    if not content:
        return findings
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        for name, pattern in _SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                snippet = match.group()[:40] + ("…" if len(match.group()) > 40 else "")
                findings.append({"type": name, "snippet": snippet, "line": i})
    return findings


@app.post("/api/docs/{doc_id}/scan-secrets")
async def scan_doc_secrets(doc_id: str, user_id: str = Depends(_require_user)):
    """扫描文档内容中的疑似密钥/凭证，并给出自动分级建议（P2-c）。
    命中密钥→建议提升为 confidential；未命中→维持当前分级。建议不落库，apply 见 auto-classify。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT content, classification FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?",
            (doc_id, user_id),
        )).fetchone()
    if not row:
        raise HTTPException(404, "文档不存在")
    cur_cls = row["classification"] if "classification" in row.keys() and row["classification"] else "internal"
    findings = _scan_secrets(_doc_atrest_decrypt(row["content"] or ""))
    if findings:
        await _audit(user_id, None, "dlp.secret_scan", "doc", doc_id, f"found={len(findings)}")
    suggested = "confidential" if findings else cur_cls
    return {"findings": findings, "count": len(findings),
            "current_classification": cur_cls, "suggested_classification": suggested}


@app.post("/api/docs/{doc_id}/auto-classify")
async def auto_classify_doc(doc_id: str, apply: bool = False, user_id: str = Depends(_require_user)):
    """P2-c 自动分级：扫描密钥命中→建议（默认）/应用提升为 confidential。
    apply=true 时若命中且当前非 confidential，则 UPDATE 分级为 confidential（写审计）；
    若文档正在公开分享（share_code），按 DLP 规则拒绝提升（仅返回建议 + 原因）。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT content, classification, share_code FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?",
            (doc_id, user_id),
        )).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        cur_cls = row["classification"] if "classification" in row.keys() and row["classification"] else "internal"
        share_code = row["share_code"] if "share_code" in row.keys() else None
        findings = _scan_secrets(_doc_atrest_decrypt(row["content"] or ""))
    suggested = "confidential" if findings else cur_cls
    applied = False
    reason = None
    if apply and findings and cur_cls != "confidential" and not share_code:
        async with _db_transaction(user_id) as db:
            await db.execute("UPDATE documents SET classification='confidential' WHERE doc_id=?", (doc_id,))
        await _audit(user_id, None, "dlp.auto_classify", "doc", doc_id,
                     f"{cur_cls}->confidential found={len(findings)}")
        applied = True
        cur_cls = "confidential"
    elif apply and findings and cur_cls != "confidential" and share_code:
        # DLP：正在公开分享的文档不得提升为机密（与 update_doc_meta 同款约束）
        reason = "文档正在公开分享，不能自动设为机密。请先取消分享后再应用。"
    return {"findings": findings, "count": len(findings),
            "current_classification": cur_cls, "suggested_classification": suggested,
            "applied": applied, "reason": reason}


# ==================== P2: 批量导入导出 ====================
@app.post("/api/docs/bulk-import")
async def bulk_import(docs: list = Body(...), user_id: str = Depends(_require_user)):
    """批量导入文档（JSON 数组 [{title, content, path}]）。"""
    if not await _check_endpoint_rate_limit(user_id, "/api/docs/bulk-import"):
        raise HTTPException(429, "批量导入每天限 1 次")
    if not isinstance(docs, list) or len(docs) > 500:
        raise HTTPException(400, "需为 JSON 数组（≤500 篇）")
    now = _utcnow_iso()
    created = []
    async with _db_transaction(user_id) as db:
        for d in docs[:500]:
            if not isinstance(d, dict):
                continue
            doc_id = secrets.token_urlsafe(12)
            await db.execute(
                "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, user_id) VALUES (?,?,?, ?, ?, 'file', ?, ?)",
                (doc_id, (d.get("title") or "untitled")[:200], d.get("content", ""), now, now, d.get("path", ""), user_id),
            )
            created.append(doc_id)
    await _audit(user_id, None, "doc.bulk_import", "doc", None, f"count={len(created)}")
    return {"imported": len(created), "doc_ids": created}


@app.get("/api/docs/bulk-export")
async def bulk_export(user_id: str = Depends(_require_user)):
    """导出当前用户所有文档（JSON 数组）。"""
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT doc_id, title, content, path, updated_at FROM documents WHERE deleted_at IS NULL ORDER BY updated_at DESC"
        )).fetchall()
    return {"items": [{"doc_id": r["doc_id"], "title": r["title"], "content": r["content"],
                       "path": r["path"] or "", "updated_at": r["updated_at"]} for r in rows]}


# ==================== P1-7 企业导出格式（md/html/confluence/zip）====================
def _esc_html(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _md_inline_html(md: str) -> str:
    """行内标记子集：bold/italic/code/link。先转义再注入标签，避免 XSS。"""
    out = _esc_html(md)
    # [text](url) → 链接（url 仅允许 http(s)/相对）
    def _link(m):
        txt, url = m.group(1), m.group(2)
        if re.match(r"^https?://", url) or not url.startswith(("javascript:", "data:")):
            return f'<a href="{url}">{txt}</a>'
        return txt
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", out)
    return out


def _md_to_html_body(md: str) -> str:
    """轻量 markdown→HTML（导出可读用，非完整渲染）：标题/列表/代码块/段落。
    客户端仍有完整渲染；此处仅服务端导出兜底。"""
    lines = (md or "").split("\n")
    html, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        if ln.strip().startswith("```"):
            lang = ln.strip()[3:]
            code = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(_esc_html(lines[i])); i += 1
            i += 1  # 跳过结束 ```
            html.append(f'<pre><code data-lang="{lang}">' + "\n".join(code) + "</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1)); html.append(f"<h{lvl}>{_md_inline_html(m.group(2))}</h{lvl}>"); i += 1; continue
        if re.match(r"^\s*[-*]\s+", ln):
            items = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(f"<li>{_md_inline_html(re.sub(r'^\s*[-*]\s+', '', lines[i]))}</li>"); i += 1
            html.append("<ul>" + "".join(items) + "</ul>"); continue
        if ln.strip() == "":
            i += 1; continue
        para = []
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|\s*[-*]\s+)", lines[i]):
            para.append(_md_inline_html(lines[i])); i += 1
        html.append("<p>" + " ".join(para) + "</p>")
    return "\n".join(html)


def _render_mermaid_svg(code: str) -> Optional[str]:
    """服务端 mermaid→SVG（经 mmdc CLI）。未配置/失败返回 None（调用方回退客户端运行时渲染）。"""
    import subprocess, tempfile as _tf, os as _os
    cmd = (MERMAID_MMDC_COMMAND or "").split()
    if not cmd:
        return None
    try:
        with _tf.NamedTemporaryFile("w", suffix=".mmd", delete=False, encoding="utf-8") as f:
            f.write(code); src = f.name
        out = src[:-4] + ".svg"
        try:
            r = subprocess.run(cmd + ["-i", src, "-o", out], capture_output=True, timeout=30)
            if r.returncode != 0 or not _os.path.exists(out):
                logger.warning("mermaid mmdc 渲染失败: %s", r.stderr.decode("utf-8", errors="replace")[:200])
                return None
            with open(out, "rb") as g:
                return g.read().decode("utf-8", errors="replace")
        finally:
            for p in (src, out):
                try: _os.remove(p)
                except OSError: pass
    except Exception as e:
        logger.warning("mermaid 服务端渲染异常: %s", e)
        return None


def _md_to_html_body_enhanced(md: str) -> tuple:
    """增强渲染：mermaid 代码块→内联 SVG（mmdc 可用）或客户端运行时 div；数学 $...$/$$...$$ 原样保留交 KaTeX 客户端渲染。
    返回 (body_html, has_mermaid_client, has_math)。"""
    lines = (md or "").split("\n")
    html, i, n = [], 0, len(lines)
    has_mermaid = False
    has_math = False
    while i < n:
        ln = lines[i]
        if ln.strip().startswith("```"):
            lang = ln.strip()[3:].strip().lower()
            code, i = [], i + 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            i += 1  # 跳过结束 ```
            code_str = "\n".join(code)
            if lang == "mermaid":
                svg = _render_mermaid_svg(code_str)
                if svg:
                    html.append(f'<div class="mermaid-svg">{svg}</div>')
                else:
                    has_mermaid = True
                    html.append(f'<div class="mermaid">{_esc_html(code_str)}</div>')
            else:
                html.append(f'<pre><code data-lang="{lang}">' + _esc_html(code_str) + "</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1)); html.append(f"<h{lvl}>{_md_inline_html(m.group(2))}</h{lvl}>"); i += 1; continue
        if re.match(r"^\s*[-*]\s+", ln):
            items = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(f"<li>{_md_inline_html(re.sub(r'^\s*[-*]\s+', '', lines[i]))}</li>"); i += 1
            html.append("<ul>" + "".join(items) + "</ul>"); continue
        if ln.strip() == "":
            i += 1; continue
        para = []
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|\s*[-*]\s+)", lines[i]):
            para.append(_md_inline_html(lines[i])); i += 1
        html.append("<p>" + " ".join(para) + "</p>")
    if "$$" in (md or "") or re.search(r"(?<!\\)\$", md or ""):
        has_math = True
    return "\n".join(html), has_mermaid, has_math


def _site_head_assets(has_mermaid: bool, has_math: bool) -> str:
    """注入导出/站点页 head 的图表与数学运行时。仅在需要时加载对应库。"""
    assets = ""
    if has_math:
        assets += (f'<link rel="stylesheet" href="{KATEX_CSS_CDN}">'
                   f'<script defer src="{KATEX_JS_CDN}"></script>'
                   f'<script defer src="{KATEX_AUTORENDER_CDN}"'
                   ' onload="renderMathInElement(document.body,{delimiters:[{left: \'$$\',right: \'$$\',display:true},{left: \'$\',right: \'$\',display:false}]});"></script>')
    if has_mermaid:
        assets += (f'<script src="{MERMAID_CDN}"></script>'
                   '<script>if(window.mermaid){mermaid.initialize({startOnLoad:true})}</script>')
    return assets


def _build_enhanced_page(title: str, md: str, site_title: str = "", index_link: bool = False,
                         watermark: str = "") -> str:
    """增强单页 HTML（mermaid+数学运行时）。供导出 html 与静态站点共用。

    watermark 非空时注入半透明斜向水印（出口 DLP 溯源，机密文档导出强制）。
    """
    body, has_m, has_math = _md_to_html_body_enhanced(md)
    nav = '<p class="nav"><a href="index.html">← 首页</a></p>' if index_link else ""
    head = _site_head_assets(has_m, has_math)
    wm_css = ""
    wm_div = ""
    if watermark:
        wm_css = (".md2-wm{position:fixed;inset:0;pointer-events:none;z-index:9999;"
                  "display:flex;align-items:center;justify-content:center;transform:rotate(-28deg);"
                  "font-size:5vw;color:#00000010;font-weight:800;white-space:pre-wrap;text-align:center;}")
        wm_div = f'<div class="md2-wm">{_esc_html(watermark)}</div>'
    return (
        f"<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{_esc_html(title)}</title>"
        "<style>"
        "body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:820px;margin:2em auto;padding:0 1.2em;line-height:1.6;color:#222}"
        ".nav{color:#666;font-size:.9em;margin-bottom:1em}"
        "h1{border-bottom:2px solid #eee;padding-bottom:.3em}"
        "pre{background:#f6f8fa;padding:1em;overflow:auto;border-radius:6px}"
        "code{background:#f0f0f0;padding:.1em .3em;border-radius:3px;font-size:.92em}"
        "pre code{background:none;padding:0}"
        "a{color:#0969da}img{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.4em .7em}"
        ".mermaid-svg svg{max-width:100%}"
        f"{wm_css}"
        "</style>"
        f"{head}</head><body>{nav}<h1>{_esc_html(title)}</h1>{body}{wm_div}</body></html>"
    )


def _safe_filename(title: str, doc_id: str) -> str:
    name = re.sub(r"[^\w一-鿿.\- ]", "_", (title or doc_id)[:60]).strip() or doc_id
    return name


def _content_disposition(base: str, ext: str) -> str:
    """构造 Content-Disposition：ASCII filename= + UTF-8 filename*=（RFC 5987，兼容中文）。"""
    from urllib.parse import quote
    ascii_base = re.sub(r"[^\x20-\x7e]", "_", base)[:60].strip() or "doc"
    return f"attachment; filename=\"{ascii_base}{ext}\"; filename*=UTF-8''{quote(base + ext)}"


async def _doc_egress_guard(row, user_id: str, action: str = "export"):
    """出口 DLP：机密文档防泄露守卫。

    机密（confidential）文档仅属主/管理员可导出/打包/建站；其余调用方 403。
    属主/管理员导出时由调用方注入水印（见 export_doc / _build_enhanced_page）。
    """
    if not DLP_BLOCK_EXPORT_CONFIDENTIAL or not row:
        return None
    keys = row.keys()
    cls = row["classification"] if "classification" in keys else None
    if cls != "confidential":
        return None
    owner = row["user_id"] if "user_id" in keys else None
    if owner == user_id:
        return None
    if await _is_admin(user_id):
        return None
    raise HTTPException(403, f"机密文档禁止{action}（DLP）")


@app.get("/api/docs/{doc_id}/export")
async def export_doc(doc_id: str, fmt: str = "md", user_id: str = Depends(_require_user)):
    """单文档导出：md / html / confluence（Confluence storage-format XHTML）。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT title, content, classification FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,)
        )).fetchone()
    if not row:
        raise HTTPException(404, "文档不存在")
    await _doc_egress_guard(row, user_id, "导出")
    plain = _doc_atrest_decrypt(row["content"]) if row["content"] else ""
    title = row["title"] or doc_id
    fname = _safe_filename(title, doc_id)
    if fmt == "md":
        return Response(plain.encode("utf-8"), media_type="text/markdown",
                        headers={"Content-Disposition": _content_disposition(fname, ".md")})
    if fmt == "confluence":
        body = _md_to_html_body(plain)
        # Confluence storage format：XHTML，包裹在 <ac:structured-macro> 外的根 div
        xml = (f'<html><head><title>{_esc_html(title)}</title></head>'
               f'<body><h1>{_esc_html(title)}</h1>{body}</body></html>')
        return Response(xml.encode("utf-8"), media_type="application/xhtml+xml",
                        headers={"Content-Disposition": _content_disposition(fname, ".html")})
    # html（默认可读 HTML，含 mermaid/数学运行时）
    wm = ""
    if DLP_WATERMARK and (row["classification"] == "confidential"):
        wm = f"机密 · {user_id} · {_utcnow_iso()}"
    page = _build_enhanced_page(title, plain, watermark=wm)
    await _audit(user_id, None, "doc.export", "doc", doc_id, f"fmt={fmt}")
    return Response(page.encode("utf-8"), media_type="text/html",
                    headers={"Content-Disposition": _content_disposition(fname, ".html")})


@app.get("/api/docs/bulk-export.zip")
async def bulk_export_zip(user_id: str = Depends(_require_user)):
    """批量导出全部文档为 zip（每个 .md + manifest.json）。stdlib zipfile，无外部依赖。"""
    import io, zipfile, json as _json
    async with _db_transaction(user_id) as db:
        # PG 共享库模式下按 user_id 收敛，防跨用户泄露（SQLite per-user 本就隔离）
        rows = await (await db.execute(
            "SELECT doc_id, title, content, path, updated_at, user_id, classification "
            "FROM documents WHERE deleted_at IS NULL AND user_id=? ORDER BY updated_at DESC",
            (user_id,)
        )).fetchall()
    buf = io.BytesIO()
    used = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = []
        for r in rows:
            # 出口 DLP：机密文档不入批量包（防一次性打包泄露）
            if DLP_BLOCK_EXPORT_CONFIDENTIAL and r["classification"] == "confidential":
                continue
            plain = _doc_atrest_decrypt(r["content"]) if r["content"] else ""
            base = _safe_filename(r["title"], r["doc_id"])
            n, fname = 1, f"{base}.md"
            while fname in used:
                n += 1; fname = f"{base} ({n}).md"
            used.add(fname)
            zf.writestr(fname, plain)
            manifest.append({"file": fname, "doc_id": r["doc_id"], "title": r["title"],
                             "path": r["path"] or "", "updated_at": r["updated_at"]})
        zf.writestr("manifest.json", _json.dumps({"exported_at": _utcnow_iso(), "count": len(manifest), "items": manifest},
                                                ensure_ascii=False, indent=2))
    await _audit(user_id, None, "doc.bulk_export", "doc", None, f"count={len(rows)} fmt=zip")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": _content_disposition("docs-export", ".zip")})


# ==================== P1 静态站点构建（docs-as-site）====================
def _site_slug(title: str, doc_id: str) -> str:
    """标题→URL 安全文件名（保留中文）；空则回退 doc_id。"""
    s = re.sub(r"[^\w一-鿿.\-]", "-", (title or "").strip())[:80].strip("-") or doc_id
    return s


def _site_rewrite_links(body_html: str, slug_map: dict) -> str:
    """把站内引用重写为相对页链接：
    - [[doc_id]] / [[doc_id|alias]] → <a href="{slug}.html">alias/doc_id</a>（命中集合内页；未命中保留纯文本）
    - [text](doc:doc_id) → <a href="{slug}.html">text</a>"""
    def _wiki(m):
        ref = m.group(1)
        alias = m.group(2) or ref
        slug = slug_map.get(ref)
        if slug:
            return f'<a href="{slug}.html">{_esc_html(alias)}</a>'
        return _esc_html(alias)
    body_html = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", _wiki, body_html)
    # 原始 markdown 形式 [text](doc:id)（若未被行内渲染消费）
    def _doclink(m):
        txt, ref = m.group(1), m.group(2)
        slug = slug_map.get(ref)
        if slug:
            return f'<a href="{slug}.html">{txt}</a>'
        return txt
    body_html = re.sub(r"\[([^\]]+)\]\(doc:([^)]+)\)", _doclink, body_html)
    # 已被 _md_inline_html 渲染为 <a href="doc:id"> 的形式
    def _dochref(m):
        ref = m.group(1)
        slug = slug_map.get(ref)
        if slug:
            return f'href="{slug}.html"'
        return m.group(0)
    body_html = re.sub(r'href="doc:([^"]+)"', _dochref, body_html)
    return body_html


def _site_page_html(title: str, body_html: str, site_title: str, index_link: bool = True) -> str:
    nav = '<p class="nav"><a href="index.html">← 首页</a></p>' if index_link else ""
    return (
        f"<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{_esc_html(title)}</title>"
        "<style>"
        "body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:820px;margin:2em auto;padding:0 1.2em;line-height:1.6;color:#222}"
        ".nav{color:#666;font-size:.9em;margin-bottom:1em}"
        "h1{border-bottom:2px solid #eee;padding-bottom:.3em}"
        "pre{background:#f6f8fa;padding:1em;overflow:auto;border-radius:6px}"
        "code{background:#f0f0f0;padding:.1em .3em;border-radius:3px;font-size:.92em}"
        "pre code{background:none;padding:0}"
        "a{color:#0969da}img{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.4em .7em}"
        "</style></head><body>"
        f"{nav}<h1>{_esc_html(title)}</h1>{body_html}</body></html>"
    )


def _build_site_zip(pages: list, site_title: str) -> bytes:
    """pages: [{doc_id,title,content}] → 静态站点 zip（各 .html + index.html + manifest.json）。"""
    import io, zipfile, json as _json
    # 去重 slug
    used, slug_map, items = {}, {}, []
    for p in pages:
        base = _site_slug(p["title"], p["doc_id"])
        n, slug = 1, base
        while slug in used:
            n += 1; slug = f"{base}-{n}"
        used[slug] = True
        slug_map[p["doc_id"]] = slug
        items.append({**p, "slug": slug})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = []
        for it in items:
            body, has_m, has_math = _md_to_html_body_enhanced(it["content"] or "")
            body = _site_rewrite_links(body, slug_map)
            # 复用增强页（带 mermaid/数学运行时），首行注入返回首页
            html = _build_enhanced_page(it["title"], "")  # 占位以拿 head/style 壳
            # 把 body 替换进壳（_build_enhanced_page 已渲染 body；此处改为带链接重写的 body）
            nav = '<p class="nav"><a href="index.html">← 首页</a></p>'
            head = _site_head_assets(has_m, has_math)
            html = (
                f"<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
                f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                f"<title>{_esc_html(it['title'])}</title>"
                "<style>"
                "body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:820px;margin:2em auto;padding:0 1.2em;line-height:1.6;color:#222}"
                ".nav{color:#666;font-size:.9em;margin-bottom:1em}"
                "h1{border-bottom:2px solid #eee;padding-bottom:.3em}"
                "pre{background:#f6f8fa;padding:1em;overflow:auto;border-radius:6px}"
                "code{background:#f0f0f0;padding:.1em .3em;border-radius:3px;font-size:.92em}"
                "pre code{background:none;padding:0}"
                "a{color:#0969da}img{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.4em .7em}"
                ".mermaid-svg svg{max-width:100%}"
                "</style>"
                f"{head}</head><body>{nav}<h1>{_esc_html(it['title'])}</h1>{body}</body></html>"
            )
            zf.writestr(f"{it['slug']}.html", html)
            manifest.append({"file": f"{it['slug']}.html", "doc_id": it["doc_id"], "title": it["title"]})
        # index.html
        rows = "\n".join(f'<li><a href="{_esc_html(it["slug"])}.html">{_esc_html(it["title"])}</a></li>'
                        for it in items)
        idx_body = f"<ul>{rows}</ul>" if items else "<p>（无页面）</p>"
        idx = (f"<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
               f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
               f"<title>{_esc_html(site_title)}</title>"
               "<style>body{font-family:system-ui,sans-serif;max-width:820px;margin:2em auto;padding:0 1.2em}"
               "h1{border-bottom:2px solid #eee;padding-bottom:.3em}a{color:#0969da}ul{list-style:square}</style>"
               f"</head><body><h1>{_esc_html(site_title)}</h1>{idx_body}</body></html>")
        zf.writestr("index.html", idx)
        zf.writestr("manifest.json", _json.dumps({"site_title": site_title, "built_at": _utcnow_iso(),
                                                  "page_count": len(items), "pages": manifest},
                                                 ensure_ascii=False, indent=2))
    return buf.getvalue()


class SiteBuildRequest(BaseModel):
    doc_ids: Optional[List[str]] = None  # 空则取全部未删除文档
    title: Optional[str] = None          # 站点标题


@app.post("/api/docs/site/build")
async def build_personal_site(req: SiteBuildRequest, user_id: str = Depends(_require_user)):
    """构建个人静态站点：把选定（或全部）文档渲染为可托管静态 HTML 站点 zip。"""
    async with _db_transaction(user_id) as db:
        if req.doc_ids:
            ph = ",".join("?" * len(req.doc_ids))
            rows = await (await db.execute(
                f"SELECT doc_id, title, content, classification FROM documents WHERE doc_id IN ({ph}) "
                f"AND deleted_at IS NULL AND user_id=?", (*req.doc_ids, user_id)
            )).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT doc_id, title, content, classification FROM documents WHERE deleted_at IS NULL AND user_id=? "
                "ORDER BY updated_at DESC", (user_id,)
            )).fetchall()
    if not rows:
        raise HTTPException(404, "无可构建的文档")
    # 出口 DLP：机密文档不入公开站点（防一次性打包泄露）
    if DLP_BLOCK_EXPORT_CONFIDENTIAL:
        rows = [r for r in rows if r["classification"] != "confidential"]
    if not rows:
        raise HTTPException(403, "全部文档为机密，禁止站点构建（DLP）")
    pages = [{"doc_id": r["doc_id"], "title": r["title"] or r["doc_id"],
              "content": _doc_atrest_decrypt(r["content"]) if r["content"] else ""} for r in rows]
    zip_bytes = _build_site_zip(pages, req.title or "我的文档站点")
    await _audit(user_id, None, "site.build", "doc", None, f"count={len(pages)} scope=personal")
    return Response(zip_bytes, media_type="application/zip",
                    headers={"Content-Disposition": _content_disposition(
                        req.title or "site", ".zip")})


@app.post("/api/teams/{tid}/site/build")
async def build_team_site(tid: str, req: SiteBuildRequest, user_id: str = Depends(_require_user)):
    """构建团队静态站点：基于团队成员可读的文档渲染为静态 HTML 站点 zip。"""
    # 鉴权：成员身份 + doc.read 权限（per-doc ACL 旁路/拒绝）
    await _require_team_permission(tid, user_id, "doc.read")
    async with _team_db_transaction(tid) as db:
        if req.doc_ids:
            ph = ",".join("?" * len(req.doc_ids))
            rows = await (await db.execute(
                f"SELECT doc_id, title, content, user_id FROM documents WHERE doc_id IN ({ph}) "
                f"AND deleted_at IS NULL", (*req.doc_ids,)
            )).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT doc_id, title, content, user_id FROM documents "
                "WHERE deleted_at IS NULL ORDER BY updated_at DESC"
            )).fetchall()
    # 逐篇 ACL 校验（reader 视角）：拒绝者剔除
    pages = []
    for r in rows:
        chk = await _team_doc_acl_check(tid, r["doc_id"], user_id, "read")
        if chk == "deny":
            continue
        if chk is None:
            # 无显式 ACL：成员默认可读（ACL 旁路已含 owner/admin；此处普通成员也放行）
            pass
        pages.append({"doc_id": r["doc_id"], "title": r["title"] or r["doc_id"],
                      "content": _doc_atrest_decrypt(r["content"]) if r["content"] else ""})
    if not pages:
        raise HTTPException(404, "无可构建的团队文档（或无读取权限）")
    zip_bytes = _build_site_zip(pages, req.title or "团队文档站点")
    await _audit(user_id, tid, "site.build", "team_doc", None, f"count={len(pages)} scope=team")
    return Response(zip_bytes, media_type="application/zip",
                    headers={"Content-Disposition": _content_disposition(
                        req.title or "team-site", ".zip")})


# ==================== 配额与用量计量 ====================
@app.get("/api/usage")
async def get_personal_usage(user_id: str = Depends(_require_user)):
    """当前用户用量与配额：文档数/存储/AI今日/团队数。"""
    u = await _user_doc_usage(user_id)
    teams = await _user_team_count(user_id)
    ai_today = await _ai_usage_count(user_id, None)
    return {
        "docs": {"count": u["count"], "max": USER_MAX_DOCS or None},
        "storage": {"bytes": u["storage_bytes"], "max": USER_MAX_STORAGE_BYTES or None},
        "teams": {"count": teams, "max": USER_MAX_TEAMS or None},
        "ai_today": {"count": ai_today, "max": AI_USER_DAILY_QUOTA or None},
    }


@app.get("/api/teams/{tid}/usage")
async def get_team_usage(tid: str, user_id: str = Depends(_require_user)):
    """团队用量与配额（成员可读）。"""
    role = await _team_member_role(tid, user_id)
    if not role:
        raise HTTPException(403, "非团队成员")
    u = await _team_doc_usage(tid)
    ai_today = await _ai_usage_count(user_id, tid)
    return {
        "team_id": tid,
        "docs": {"count": u["count"], "max": TEAM_MAX_DOCS or None},
        "storage": {"bytes": u["storage_bytes"], "max": TEAM_MAX_STORAGE_BYTES or None},
        "members": {"count": u["member_count"], "max": TEAM_MAX_MEMBERS or None},
        "ai_today": {"count": ai_today, "max": AI_TEAM_DAILY_QUOTA or None},
    }


@app.get("/api/admin/usage")
async def admin_usage_overview(user_id: str = Depends(_require_user)):
    """管理员全局用量概览：总用户/总团队/总文档存储估算。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        users = await (await db.execute("SELECT COUNT(*) AS c FROM users")).fetchone()
        teams = await (await db.execute("SELECT COUNT(*) AS c FROM teams")).fetchone()
        tmembers = await (await db.execute("SELECT COUNT(*) AS c FROM team_members")).fetchone()
    return {
        "users": int(users["c"] or 0),
        "teams": int(teams["c"] or 0),
        "team_members": int(tmembers["c"] or 0),
        "quotas": {"user_max_docs": USER_MAX_DOCS or None, "team_max_docs": TEAM_MAX_DOCS or None,
                   "user_max_storage_bytes": USER_MAX_STORAGE_BYTES or None,
                   "team_max_storage_bytes": TEAM_MAX_STORAGE_BYTES or None,
                   "user_max_teams": USER_MAX_TEAMS or None},
    }


# ==================== 法务保留（legal hold）端点 ====================
class LegalHoldRequest(BaseModel):
    scope: str            # global | user | team
    scope_id: Optional[str] = ""  # global 留空
    reason: str


@app.post("/api/admin/legal-holds", status_code=201)
async def create_legal_hold(req: LegalHoldRequest, user_id: str = Depends(_require_user)):
    """建立法务保留（仅管理员）。建立后受影响文档不可删除、版本不可清理，直至释放。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    if req.scope not in ("global", "user", "team"):
        raise HTTPException(400, "scope 需为 global/user/team")
    if req.scope in ("user", "team") and not req.scope_id:
        raise HTTPException(400, f"{req.scope} 范围需指定 scope_id")
    hid = secrets.token_urlsafe(10)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO legal_holds (id, scope, scope_id, reason, held_by, created_at) VALUES (?,?,?,?,?,?)",
            (hid, req.scope, req.scope_id or "", req.reason, user_id, now),
        )
    await _audit(user_id, None, "legal_hold.create", "legal_hold", hid, f"scope={req.scope} reason={req.reason}")
    return {"id": hid, "scope": req.scope, "scope_id": req.scope_id or "", "reason": req.reason, "held_by": user_id, "created_at": now}


@app.get("/api/admin/legal-holds")
async def list_legal_holds(active_only: bool = True, user_id: str = Depends(_require_user)):
    """列法务保留（仅管理员）。active_only=1 仅未释放。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        if active_only:
            rows = await (await db.execute(
                "SELECT id, scope, scope_id, reason, held_by, created_at, released_at, released_by "
                "FROM legal_holds WHERE released_at IS NULL ORDER BY created_at DESC"
            )).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT id, scope, scope_id, reason, held_by, created_at, released_at, released_by "
                "FROM legal_holds ORDER BY created_at DESC"
            )).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.post("/api/admin/legal-holds/{hid}/release")
async def release_legal_hold(hid: str, user_id: str = Depends(_require_user)):
    """释放法务保留（仅管理员）。释放后受影响文档可正常删除。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        r = await (await db.execute("SELECT id, released_at FROM legal_holds WHERE id=?", (hid,))).fetchone()
        if not r:
            raise HTTPException(404, "法务保留不存在")
        if r["released_at"]:
            raise HTTPException(409, "该法务保留已释放")
        await db.execute("UPDATE legal_holds SET released_at=?, released_by=? WHERE id=?", (now, user_id, hid))
    await _audit(user_id, None, "legal_hold.release", "legal_hold", hid, "")
    return {"ok": True, "id": hid, "released_at": now}


@app.get("/api/docs/{doc_id}/legal-hold")
async def doc_legal_hold_status(doc_id: str, user_id: str = Depends(_require_user)):
    """查询某个人文档是否处于法务保留（UI 提示用）。"""
    reason = await _doc_legal_hold(user_id=user_id)
    return {"held": reason is not None, "reason": reason}


# ==================== eDiscovery 合规导出 ====================
class EdiscoveryRequest(BaseModel):
    scope: str                       # user | team | global
    scope_id: str = ""               # user/team 范围必填
    include_deleted: bool = True
    include_versions: bool = True
    include_audit: bool = True


@app.post("/api/admin/ediscovery/export")
async def ediscovery_export(req: EdiscoveryRequest, user_id: str = Depends(_require_user)):
    """合规导出（仅管理员）：打包指定范围全部文档（含软删）、版本快照、审计日志、ACL 为 zip。
    用于诉讼证据保全 / 法务取证。导出行为本身写入审计。"""
    import io, zipfile, json as _json
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    if req.scope not in ("user", "team", "global"):
        raise HTTPException(400, "scope 需为 user/team/global")
    if req.scope in ("user", "team") and not req.scope_id:
        raise HTTPException(400, f"{req.scope} 范围需指定 scope_id")

    docs, versions, audit_rows, acl_rows, meta = [], [], [], [], {}
    deleted_clause = "" if req.include_deleted else "AND deleted_at IS NULL"

    if req.scope == "user":
        async with _db_transaction(req.scope_id) as db:
            docs = [dict(r) for r in await (await db.execute(
                f"SELECT doc_id, title, content, created_at, updated_at, version, deleted_at, "
                f"user_id, etag, status, archived FROM documents WHERE user_id=? {deleted_clause}",
                (req.scope_id,),
            )).fetchall()]
            if req.include_versions:
                versions = [dict(r) for r in await (await db.execute(
                    "SELECT doc_id, version, title, content, created_at, created_by FROM doc_versions "
                    "WHERE doc_id IN (SELECT doc_id FROM documents WHERE user_id=?)",
                    (req.scope_id,),
                )).fetchall()]
        if req.include_audit:
            async with _registry_transaction() as db:
                audit_rows = [dict(r) for r in await (await db.execute(
                    "SELECT id, ts, user_id, team_id, action, target_type, target_id, detail FROM audit_log "
                    "WHERE user_id=? ORDER BY id", (req.scope_id,)
                )).fetchall()]
        meta["scope"] = "user"; meta["scope_id"] = req.scope_id
    elif req.scope == "team":
        async with _team_db_transaction(req.scope_id) as db:
            docs = [dict(r) for r in await (await db.execute(
                f"SELECT doc_id, title, content, created_at, updated_at, version, deleted_at, "
                f"user_id, etag, status FROM documents WHERE 1=1 {deleted_clause}"
            )).fetchall()]
            if req.include_versions:
                versions = [dict(r) for r in await (await db.execute(
                    "SELECT doc_id, version, title, content, created_at, created_by FROM doc_versions"
                )).fetchall()]
            acl_rows = [dict(r) for r in await (await db.execute(
                "SELECT doc_id, grantee_user_id, permission, granted_by, created_at FROM team_doc_acl"
            )).fetchall()]
        if req.include_audit:
            async with _registry_transaction() as db:
                audit_rows = [dict(r) for r in await (await db.execute(
                    "SELECT id, ts, user_id, team_id, action, target_type, target_id, detail FROM audit_log "
                    "WHERE team_id=? ORDER BY id", (req.scope_id,)
                )).fetchall()]
        meta["scope"] = "team"; meta["scope_id"] = req.scope_id
    else:  # global
        if req.include_audit:
            async with _registry_transaction() as db:
                audit_rows = [dict(r) for r in await (await db.execute(
                    "SELECT id, ts, user_id, team_id, action, target_type, target_id, detail FROM audit_log ORDER BY id"
                )).fetchall()]
        meta["scope"] = "global"

    # 解密正文（at-rest）+ 构建存档
    for d in docs:
        d["content_plain"] = _doc_atrest_decrypt(d["content"]) if d.get("content") else ""
        d.pop("content", None)  # 不存密文，只存明文（取证用）
    for v in versions:
        v["content_plain"] = _doc_atrest_decrypt(v["content"]) if v.get("content") else ""
        v.pop("content", None)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {**meta, "exported_at": _utcnow_iso(), "exported_by": user_id,
                    "doc_count": len(docs), "version_count": len(versions),
                    "audit_count": len(audit_rows), "acl_count": len(acl_rows),
                    "include_deleted": req.include_deleted}
        zf.writestr("manifest.json", _json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
        zf.writestr("documents.json", _json.dumps(docs, ensure_ascii=False, indent=2, default=str))
        if req.include_versions:
            zf.writestr("versions.json", _json.dumps(versions, ensure_ascii=False, indent=2, default=str))
        if req.include_audit:
            zf.writestr("audit.json", _json.dumps(audit_rows, ensure_ascii=False, indent=2, default=str))
        if acl_rows:
            zf.writestr("acl.json", _json.dumps(acl_rows, ensure_ascii=False, indent=2, default=str))
        # 各文档明文另存 .md（便于法务直读）
        used = set()
        for d in docs:
            base = _safe_filename(d.get("title") or d["doc_id"], d["doc_id"])
            n, fname = 1, f"{base}.md"
            while fname in used:
                n += 1; fname = f"{base} ({n}).md"
            used.add(fname)
            zf.writestr(f"docs/{fname}", d.get("content_plain", ""))
    await _audit(user_id, None, "ediscovery.export", "ediscovery", req.scope_id or req.scope,
                 f"scope={req.scope} docs={len(docs)}")
    label = f"ediscovery-{req.scope}-{req.scope_id or 'global'}"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": _content_disposition(label, ".zip")})


# ==================== 数据驻留分区（admin）====================
class ResidencyAssignRequest(BaseModel):
    scope: str        # user | team
    scope_id: str
    region: str       # 目标 region（须在 RESIDENCY_REGIONS 配置中，或为 "" 解除）


@app.get("/api/admin/residency")
async def residency_overview(user_id: str = Depends(_require_user)):
    """数据驻留概览（仅管理员）：region 配置 + 各 region 用户/团队计数 + 未分区计数。"""
    if not await _is_admin(user_id):
        raise HTTPException(403, "仅管理员")
    async with _registry_transaction() as db:
        u_rows = await (await db.execute(
            "SELECT residency_region, COUNT(*) AS c FROM users GROUP BY residency_region"
        )).fetchall()
        t_rows = await (await db.execute(
            "SELECT residency_region, COUNT(*) AS c FROM teams GROUP BY residency_region"
        )).fetchall()
    users_by_region = {r["residency_region"] or "(default)": r["c"] for r in u_rows}
    teams_by_region = {r["residency_region"] or "(default)": r["c"] for r in t_rows}
    regions = {name: {"dir": cfg.get("dir") if isinstance(cfg, dict) else None}
               for name, cfg in (RESIDENCY_REGIONS or {}).items()}
    return {"enabled": bool(DATA_RESIDENCY_ENABLED), "default_region": RESIDENCY_DEFAULT_REGION or None,
            "regions": regions, "users_by_region": users_by_region,
            "teams_by_region": teams_by_region}


