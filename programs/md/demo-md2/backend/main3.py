# ==================== 团队（teams / 成员 / 角色）====================
class TeamCreateRequest(BaseModel):
    name: str
    slug: Optional[str] = None


class MemberAddRequest(BaseModel):
    username: str  # 按用户名邀请
    role: str = "member"  # viewer/member/admin（owner 仅创建者）


@app.post("/api/teams", status_code=201)
async def create_team(req: TeamCreateRequest, user_id: str = Depends(_require_user)):
    """创建团队，创建者为 owner。"""
    name = (req.name or "").strip()
    if not name or len(name) > 64:
        raise HTTPException(400, "团队名必填且 ≤64 字符")
    qerr = await _team_quota_check_create(user_id)
    if qerr:
        raise HTTPException(429, qerr)
    tid = "team-" + secrets.token_urlsafe(10)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        await db.execute(
            "INSERT INTO teams (team_id, name, slug, owner_user_id, created_at) VALUES (?,?,?,?,?)",
            (tid, name, (req.slug or "").strip() or None, user_id, now),
        )
        await db.execute(
            "INSERT INTO team_members (team_id, user_id, role, created_at) VALUES (?,?,?,?)",
            (tid, user_id, "owner", now),
        )
        await _seed_default_team_roles(tid, db)
    await _audit(user_id, tid, "team.create", "team", tid, name)
    logger.info("创建团队 id=%s name=%s owner=%s", tid, name, user_id)
    return {"team_id": tid, "name": name, "role": "owner", "created_at": now}


@app.get("/api/teams")
async def list_my_teams(user_id: str = Depends(_require_user)):
    """列出当前用户加入的所有团队 + 角色。"""
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT t.team_id, t.name, t.slug, t.owner_user_id, t.created_at, m.role "
            "FROM team_members m JOIN teams t ON t.team_id = m.team_id "
            "WHERE m.user_id=? ORDER BY t.created_at DESC",
            (user_id,),
        )).fetchall()
    return {"items": [
        {"team_id": r["team_id"], "name": r["name"], "slug": r["slug"],
         "owner_user_id": r["owner_user_id"], "role": r["role"], "created_at": r["created_at"]}
        for r in rows
    ]}


@app.get("/api/teams/{tid}")
async def get_team(tid: str, user_id: str = Depends(_require_user)):
    """团队详情 + 成员列表（成员可见）。"""
    await _require_team_role(tid, user_id, "viewer")
    async with _registry_transaction() as db:
        t = await (await db.execute("SELECT * FROM teams WHERE team_id=?", (tid,))).fetchone()
        members = await (await db.execute(
            "SELECT m.user_id, m.role, m.created_at, u.username FROM team_members m "
            "JOIN users u ON u.user_id = m.user_id WHERE m.team_id=? ORDER BY m.created_at",
            (tid,),
        )).fetchall()
    return {
        "team_id": tid, "name": t["name"], "slug": t["slug"],
        "owner_user_id": t["owner_user_id"], "created_at": t["created_at"],
        "members": [{"user_id": m["user_id"], "username": m["username"], "role": m["role"], "created_at": m["created_at"]} for m in members],
    }


@app.post("/api/teams/{tid}/members", status_code=201)
async def add_team_member(tid: str, req: MemberAddRequest, user_id: str = Depends(_require_user)):
    """邀请成员（按用户名）。需 member.invite 权限（默认 admin/owner 拥有）。role 可为内建或自定义角色。"""
    await _require_team_permission(tid, user_id, "member.invite")
    role = (req.role or "member").strip()
    async with _registry_transaction() as db:
        # 内建角色（viewer/commenter/reviewer/member/admin/owner）始终合法：
        # 兼容在 _seed_default_team_roles 接入前创建的旧团队（其 team_roles 无内建占位行），
        # 与 _team_role_permissions 的默认矩阵回退保持一致。
        valid_roles = {r["role"] for r in await (await db.execute(
            "SELECT role FROM team_roles WHERE team_id=?", (tid,)
        )).fetchall()} | set(_DEFAULT_ROLE_MATRIX.keys())
        if role == "owner":
            raise HTTPException(400, "不能直接指派 owner")
        if role not in valid_roles:
            raise HTTPException(400, f"角色不存在：{role}")
        target = await (await db.execute("SELECT user_id FROM users WHERE username=?", (req.username.strip(),))).fetchone()
        if not target:
            raise HTTPException(404, "用户不存在")
        if target["user_id"] == user_id:
            raise HTTPException(400, "不能邀请自己")
        existing = await (await db.execute("SELECT 1 FROM team_members WHERE team_id=? AND user_id=?", (tid, target["user_id"]))).fetchone()
        if existing:
            raise HTTPException(409, "该用户已是团队成员")
        await db.execute(
            "INSERT INTO team_members (team_id, user_id, role, created_at) VALUES (?,?,?,?)",
            (tid, target["user_id"], role, _utcnow_iso()),
        )
    await _audit(user_id, tid, "team.member.add", "user", target["user_id"], f"role={role}")
    return {"user_id": target["user_id"], "username": req.username.strip(), "role": role}


@app.put("/api/teams/{tid}/members/{uid}")
async def update_member_role(tid: str, uid: str, role: str, user_id: str = Depends(_require_user)):
    """修改成员角色。需 member.remove 权限（默认 admin/owner）。role 可为内建或自定义角色。"""
    await _require_team_permission(tid, user_id, "member.remove")
    if role == "owner":
        raise HTTPException(400, "不能直接指派 owner")
    async with _registry_transaction() as db:
        # 同 add_team_member：内建角色始终合法，兼容旧团队未播种 team_roles 的情况。
        valid_roles = {r["role"] for r in await (await db.execute(
            "SELECT role FROM team_roles WHERE team_id=?", (tid,)
        )).fetchall()} | set(_DEFAULT_ROLE_MATRIX.keys())
        if role not in valid_roles:
            raise HTTPException(400, f"角色不存在：{role}")
        cur = await (await db.execute("SELECT role FROM team_members WHERE team_id=? AND user_id=?", (tid, uid))).fetchone()
        if not cur:
            raise HTTPException(404, "成员不存在")
        if cur["role"] == "owner":
            raise HTTPException(400, "不能直接修改 owner 角色")
        await db.execute("UPDATE team_members SET role=? WHERE team_id=? AND user_id=?", (role, tid, uid))
    await _audit(user_id, tid, "team.member.role", "user", uid, f"{cur['role']}->{role}")
    return {"user_id": uid, "role": role}


# ---------- 自定义角色与权限矩阵 ----------
class RoleMatrixRequest(BaseModel):
    role: str  # 角色名（内建 viewer/member/admin/owner 或自定义）
    permissions: list[str] = []  # 权限 key 子集，缺省为空


@app.get("/api/teams/{tid}/roles")
async def list_team_roles(tid: str, user_id: str = Depends(_require_user)):
    """列出团队全部角色及其权限矩阵（成员可见）。"""
    await _require_team_role(tid, user_id, "viewer")
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT role, permissions_json, is_default, created_at FROM team_roles WHERE team_id=? ORDER BY is_default DESC, role",
            (tid,),
        )).fetchall()
    items = []
    for r in rows:
        try:
            perms = json.loads(r["permissions_json"])
        except Exception:
            perms = []
        items.append({"role": r["role"], "permissions": perms,
                      "is_default": bool(r["is_default"]), "created_at": r["created_at"]})
    return {"team_id": tid, "items": items, "available_permissions": sorted(_TEAM_PERMISSIONS)}


@app.post("/api/teams/{tid}/roles", status_code=201)
async def create_team_role(tid: str, req: RoleMatrixRequest, user_id: str = Depends(_require_user)):
    """新建自定义角色（仅 owner）。角色名不得与内建角色冲突，≤32 字符。"""
    await _require_team_permission(tid, user_id, "role.manage")
    role = (req.role or "").strip()
    if not role or len(role) > 32 or not role.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "角色名仅允许字母数字/下划线/短横线，≤32 字符")
    if role in _DEFAULT_ROLE_MATRIX:
        raise HTTPException(400, "不能创建与内建角色同名的角色")
    perms = sorted(_normalize_perms(req.permissions))
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        existing = await (await db.execute("SELECT 1 FROM team_roles WHERE team_id=? AND role=?", (tid, role))).fetchone()
        if existing:
            raise HTTPException(409, "角色已存在")
        await db.execute(
            "INSERT INTO team_roles (team_id, role, permissions_json, is_default, created_at) VALUES (?,?,?,0,?)",
            (tid, role, json.dumps(perms), now),
        )
    await _audit(user_id, tid, "team.role.create", "role", role, f"perms={','.join(perms)}")
    return {"role": role, "permissions": perms, "is_default": False, "created_at": now}


@app.put("/api/teams/{tid}/roles/{role}")
async def update_team_role(tid: str, role: str, req: RoleMatrixRequest, user_id: str = Depends(_require_user)):
    """更新角色权限矩阵（仅 owner）。可调整内建角色的矩阵（owner 除外）。"""
    await _require_team_permission(tid, user_id, "role.manage")
    if role == "owner":
        raise HTTPException(400, "不能修改 owner 的权限矩阵")
    perms = sorted(_normalize_perms(req.permissions))
    async with _registry_transaction() as db:
        cur = await (await db.execute("SELECT 1 FROM team_roles WHERE team_id=? AND role=?", (tid, role))).fetchone()
        if not cur:
            raise HTTPException(404, "角色不存在")
        await db.execute(
            "UPDATE team_roles SET permissions_json=? WHERE team_id=? AND role=?",
            (json.dumps(perms), tid, role),
        )
    await _audit(user_id, tid, "team.role.update", "role", role, f"perms={','.join(perms)}")
    return {"role": role, "permissions": perms}


@app.delete("/api/teams/{tid}/roles/{role}")
async def delete_team_role(tid: str, role: str, user_id: str = Depends(_require_user)):
    """删除自定义角色（仅 owner）。内建角色不可删；若仍有成员持该角色则拒绝。"""
    await _require_team_permission(tid, user_id, "role.manage")
    if role in _DEFAULT_ROLE_MATRIX:
        raise HTTPException(400, "内建角色不可删除")
    async with _registry_transaction() as db:
        in_use = await (await db.execute(
            "SELECT 1 FROM team_members WHERE team_id=? AND role=? LIMIT 1", (tid, role)
        )).fetchone()
        if in_use:
            raise HTTPException(409, "仍有成员持有该角色，无法删除")
        cur = await db.execute("DELETE FROM team_roles WHERE team_id=? AND role=?", (tid, role))
        if cur.rowcount == 0:
            raise HTTPException(404, "角色不存在")
    await _audit(user_id, tid, "team.role.delete", "role", role, None)
    return {"deleted": role}


@app.delete("/api/teams/{tid}/members/{uid}")
async def remove_member(tid: str, uid: str, user_id: str = Depends(_require_user)):
    """移除成员。owner 不可被移除（需先转让 owner）。"""
    caller = await _require_team_role(tid, user_id, "admin")
    async with _registry_transaction() as db:
        cur = await (await db.execute("SELECT role FROM team_members WHERE team_id=? AND user_id=?", (tid, uid))).fetchone()
        if not cur:
            raise HTTPException(404, "成员不存在")
        if cur["role"] == "owner":
            raise HTTPException(400, "不能移除 owner")
        await db.execute("DELETE FROM team_members WHERE team_id=? AND user_id=?", (tid, uid))
    await _audit(user_id, tid, "team.member.remove", "user", uid, None)
    return {"ok": True}


@app.delete("/api/teams/{tid}")
async def delete_team(tid: str, user_id: str = Depends(_require_user)):
    """删除团队（仅 owner）。同时清空 team_members 与团队库文件。"""
    await _require_team_role(tid, user_id, "owner")
    async with _registry_transaction() as db:
        await db.execute("DELETE FROM team_members WHERE team_id=?", (tid,))
        await db.execute("DELETE FROM teams WHERE team_id=?", (tid,))
    # 清理团队库文件
    import shutil as _sh
    try:
        p = _team_db_path(tid).parent
        if p.exists():
            _sh.rmtree(str(p), ignore_errors=True)
    except Exception:
        pass
    await _audit(user_id, tid, "team.delete", "team", tid, None)
    return {"ok": True}


# ==================== 团队文档库（每团队库，RBAC）====================
class FolderCreateRequest(BaseModel):
    name: str
    path: str = ""  # 父文件夹完整路径，'' 表示根


class FolderRenameRequest(BaseModel):
    name: str


class FolderMoveRequest(BaseModel):
    parent_path: str = ""  # 新父目录完整路径，'' 表示根


class TeamDocCreate(BaseModel):
    title: str
    content: str = ""
    path: str = ""


@app.get("/api/teams/{tid}/docs")
async def list_team_docs(tid: str, limit: int = 200, user_id: str = Depends(_require_user)):
    """列出团队文档（viewer+ 可读）。viewer 只看到 published 文档。"""
    role = await _require_team_role(tid, user_id, "viewer")
    limit = max(1, min(limit, 500))
    async with _team_db_transaction(tid) as db:
        if role == "viewer":
            # 读者视图分离：viewer 只看 published 文档
            rows = await (await db.execute(
                "SELECT doc_id, title, substr(content,1,60) AS preview, updated_at, version, kind, path, tags, starred, is_encrypted, status "
                "FROM documents WHERE deleted_at IS NULL AND status='published' ORDER BY (kind='folder') DESC, updated_at DESC LIMIT ?",
                (limit,),
            )).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT doc_id, title, substr(content,1,60) AS preview, updated_at, version, kind, path, tags, starred, is_encrypted, status "
                "FROM documents WHERE deleted_at IS NULL ORDER BY (kind='folder') DESC, updated_at DESC LIMIT ?",
                (limit,),
            )).fetchall()
    return {"items": [
        {"doc_id": r["doc_id"], "title": r["title"], "path": r["path"] or "", "kind": r["kind"] or "file",
         "preview": r["preview"] or "", "updated_at": r["updated_at"], "version": r["version"],
         "tags": r["tags"] or "", "starred": bool(r["starred"]), "is_encrypted": bool(r["is_encrypted"]),
         "status": r["status"] if "status" in r.keys() else "draft"}
        for r in rows
    ]}


@app.get("/api/teams/{tid}/docs/search")
async def search_team_docs(tid: str, q: str = "", tag: str = "", starred: Optional[int] = None,
                           date: str = "all", sort: str = "updated", limit: int = 50,
                           user_id: str = Depends(_require_user)):
    """团队文档搜索/筛选（viewer+ 可读）。viewer 只看到 published 文档。

    路由必须定义在 /api/teams/{tid}/docs/{doc_id} 之前，否则 search 会被 {doc_id} 捕获。
    镜像个人 search_docs，补齐团队空间的"仅看收藏/标签/日期/全文"筛选（原先前端
    在团队空间仍查个人 /api/docs/search，结果错误）。
    """
    role = await _require_team_role(tid, user_id, "viewer")
    limit = max(1, min(limit, 200))
    sql = ("SELECT doc_id, title, substr(content, 1, 120) AS preview, "
           "updated_at, created_at, tags, starred, last_opened_at, status "
           "FROM documents WHERE deleted_at IS NULL")
    params = []
    # 读者视图分离：viewer 只看 published 文档（管理员/ACL 旁路见 get_team_doc 同款逻辑）
    if role == "viewer":
        sql += " AND status='published'"
    if q:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if tag:
        sql += " AND (tags LIKE ? OR tags = ?)"
        params += [f"%{tag}%", tag]
    if starred is not None:
        sql += " AND starred=?"
        params.append(1 if starred else 0)
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
    order = {
        "opened": "last_opened_at DESC",
        "created": "created_at DESC",
        "updated": "updated_at DESC",
    }.get(sort, "updated_at DESC")
    sql += f" ORDER BY {order} LIMIT ?"
    params.append(limit)
    with span("search.team_docs", tid=tid, q=q, tag=tag, limit=limit):
        async with _team_db_transaction(tid) as db:
            rows = await (await db.execute(sql, params)).fetchall()
    return {"items": [
        {
            "doc_id": r["doc_id"], "title": r["title"],
            "preview": r["preview"] or "", "updated_at": r["updated_at"],
            "created_at": r["created_at"], "tags": r["tags"] or "",
            "starred": bool(r["starred"]), "last_opened_at": r["last_opened_at"],
            "status": r["status"] if "status" in r.keys() else "draft",
            "scope": "team", "team_id": tid,
        }
        for r in rows
    ]}


@app.get("/api/teams/{tid}/docs/{doc_id}")
async def get_team_doc(tid: str, doc_id: str, user_id: str = Depends(_require_user)):
    role = await _require_team_role(tid, user_id, "viewer")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute(
            "SELECT doc_id, title, content, updated_at, version, path, is_encrypted, status, etag FROM documents WHERE doc_id=? AND deleted_at IS NULL",
            (doc_id,),
        )).fetchone()
    if not row:
        raise HTTPException(404, "文档不存在")
    # P2 团队内 per-doc ACL：文档受 ACL 管控时按授权判定；无 ACL 回退 membership+role
    acl = await _team_doc_acl_check(tid, doc_id, user_id, "read")
    if acl == "deny":
        raise HTTPException(403, "无该文档访问权（文档级 ACL）")
    # 读者视图分离：viewer 只能读 published 文档（ACL 显式授权或 admin 旁路可读未发布）
    doc_status = row["status"] if "status" in row.keys() else "draft"
    if role == "viewer" and doc_status != "published" and acl not in ("allow", "bypass"):
        raise HTTPException(403, "该文档尚未发布，读者无权访问")
    plain = _doc_atrest_decrypt(row["content"])
    etag = row["etag"] if "etag" in row.keys() and row["etag"] else _compute_doc_etag(row["version"], row["title"], plain)
    return {"doc_id": row["doc_id"], "title": row["title"], "content": plain,
            "path": row["path"] or "", "version": row["version"], "updated_at": row["updated_at"],
            "is_encrypted": bool(row["is_encrypted"]), "etag": etag}


@app.post("/api/teams/{tid}/docs", status_code=201)
async def create_team_doc(tid: str, req: TeamDocCreate, user_id: str = Depends(_require_user)):
    """创建团队文档（需 doc.create 权限）。"""
    await _require_team_permission(tid, user_id, "doc.create")
    if len(req.content.encode("utf-8")) > DOC_MAX_CONTENT_BYTES:
        raise HTTPException(413, "文档内容超限")
    qerr = await _doc_quota_check_team(tid, len(req.content.encode("utf-8")))
    if qerr:
        raise HTTPException(429, qerr)
    doc_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    etag = _compute_doc_etag(1, req.title, req.content)
    async with _team_db_transaction(tid) as db:
        await db.execute(
            "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, user_id, etag) VALUES (?, ?, ?, ?, ?, 'file', ?, ?, ?)",
            (doc_id, req.title, _doc_atrest_encrypt(req.content), now, now, req.path or "", user_id, etag),
        )
        # 版本快照 v1（团队文档行级 diff 审阅基线）
        try:
            await db.execute(
                "INSERT INTO doc_versions (doc_id, version, title, content, created_at, created_by) VALUES (?,?,?,?,?,?)",
                (doc_id, 1, req.title, _doc_atrest_encrypt(req.content), now, user_id),
            )
            await _prune_doc_versions(db, doc_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("团队文档版本快照失败 doc_id=%s err=%s", doc_id, e)
    await _audit(user_id, tid, "doc.create", "doc", doc_id, req.title)
    return {"doc_id": doc_id, "title": req.title, "version": 1, "path": req.path or "", "etag": etag}


@app.put("/api/teams/{tid}/docs/{doc_id}")
async def update_team_doc(tid: str, doc_id: str, payload: dict, if_match: Optional[str] = Header(None, alias="If-Match"), user_id: str = Depends(_require_user)):
    """更新团队文档内容/标题（需 doc.edit 权限）。支持 If-Match 乐观锁。
    P2 per-doc ACL：文档受 ACL 管控时按 write 授权判定，授权用户可绕过 doc.edit 角色权限。"""
    acl = await _team_doc_acl_check(tid, doc_id, user_id, "write")
    if acl == "deny":
        raise HTTPException(403, "无该文档写入权（文档级 ACL）")
    if acl is None:
        await _require_team_permission(tid, user_id, "doc.edit")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        cur_etag = row["etag"] if "etag" in row.keys() and row["etag"] else _compute_doc_etag(row["version"], row["title"], _doc_atrest_decrypt(row["content"]))
        if if_match is not None and if_match != cur_etag:
            raise HTTPException(409, "文档已被他人修改（ETag 失配），请刷新后重试")
        if payload.get("version") is not None and payload["version"] != row["version"]:
            raise HTTPException(409, "版本冲突")
        title = payload.get("title", row["title"])
        path = payload.get("path", row["path"])
        # 重命名/移动时检查同目录下重名（团队库范围）
        if (payload.get("title") is not None and title != row["title"]) or \
           (payload.get("path") is not None and path != row["path"]):
            dup = await (await db.execute(
                "SELECT 1 FROM documents WHERE path=? AND title=? AND doc_id<>? AND deleted_at IS NULL",
                (path, title, doc_id),
            )).fetchone()
            if dup:
                raise HTTPException(409, "目标位置已存在同名节点")
        # 正文：传入为明文（落库前静态加密）；未传则沿用库内已存形态
        if "content" in payload:
            content = _doc_atrest_encrypt(payload["content"])
            plain = payload["content"]
        else:
            content = row["content"]
            plain = _doc_atrest_decrypt(row["content"])
        if len(plain.encode("utf-8")) > DOC_MAX_CONTENT_BYTES:
            raise HTTPException(413, "文档内容超限")
        now = _utcnow_iso()
        new_version = row["version"] + 1
        new_etag = _compute_doc_etag(new_version, title, plain)
        await db.execute("UPDATE documents SET title=?, content=?, updated_at=?, version=?, path=?, etag=? WHERE doc_id=?",
                         (title, content, now, new_version, path, new_etag, doc_id))
        # 版本快照（团队文档行级 diff 审阅）
        if "content" in payload or "title" in payload:
            try:
                await db.execute(
                    "INSERT INTO doc_versions (doc_id, version, title, content, created_at, created_by) VALUES (?,?,?,?,?,?)",
                    (doc_id, new_version, title, content, now, user_id),
                )
                await _prune_doc_versions(db, doc_id)
            except Exception as e:  # noqa: BLE001
                logger.warning("团队文档版本快照失败 doc_id=%s err=%s", doc_id, e)
    await _audit(user_id, tid, "doc.update", "doc", doc_id, f"v{new_version}")
    # 内容中的 @mention 通知（团队文档，基于明文解析）
    await _notify_mentions(plain, author_id=user_id, link=f"/?doc={doc_id}&team={tid}", detail_prefix="团队文档中提及你")
    return {"doc_id": doc_id, "version": new_version, "updated_at": now, "etag": new_etag}


@app.delete("/api/teams/{tid}/docs/{doc_id}")
async def delete_team_doc(tid: str, doc_id: str, user_id: str = Depends(_require_user)):
    """软删除团队文档（需 doc.delete 权限）。正在分享的文档同样拦截（复用 share_code 检查）。
    P2 per-doc ACL：受管控文档需 write 授权方可删除。"""
    acl = await _team_doc_acl_check(tid, doc_id, user_id, "write")
    if acl == "deny":
        raise HTTPException(403, "无该文档删除权（文档级 ACL）")
    if acl is None:
        await _require_team_permission(tid, user_id, "doc.delete")
    # 法务保留：阻断团队文档删除
    hold = await _doc_legal_hold(team_id=tid)
    if hold:
        raise HTTPException(409, f"文档处于法务保留，禁止删除：{hold}")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute("SELECT share_code FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        if row["share_code"]:
            raise HTTPException(409, "该文档正在分享，请先取消分享后再删除")
        await db.execute("UPDATE documents SET deleted_at=? WHERE doc_id=?", (_utcnow_iso(), doc_id))
    await _audit(user_id, tid, "doc.delete", "doc", doc_id, None)
    return {"ok": True}


# ==================== 团队文件夹（与团队文档同库，kind='folder'）====================
# 之所以独立一组端点：个人 /api/folders 走 _db_transaction(user_id)（用户库），
# 团队文件夹必须落 _team_db_transaction(tid)（团队库），否则会误写入当前用户个人库。
# 镜像个人 folder 处理器，但按库隔离——SQL 不带 user_id 过滤（团队库已天然隔离），
# 权限走 _require_team_permission(doc.create/edit/delete)，审计带 tid。
@app.post("/api/teams/{tid}/folders", status_code=201)
async def create_team_folder(tid: str, req: FolderCreateRequest, user_id: str = Depends(_require_user)):
    """创建团队文件夹（需 doc.create 权限）。"""
    await _require_team_permission(tid, user_id, "doc.create")
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "文件夹名称不能为空")
    if "/" in name:
        raise HTTPException(400, "文件夹名称不能包含 /")
    doc_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    async with _team_db_transaction(tid) as db:
        # 同目录重名检查（团队库范围）
        dup = await (await db.execute(
            "SELECT 1 FROM documents WHERE path=? AND title=? AND kind='folder' AND deleted_at IS NULL",
            (req.path or "", name),
        )).fetchone()
        if dup:
            raise HTTPException(409, "当前目录下已存在同名文件夹")
        await db.execute(
            "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, user_id) VALUES (?, ?, '', ?, ?, 'folder', ?, ?)",
            (doc_id, name, now, now, req.path or "", user_id),
        )
    await _audit(user_id, tid, "doc.create", "doc", doc_id, f"folder:{name}")
    return {"doc_id": doc_id, "name": name, "path": req.path or ""}


@app.put("/api/teams/{tid}/folders/{doc_id}")
async def rename_team_folder(tid: str, doc_id: str, req: FolderRenameRequest, user_id: str = Depends(_require_user)):
    """重命名团队文件夹并级联更新后代 path（需 doc.edit 权限）。"""
    await _require_team_permission(tid, user_id, "doc.edit")
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "文件夹名称不能为空")
    if "/" in name:
        raise HTTPException(400, "文件夹名称不能包含 /")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not row:
            raise HTTPException(404, "文件夹不存在")
        if (row["kind"] or "file") != "folder":
            raise HTTPException(400, "目标不是文件夹")
        old_full = _node_full_path(row)
        parent_path = row["path"] or ""
        new_full = f"{parent_path}/{name}" if parent_path else name
        if name != row["title"]:
            dup = await (await db.execute(
                "SELECT 1 FROM documents WHERE path=? AND title=? AND doc_id<>? AND deleted_at IS NULL",
                (parent_path, name, doc_id),
            )).fetchone()
            if dup:
                raise HTTPException(409, "当前目录下已存在同名文件夹")
        now = _utcnow_iso()
        await db.execute("UPDATE documents SET title=?, updated_at=? WHERE doc_id=?", (name, now, doc_id))
        # 级联：所有后代（path == old_full 或 path LIKE 'old_full/%'）前缀替换为 new_full
        like = old_full + "/%"
        descendants = await (await db.execute(
            "SELECT doc_id, path FROM documents WHERE (path = ? OR path LIKE ?) AND deleted_at IS NULL",
            (old_full, like),
        )).fetchall()
        for d in descendants:
            dp = d["path"] or ""
            new_dp = new_full if dp == old_full else new_full + dp[len(old_full):]
            await db.execute("UPDATE documents SET path=?, updated_at=? WHERE doc_id=?", (new_dp, now, d["doc_id"]))
    await _audit(user_id, tid, "doc.update", "doc", doc_id, f"folder rename:{old_full}->{new_full}")
    return {"doc_id": doc_id, "name": name, "path": parent_path}


@app.post("/api/teams/{tid}/folders/{doc_id}/move")
async def move_team_folder(tid: str, doc_id: str, req: FolderMoveRequest, user_id: str = Depends(_require_user)):
    """移动团队文件夹到新父目录（parent_path），并级联更新所有后代 path 前缀（需 doc.edit 权限）。"""
    await _require_team_permission(tid, user_id, "doc.edit")
    new_parent = (req.parent_path or "").strip()
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not row:
            raise HTTPException(404, "文件夹不存在")
        if (row["kind"] or "file") != "folder":
            raise HTTPException(400, "目标不是文件夹")
        old_full = _node_full_path(row)
        # 移动到自身或自身后代下 → 非法（成环）
        if new_parent == old_full or new_parent.startswith(old_full + "/"):
            raise HTTPException(400, "不能将文件夹移动到自身或其子目录下")
        # 已在目标父目录下 → 无需移动
        if (row["path"] or "") == new_parent:
            return {"doc_id": doc_id, "path": new_parent}
        name = row["title"]
        new_full = f"{new_parent}/{name}" if new_parent else name
        # 目标父目录下同名检查
        dup = await (await db.execute(
            "SELECT 1 FROM documents WHERE path=? AND title=? AND doc_id<>? AND deleted_at IS NULL",
            (new_parent, name, doc_id),
        )).fetchone()
        if dup:
            raise HTTPException(409, "目标目录下已存在同名节点")
        now = _utcnow_iso()
        await db.execute("UPDATE documents SET path=?, updated_at=? WHERE doc_id=?", (new_parent, now, doc_id))
        # 级联：所有后代（path == old_full 或 LIKE 'old_full/%'）前缀替换为 new_full
        like = old_full + "/%"
        descendants = await (await db.execute(
            "SELECT doc_id, path FROM documents WHERE (path = ? OR path LIKE ?) AND deleted_at IS NULL",
            (old_full, like),
        )).fetchall()
        for d in descendants:
            dp = d["path"] or ""
            new_dp = new_full if dp == old_full else new_full + dp[len(old_full):]
            await db.execute("UPDATE documents SET path=?, updated_at=? WHERE doc_id=?", (new_dp, now, d["doc_id"]))
    await _audit(user_id, tid, "doc.update", "doc", doc_id, f"folder move:{old_full}->{new_full}")
    return {"doc_id": doc_id, "path": new_parent}


@app.delete("/api/teams/{tid}/folders/{doc_id}")
async def delete_team_folder(tid: str, doc_id: str, user_id: str = Depends(_require_user)):
    """软删除团队文件夹及其所有后代（需 doc.delete 权限）。含正在分享的文档则禁止。"""
    await _require_team_permission(tid, user_id, "doc.delete")
    hold = await _doc_legal_hold(team_id=tid)
    if hold:
        raise HTTPException(409, f"文档处于法务保留，禁止删除：{hold}")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not row:
            raise HTTPException(404, "文件夹不存在")
        if (row["kind"] or "file") != "folder":
            raise HTTPException(400, "目标不是文件夹")
        old_full = _node_full_path(row)
        like = old_full + "/%"
        now = _utcnow_iso()
        # 含正在分享的文档则禁止删除：先取消分享
        shared = await (await db.execute(
            "SELECT title FROM documents WHERE share_code IS NOT NULL AND deleted_at IS NULL AND (doc_id = ? OR path = ? OR path LIKE ?)",
            (doc_id, old_full, like),
        )).fetchall()
        if shared:
            names = "、".join(r["title"] for r in shared[:5])
            raise HTTPException(409, f"文件夹下有 {len(shared)} 篇文档正在分享（{names}），请先取消分享后再删除")
        cur = await db.execute(
            "UPDATE documents SET deleted_at=? WHERE (doc_id = ? OR path = ? OR path LIKE ?) AND deleted_at IS NULL",
            (now, doc_id, old_full, like),
        )
        deleted = cur.rowcount
    await _audit(user_id, tid, "doc.delete", "doc", doc_id, f"folder:{old_full} count={deleted}")
    return {"deleted": True, "count": deleted}


# ==================== P2 团队内 per-doc ACL ====================
@app.put("/api/teams/{tid}/docs/{doc_id}/acl")
async def set_team_doc_acl(tid: str, doc_id: str, target_username: str, permission: str, user_id: str = Depends(_require_user)):
    """为团队文档授予成员细粒度权限（read|write）。仅 owner/admin 或文档作者可设置。
    设置后该文档即受 ACL 管控：未被显式授权的成员将无法访问（owner/admin 旁路）。"""
    if permission not in ("read", "write"):
        raise HTTPException(400, "permission 须为 read|write")
    role = await _team_member_role(tid, user_id)
    if not role:
        raise HTTPException(403, "非团队成员")
    is_author = False
    async with _team_db_transaction(tid) as db:
        d = await (await db.execute("SELECT user_id FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not d:
            raise HTTPException(404, "文档不存在")
        is_author = (d["user_id"] == user_id)
    if role not in ("owner", "admin") and not is_author:
        raise HTTPException(403, "仅 owner/admin 或文档作者可设置文档 ACL")
    grantee = await _resolve_user_id_by_username(target_username)
    if not grantee:
        raise HTTPException(404, "目标用户不存在")
    grole = await _team_member_role(tid, grantee)
    if not grole:
        raise HTTPException(400, "目标用户非团队成员")
    now = _utcnow_iso()
    async with _team_db_transaction(tid) as db:
        await db.execute(
            "INSERT INTO team_doc_acl (doc_id, grantee_user_id, permission, granted_by, created_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(doc_id, grantee_user_id) DO UPDATE SET permission=excluded.permission, granted_by=excluded.granted_by, created_at=excluded.created_at",
            (doc_id, grantee, permission, user_id, now),
        )
    await _audit(user_id, tid, "team_doc_acl.set", "doc", doc_id, f"{target_username}={permission}")
    return {"ok": True, "doc_id": doc_id, "grantee": target_username, "permission": permission}


@app.get("/api/teams/{tid}/docs/{doc_id}/acl")
async def list_team_doc_acl(tid: str, doc_id: str, user_id: str = Depends(_require_user)):
    """列出某团队文档的 ACL 授权（owner/admin/作者可查）。"""
    role = await _team_member_role(tid, user_id)
    if not role:
        raise HTTPException(403, "非团队成员")
    async with _team_db_transaction(tid) as db:
        d = await (await db.execute("SELECT user_id FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not d:
            raise HTTPException(404, "文档不存在")
        if role not in ("owner", "admin") and d["user_id"] != user_id:
            raise HTTPException(403, "仅 owner/admin 或作者可查 ACL")
        rows = await (await db.execute(
            "SELECT grantee_user_id, permission, granted_by, created_at FROM team_doc_acl WHERE doc_id=?",
            (doc_id,),
        )).fetchall()
    # users 表在 registry 库，团队库无该表 → 逐行补查 username
    items = []
    for r in rows:
        uname = await _username_of(r["grantee_user_id"])
        items.append({"grantee_user_id": r["grantee_user_id"], "username": uname,
                      "permission": r["permission"], "granted_by": r["granted_by"], "created_at": r["created_at"]})
    return {"doc_id": doc_id, "items": items}


@app.delete("/api/teams/{tid}/docs/{doc_id}/acl")
async def delete_team_doc_acl(tid: str, doc_id: str, target_username: str, user_id: str = Depends(_require_user)):
    """撤销某成员对团队文档的 ACL 授权。撤销后若无剩余 ACL 行，文档回退 membership+role。"""
    role = await _team_member_role(tid, user_id)
    if not role:
        raise HTTPException(403, "非团队成员")
    async with _team_db_transaction(tid) as db:
        d = await (await db.execute("SELECT user_id FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,))).fetchone()
        if not d:
            raise HTTPException(404, "文档不存在")
        if role not in ("owner", "admin") and d["user_id"] != user_id:
            raise HTTPException(403, "仅 owner/admin 或作者可撤销 ACL")
        grantee = await _resolve_user_id_by_username(target_username)
        if not grantee:
            raise HTTPException(404, "目标用户不存在")
        await db.execute("DELETE FROM team_doc_acl WHERE doc_id=? AND grantee_user_id=?", (doc_id, grantee))
    await _audit(user_id, tid, "team_doc_acl.revoke", "doc", doc_id, target_username)
    return {"ok": True}


# ==================== 团队文档行级 diff 审阅 ====================
async def _require_team_doc_read(tid: str, doc_id: str, user_id: str, db) -> dict:
    """团队文档读权限统一校验（per-doc ACL + 成员身份），返回文档行。"""
    acl = await _team_doc_acl_check(tid, doc_id, user_id, "read")
    if acl == "deny":
        raise HTTPException(403, "无该文档读取权（文档级 ACL）")
    if acl is None:
        role = await _team_member_role(tid, user_id)
        if not role:
            raise HTTPException(403, "非团队成员")
    row = await (await db.execute(
        "SELECT * FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,)
    )).fetchone()
    if not row:
        raise HTTPException(404, "文档不存在")
    return dict(row)


@app.get("/api/teams/{tid}/docs/{doc_id}/versions")
async def list_team_doc_versions(tid: str, doc_id: str, limit: int = 50, user_id: str = Depends(_require_user)):
    """列出团队文档版本快照（最新在前；按 read 权限校验）。"""
    limit = max(1, min(limit, 200))
    async with _team_db_transaction(tid) as db:
        await _require_team_doc_read(tid, doc_id, user_id, db)
        rows = await (await db.execute(
            "SELECT id, version, title, content, created_at, created_by "
            "FROM doc_versions WHERE doc_id=? ORDER BY id DESC LIMIT ?",
            (doc_id, limit),
        )).fetchall()
    return {"items": [
        {"id": r["id"], "version": r["version"], "title": r["title"],
         "preview": (_doc_atrest_decrypt(r["content"]) or "")[:80],
         "created_at": r["created_at"], "created_by": r["created_by"]}
        for r in rows
    ]}


@app.get("/api/teams/{tid}/docs/{doc_id}/versions/{vid}")
async def get_team_doc_version(tid: str, doc_id: str, vid: int, user_id: str = Depends(_require_user)):
    """获取团队文档某版本快照完整内容。"""
    async with _team_db_transaction(tid) as db:
        await _require_team_doc_read(tid, doc_id, user_id, db)
        row = await (await db.execute(
            "SELECT id, version, title, content, created_at, created_by FROM doc_versions WHERE id=? AND doc_id=?",
            (vid, doc_id),
        )).fetchone()
    if not row:
        raise HTTPException(404, "版本不存在")
    return {"id": row["id"], "version": row["version"], "title": row["title"],
            "content": _doc_atrest_decrypt(row["content"]),
            "created_at": row["created_at"], "created_by": row["created_by"]}


@app.get("/api/teams/{tid}/docs/{doc_id}/versions/{v1}/diff/{v2}")
async def diff_team_doc_versions(tid: str, doc_id: str, v1: int, v2: str, user_id: str = Depends(_require_user)):
    """对比团队文档两个版本的行级 diff。v1 为 doc_versions.id；v2 为 id 或 "current"。
    结构化 added/removed/modified + unified 文本，供前端行级审阅侧栏渲染。"""
    async with _team_db_transaction(tid) as db:
        cur = await _require_team_doc_read(tid, doc_id, user_id, db)
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
        "doc_id": doc_id, "team_id": tid,
        "v1": {"id": old["id"], "version": old["version"], "title": old["title"],
               "created_at": old["created_at"], "created_by": old["created_by"]},
        "v2": {"id": new["id"], "version": new["version"], "title": new["title"],
               "created_at": new["created_at"], "created_by": new["created_by"]},
        "diff": diff,
    }


# ==================== AI 助手代理 ====================
class AiChatMessage(BaseModel):
    role: str
    content: str


class AiChatRequest(BaseModel):
    config_id: str  # 服务端加密落库的配置 id；前端不再传 api_key/api_url/model
    messages: list[AiChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None


# AI 配置管理请求体
class AiConfigCreate(BaseModel):
    name: str
    api_url: str
    api_key: str = ""
    model: str


class AiConfigUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None  # 提供则重新加密；不提供则保留原密钥
    model: Optional[str] = None


@app.get("/api/ai/configs")
async def list_ai_configs(user_id: str = Depends(_require_user)):
    """列出当前用户的 AI 模型配置。仅返回脱敏 key_hint，明文 key 永不下发。"""
    await _migrate_legacy_ai_configs(user_id)  # 首次访问迁移旧明文配置
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT id, name, api_url, model, enc_key, usage_count, created_at, updated_at FROM ai_configs ORDER BY usage_count DESC, created_at ASC"
        )).fetchall()
    items = []
    for r in rows:
        key = _ai_decrypt(r["enc_key"])
        items.append({
            "id": r["id"], "name": r["name"], "api_url": r["api_url"], "model": r["model"],
            "key_hint": _ai_key_hint(key), "has_key": bool(key),
            "usage_count": r["usage_count"], "created_at": r["created_at"],
        })
    return {"items": items}


@app.post("/api/ai/configs", status_code=201)
async def create_ai_config(req: AiConfigCreate, user_id: str = Depends(_require_user)):
    if not (req.api_url.startswith("http://") or req.api_url.startswith("https://")):
        raise HTTPException(400, "api_url 必须以 http(s) 开头")
    cid = "cfg-" + secrets.token_urlsafe(10)
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        await db.execute(
            "INSERT INTO ai_configs (id, name, api_url, model, enc_key, usage_count, created_at, updated_at) VALUES (?,?,?,?,?,0,?,?)",
            (cid, req.name, req.api_url, req.model, _ai_encrypt(req.api_key), now, now),
        )
    logger.info("创建 AI 配置 id=%s name=%s user=%s", cid, req.name[:30], user_id)
    return {"id": cid, "name": req.name, "api_url": req.api_url, "model": req.model, "has_key": bool(req.api_key)}


@app.put("/api/ai/configs/{cid}")
async def update_ai_config(cid: str, req: AiConfigUpdate, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM ai_configs WHERE id=?", (cid,))).fetchone()
        if not row:
            raise HTTPException(404, "配置不存在")
        name = req.name if req.name is not None else row["name"]
        api_url = req.api_url if req.api_url is not None else row["api_url"]
        if api_url and not (api_url.startswith("http://") or api_url.startswith("https://")):
            raise HTTPException(400, "api_url 必须以 http(s) 开头")
        model = req.model if req.model is not None else row["model"]
        enc_key = row["enc_key"]
        if req.api_key is not None:
            enc_key = _ai_encrypt(req.api_key)
        now = _utcnow_iso()
        await db.execute(
            "UPDATE ai_configs SET name=?, api_url=?, model=?, enc_key=?, updated_at=? WHERE id=?",
            (name, api_url, model, enc_key, now, cid),
        )
    return {"id": cid, "name": name, "api_url": api_url, "model": model, "has_key": bool(req.api_key) if req.api_key is not None else bool(enc_key)}


@app.delete("/api/ai/configs/{cid}")
async def delete_ai_config(cid: str, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT id FROM ai_configs WHERE id=?", (cid,))).fetchone()
        if not row:
            raise HTTPException(404, "配置不存在")
        await db.execute("DELETE FROM ai_configs WHERE id=?", (cid,))
    return {"ok": True}


# ==================== AI 对话历史（每用户库内存档）====================
class AiConvSaveRequest(BaseModel):
    title: Optional[str] = None
    messages: list  # [{role, content, ...}]，原样存 JSON


class AiConvUpdateRequest(BaseModel):
    title: Optional[str] = None
    messages: Optional[list] = None


def _ai_conv_title(messages, fallback="新对话"):
    """从首条 user 消息取标题（截断 30 字）。"""
    if isinstance(messages, list):
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "user":
                c = (m.get("content") or "").strip().replace("\n", " ")
                if c:
                    return c[:30] + ("…" if len(c) > 30 else "")
    return fallback


@app.get("/api/ai/conversations")
async def list_ai_conversations(user_id: str = Depends(_require_user)):
    """列出当前用户的对话历史（仅元数据，不含 messages 正文）。"""
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT id, title, msg_count, created_at, updated_at FROM ai_conversations ORDER BY updated_at DESC"
        )).fetchall()
    return {"items": [
        {"id": r["id"], "title": r["title"], "msg_count": r["msg_count"],
         "created_at": r["created_at"], "updated_at": r["updated_at"]}
        for r in rows
    ]}


@app.post("/api/ai/conversations", status_code=201)
async def save_ai_conversation(req: AiConvSaveRequest, user_id: str = Depends(_require_user)):
    """保存当前对话为新历史。自动标题=首条 user 消息。"""
    msgs = req.messages if isinstance(req.messages, list) else []
    title = (req.title or "").strip() or _ai_conv_title(msgs)
    now = _utcnow_iso()
    cid = "conv-" + secrets.token_urlsafe(10)
    async with _db_transaction(user_id) as db:
        await db.execute(
            "INSERT INTO ai_conversations (id, title, messages_json, msg_count, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (cid, title, json.dumps(msgs, ensure_ascii=False), len(msgs), now, now),
        )
    return {"id": cid, "title": title, "msg_count": len(msgs)}


@app.post("/api/ai/conversations/{cid}/fork", status_code=201)
async def fork_ai_conversation(cid: str, fork_at: int = 0, user_id: str = Depends(_require_user)):
    """从某条对话的指定消息位置分叉出新对话。"""
    async with _db_transaction(user_id) as db:
        r = await (await db.execute(
            "SELECT title, messages_json FROM ai_conversations WHERE id=?", (cid,)
        )).fetchone()
        if not r:
            raise HTTPException(404, "对话不存在")
        try:
            msgs = json.loads(r["messages_json"] or "[]")
        except Exception:
            msgs = []
        # 截取到 fork_at 位置
        fork_msgs = msgs[:fork_at] if fork_at > 0 else msgs
        now = _utcnow_iso()
        new_cid = "conv-" + secrets.token_urlsafe(10)
        new_title = (r["title"] or "") + f" (fork@{fork_at})"
        await db.execute(
            "INSERT INTO ai_conversations (id, title, messages_json, msg_count, created_at, updated_at, parent_id, fork_at_msg_index) VALUES (?,?,?,?,?,?,?,?)",
            (new_cid, new_title, json.dumps(fork_msgs, ensure_ascii=False), len(fork_msgs), now, now, cid, fork_at),
        )
    return {"id": new_cid, "title": new_title, "parent_id": cid, "fork_at": fork_at, "msg_count": len(fork_msgs)}


@app.get("/api/ai/conversations/{cid}")
async def get_ai_conversation(cid: str, user_id: str = Depends(_require_user)):
    """加载某条对话历史（含完整 messages）。"""
    async with _db_transaction(user_id) as db:
        r = await (await db.execute(
            "SELECT id, title, messages_json, msg_count, created_at, updated_at FROM ai_conversations WHERE id=?", (cid,)
        )).fetchone()
    if not r:
        raise HTTPException(404, "对话不存在")
    try:
        msgs = json.loads(r["messages_json"] or "[]")
    except Exception:
        msgs = []
    return {"id": r["id"], "title": r["title"], "messages": msgs,
            "msg_count": r["msg_count"], "created_at": r["created_at"], "updated_at": r["updated_at"]}


@app.put("/api/ai/conversations/{cid}")
async def update_ai_conversation(cid: str, req: AiConvUpdateRequest, user_id: str = Depends(_require_user)):
    """更新对话标题或 messages。"""
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM ai_conversations WHERE id=?", (cid,))).fetchone()
        if not row:
            raise HTTPException(404, "对话不存在")
        title = (req.title or "").strip() or row["title"]
        if req.messages is not None:
            msgs = req.messages if isinstance(req.messages, list) else []
            messages_json = json.dumps(msgs, ensure_ascii=False)
            msg_count = len(msgs)
            # 标题未显式提供且原为空时，按首条 user 消息补一个
            if not (req.title or "").strip() and not row["title"]:
                title = _ai_conv_title(msgs, fallback=title)
            await db.execute(
                "UPDATE ai_conversations SET title=?, messages_json=?, msg_count=?, updated_at=? WHERE id=?",
                (title, messages_json, msg_count, now, cid),
            )
        else:
            await db.execute("UPDATE ai_conversations SET title=?, updated_at=? WHERE id=?", (title, now, cid))
    return {"id": cid, "title": title}


@app.delete("/api/ai/conversations/{cid}")
async def delete_ai_conversation(cid: str, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT id FROM ai_conversations WHERE id=?", (cid,))).fetchone()
        if not row:
            raise HTTPException(404, "对话不存在")
        await db.execute("DELETE FROM ai_conversations WHERE id=?", (cid,))
    return {"ok": True}


async def _ai_collect_stream(resp):
    """消费上游 SSE 流，累加 delta.content；返回 (content, raw_tail_for_error)。"""
    content_parts = []
    raw_tail = ""
    async for line in resp.aiter_lines():
        line = line.strip()
        if not line:
            continue
        raw_tail = line
        if line.startswith("data:"):
            payload = line[5:].lstrip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except Exception:
                continue
            choices = obj.get("choices") if isinstance(obj, dict) else None
            if choices and isinstance(choices, list) and choices[0]:
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    content_parts.append(piece)
    return "".join(content_parts), raw_tail


async def _ai_forward(api_url: str, api_key: str, model: str, messages: list,
                      temperature: float = 0.7, max_tokens: int | None = None,
                      log_user: str = "") -> dict:
    """统一的上游转发：流式 SSE + 非流式回退 + 错误处理。返回 {ok,status,content,error?}。"""
    if not (api_url.startswith("http://") or api_url.startswith("https://")):
        return {"ok": False, "status": 0, "error": "配置的 api_url 非法"}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,  # 流式避免整段响应超时
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    def _host():
        try:
            from urllib.parse import urlparse as _u
            return _u(api_url).netloc
        except Exception:
            return ""

    try:
        with span("ai.forward", model=model, host=_host()):
            async with httpx.AsyncClient(timeout=AI_PROXY_TIMEOUT) as client:
                async with client.stream("POST", api_url, headers=headers, json=body) as upstream:
                    if upstream.status_code != 200:
                        err_text = ""
                        try:
                            async for chunk in upstream.aiter_bytes():
                                err_text += chunk.decode("utf-8", "ignore")
                        except Exception:
                            pass
                        return {"ok": False, "status": upstream.status_code, "error": err_text[:2000]}
                    ctype = upstream.headers.get("content-type", "")
                    if "text/event-stream" in ctype or "stream" in ctype:
                        content, raw_tail = await _ai_collect_stream(upstream)
                        if not content:
                            return {"ok": False, "status": 200, "error": f"上游流式响应未返回内容（末行: {raw_tail[:200]}）"}
                        return {"ok": True, "status": 200, "content": content}
                    data = await upstream.aread()
                    try:
                        obj = json.loads(data.decode("utf-8", "ignore"))
                    except Exception as e:
                        return {"ok": False, "status": 200, "error": f"解析上游响应失败: {e}", "content": data.decode('utf-8', 'ignore')[:2000]}
                    content = ""
                    choices = obj.get("choices") if isinstance(obj, dict) else None
                    if choices and isinstance(choices, list) and choices[0]:
                        msg = choices[0].get("message") or {}
                        content = msg.get("content") or ""
                    if not content and isinstance(obj, dict):
                        content = obj.get("content") or obj.get("text") or ""
                    return {"ok": True, "status": 200, "content": content or ""}
    except httpx.TimeoutException as e:
        logger.warning("AI 代理超时 user=%s url=%s: %s", log_user, api_url, e)
        return {"ok": False, "status": 0, "error": f"上游响应超时（>{AI_PROXY_TIMEOUT}s）：{type(e).__name__}: {e}。请检查 API 地址是否可达、模型是否过慢，或调大 AI_PROXY_TIMEOUT。"}
    except httpx.HTTPError as e:
        host = _host()
        logger.warning("AI 代理连接失败 user=%s host=%s url=%s: %s: %s", log_user, host, api_url, type(e).__name__, e)
        return {"ok": False, "status": 0, "error": f"连接上游失败 [{type(e).__name__}] host={host}: {e}。请确认 API 地址正确且后端可访问该地址（本地 LLM 注意后端与模型是否同网络）。"}


async def _ai_resolve_config(db_tx, db, config_id, table="ai_configs"):
    """从给定库连接取出并解密 AI 配置。返回 dict(api_url, model, api_key) 或 None。"""
    row = await (await db.execute(
        "SELECT id, api_url, model, enc_key FROM ai_configs WHERE id=?", (config_id,)
    )).fetchone()
    if not row:
        return None
    return {"api_url": row["api_url"], "model": row["model"], "api_key": _ai_decrypt(row["enc_key"])}


@app.post("/api/ai/chat")
async def ai_chat(req: AiChatRequest, user_id: str = Depends(_require_user)):
    """个人空间 AI 聊天：取个人配置解密转发，配额+审计+用量统计。"""
    if not await _check_endpoint_rate_limit(user_id, "/api/ai/chat"):
        raise HTTPException(429, "AI 调用过于频繁（每分钟 10 次）")
    if not req.messages:
        raise HTTPException(400, "messages 不能为空")
    raw = req.model_dump_json()
    if len(raw.encode("utf-8")) > AI_PROXY_MAX_BYTES:
        raise HTTPException(413, f"AI 请求体超过 {AI_PROXY_MAX_BYTES} 字节限制")
    # 配额检查
    quota_err = await _ai_quota_check(user_id, None)
    if quota_err:
        raise HTTPException(429, quota_err)
    # 取配置并解密
    async with _db_transaction(user_id) as db:
        cfg = await _ai_resolve_config(None, db, req.config_id)
    if not cfg:
        raise HTTPException(404, "AI 配置不存在")
    # 模型白名单
    if AI_ALLOWED_MODELS and cfg["model"] not in AI_ALLOWED_MODELS:
        raise HTTPException(400, f"模型 {cfg['model']} 不在允许列表内")
    # 计数 + 用量
    async with _db_transaction(user_id) as db:
        await db.execute("UPDATE ai_configs SET usage_count = usage_count + 1 WHERE id=?", (req.config_id,))
    await _ai_usage_inc(user_id, None)
    await _audit(user_id, None, "ai.chat", "config", req.config_id, f"model={cfg['model']}")
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]
    result = await _ai_forward(cfg["api_url"], cfg["api_key"], cfg["model"], msgs,
                               req.temperature, req.max_tokens, log_user=user_id)
    return result


# ==================== 团队 AI 配置治理 + 团队聊天 + 用量 ====================
@app.get("/api/teams/{tid}/ai/configs")
async def list_team_ai_configs(tid: str, user_id: str = Depends(_require_user)):
    """列出团队 AI 配置（成员可见，key 脱敏）。"""
    await _require_team_role(tid, user_id, "viewer")
    async with _team_db_transaction(tid) as db:
        rows = await (await db.execute(
            "SELECT id, name, api_url, model, enc_key, usage_count, created_at FROM ai_configs ORDER BY usage_count DESC, created_at ASC"
        )).fetchall()
    items = []
    for r in rows:
        key = _ai_decrypt(r["enc_key"])
        items.append({
            "id": r["id"], "name": r["name"], "api_url": r["api_url"], "model": r["model"],
            "key_hint": _ai_key_hint(key), "has_key": bool(key),
            "usage_count": r["usage_count"], "created_at": r["created_at"],
        })
    return {"items": items}


@app.post("/api/teams/{tid}/ai/configs", status_code=201)
async def create_team_ai_config(tid: str, req: AiConfigCreate, user_id: str = Depends(_require_user)):
    """创建团队 AI 配置（admin+ 管理，加密落库；成员可调用不暴露明文）。"""
    await _require_team_role(tid, user_id, "admin")
    if not (req.api_url.startswith("http://") or req.api_url.startswith("https://")):
        raise HTTPException(400, "api_url 必须以 http(s) 开头")
    cid = "cfg-" + secrets.token_urlsafe(10)
    now = _utcnow_iso()
    async with _team_db_transaction(tid) as db:
        await db.execute(
            "INSERT INTO ai_configs (id, name, api_url, model, enc_key, usage_count, created_at, updated_at) VALUES (?,?,?,?,?,0,?,?)",
            (cid, req.name, req.api_url, req.model, _ai_encrypt(req.api_key), now, now),
        )
    await _audit(user_id, tid, "ai.config.create", "config", cid, req.name)
    return {"id": cid, "name": req.name, "api_url": req.api_url, "model": req.model, "has_key": bool(req.api_key)}


@app.put("/api/teams/{tid}/ai/configs/{cid}")
async def update_team_ai_config(tid: str, cid: str, req: AiConfigUpdate, user_id: str = Depends(_require_user)):
    await _require_team_role(tid, user_id, "admin")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute("SELECT * FROM ai_configs WHERE id=?", (cid,))).fetchone()
        if not row:
            raise HTTPException(404, "配置不存在")
        name = req.name if req.name is not None else row["name"]
        api_url = req.api_url if req.api_url is not None else row["api_url"]
        model = req.model if req.model is not None else row["model"]
        enc_key = row["enc_key"]
        if req.api_key is not None:
            enc_key = _ai_encrypt(req.api_key)
        await db.execute("UPDATE ai_configs SET name=?, api_url=?, model=?, enc_key=?, updated_at=? WHERE id=?",
                          (name, api_url, model, enc_key, _utcnow_iso(), cid))
    await _audit(user_id, tid, "ai.config.update", "config", cid, None)
    return {"id": cid, "name": name, "api_url": api_url, "model": model, "has_key": bool(enc_key)}


@app.delete("/api/teams/{tid}/ai/configs/{cid}")
async def delete_team_ai_config(tid: str, cid: str, user_id: str = Depends(_require_user)):
    await _require_team_role(tid, user_id, "admin")
    async with _team_db_transaction(tid) as db:
        if not await (await db.execute("SELECT id FROM ai_configs WHERE id=?", (cid,))).fetchone():
            raise HTTPException(404, "配置不存在")
        await db.execute("DELETE FROM ai_configs WHERE id=?", (cid,))
    await _audit(user_id, tid, "ai.config.delete", "config", cid, None)
    return {"ok": True}


# ==================== 团队 AI 对话历史（与团队配置同库，ai_conversations 表）====================
# 镜像个人 /api/ai/conversations，但落 _team_db_transaction(tid)；否则团队空间聊天历史
# 会误存进当前用户个人库（与团队 AI 配置同一种泄漏）。
@app.get("/api/teams/{tid}/ai/conversations")
async def list_team_ai_conversations(tid: str, user_id: str = Depends(_require_user)):
    """列出团队对话历史（viewer+ 可读，仅元数据）。"""
    await _require_team_role(tid, user_id, "viewer")
    async with _team_db_transaction(tid) as db:
        rows = await (await db.execute(
            "SELECT id, title, msg_count, created_at, updated_at FROM ai_conversations ORDER BY updated_at DESC"
        )).fetchall()
    return {"items": [
        {"id": r["id"], "title": r["title"], "msg_count": r["msg_count"],
         "created_at": r["created_at"], "updated_at": r["updated_at"]}
        for r in rows
    ]}


@app.post("/api/teams/{tid}/ai/conversations", status_code=201)
async def save_team_ai_conversation(tid: str, req: AiConvSaveRequest, user_id: str = Depends(_require_user)):
    """保存团队对话为新历史（member+）。自动标题=首条 user 消息。"""
    await _require_team_role(tid, user_id, "member")
    msgs = req.messages if isinstance(req.messages, list) else []
    title = (req.title or "").strip() or _ai_conv_title(msgs)
    now = _utcnow_iso()
    cid = "conv-" + secrets.token_urlsafe(10)
    async with _team_db_transaction(tid) as db:
        await db.execute(
            "INSERT INTO ai_conversations (id, title, messages_json, msg_count, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (cid, title, json.dumps(msgs, ensure_ascii=False), len(msgs), now, now),
        )
    await _audit(user_id, tid, "ai.conv.create", "config", cid, title)
    return {"id": cid, "title": title, "msg_count": len(msgs)}


@app.get("/api/teams/{tid}/ai/conversations/{cid}")
async def get_team_ai_conversation(tid: str, cid: str, user_id: str = Depends(_require_user)):
    """加载某条团队对话历史（viewer+，含完整 messages）。"""
    await _require_team_role(tid, user_id, "viewer")
    async with _team_db_transaction(tid) as db:
        r = await (await db.execute(
            "SELECT id, title, messages_json, msg_count, created_at, updated_at FROM ai_conversations WHERE id=?", (cid,)
        )).fetchone()
    if not r:
        raise HTTPException(404, "对话不存在")
    try:
        msgs = json.loads(r["messages_json"] or "[]")
    except Exception:
        msgs = []
    return {"id": r["id"], "title": r["title"], "messages": msgs,
            "msg_count": r["msg_count"], "created_at": r["created_at"], "updated_at": r["updated_at"]}


@app.put("/api/teams/{tid}/ai/conversations/{cid}")
async def update_team_ai_conversation(tid: str, cid: str, req: AiConvUpdateRequest, user_id: str = Depends(_require_user)):
    """更新团队对话标题或 messages（member+）。"""
    await _require_team_role(tid, user_id, "member")
    now = _utcnow_iso()
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute("SELECT * FROM ai_conversations WHERE id=?", (cid,))).fetchone()
        if not row:
            raise HTTPException(404, "对话不存在")
        title = (req.title or "").strip() or row["title"]
        if req.messages is not None:
            msgs = req.messages if isinstance(req.messages, list) else []
            messages_json = json.dumps(msgs, ensure_ascii=False)
            msg_count = len(msgs)
            if not (req.title or "").strip() and not row["title"]:
                title = _ai_conv_title(msgs, fallback=title)
            await db.execute(
                "UPDATE ai_conversations SET title=?, messages_json=?, msg_count=?, updated_at=? WHERE id=?",
                (title, messages_json, msg_count, now, cid),
            )
        else:
            await db.execute("UPDATE ai_conversations SET title=?, updated_at=? WHERE id=?", (title, now, cid))
    await _audit(user_id, tid, "ai.conv.update", "config", cid, None)
    return {"id": cid, "title": title}


@app.delete("/api/teams/{tid}/ai/conversations/{cid}")
async def delete_team_ai_conversation(tid: str, cid: str, user_id: str = Depends(_require_user)):
    """删除团队对话（member+）。"""
    await _require_team_role(tid, user_id, "member")
    async with _team_db_transaction(tid) as db:
        if not await (await db.execute("SELECT id FROM ai_conversations WHERE id=?", (cid,))).fetchone():
            raise HTTPException(404, "对话不存在")
        await db.execute("DELETE FROM ai_conversations WHERE id=?", (cid,))
    await _audit(user_id, tid, "ai.conv.delete", "config", cid, None)
    return {"ok": True}


@app.post("/api/teams/{tid}/ai/conversations/{cid}/fork", status_code=201)
async def fork_team_ai_conversation(tid: str, cid: str, fork_at: int = 0, user_id: str = Depends(_require_user)):
    """从某条团队对话的指定消息位置分叉出新对话（member+）。"""
    await _require_team_role(tid, user_id, "member")
    async with _team_db_transaction(tid) as db:
        r = await (await db.execute(
            "SELECT title, messages_json FROM ai_conversations WHERE id=?", (cid,)
        )).fetchone()
        if not r:
            raise HTTPException(404, "对话不存在")
        try:
            msgs = json.loads(r["messages_json"] or "[]")
        except Exception:
            msgs = []
        fork_msgs = msgs[:fork_at] if fork_at > 0 else msgs
        now = _utcnow_iso()
        new_cid = "conv-" + secrets.token_urlsafe(10)
        new_title = (r["title"] or "") + f" (fork@{fork_at})"
        await db.execute(
            "INSERT INTO ai_conversations (id, title, messages_json, msg_count, created_at, updated_at, parent_id, fork_at_msg_index) VALUES (?,?,?,?,?,?,?,?)",
            (new_cid, new_title, json.dumps(fork_msgs, ensure_ascii=False), len(fork_msgs), now, now, cid, fork_at),
        )
    await _audit(user_id, tid, "ai.conv.fork", "config", new_cid, f"from={cid}@{fork_at}")
    return {"id": new_cid, "title": new_title, "parent_id": cid, "fork_at": fork_at, "msg_count": len(fork_msgs)}


@app.post("/api/teams/{tid}/ai/chat")
async def team_ai_chat(tid: str, req: AiChatRequest, user_id: str = Depends(_require_user)):
    """团队 AI 聊天：成员可用团队配置（解密转发），按团队配额计费 + 审计。"""
    await _require_team_role(tid, user_id, "viewer")  # viewer 也可调用团队 AI
    if not req.messages:
        raise HTTPException(400, "messages 不能为空")
    raw = req.model_dump_json()
    if len(raw.encode("utf-8")) > AI_PROXY_MAX_BYTES:
        raise HTTPException(413, "AI 请求体超限")
    quota_err = await _ai_quota_check(user_id, tid)
    if quota_err:
        raise HTTPException(429, quota_err)
    async with _team_db_transaction(tid) as db:
        cfg = await _ai_resolve_config(None, db, req.config_id)
    if not cfg:
        raise HTTPException(404, "AI 配置不存在")
    if AI_ALLOWED_MODELS and cfg["model"] not in AI_ALLOWED_MODELS:
        raise HTTPException(400, f"模型 {cfg['model']} 不在允许列表内")
    async with _team_db_transaction(tid) as db:
        await db.execute("UPDATE ai_configs SET usage_count = usage_count + 1 WHERE id=?", (req.config_id,))
    await _ai_usage_inc(user_id, tid)
    await _audit(user_id, tid, "ai.chat", "config", req.config_id, f"model={cfg['model']}")
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]
    return await _ai_forward(cfg["api_url"], cfg["api_key"], cfg["model"], msgs,
                              req.temperature, req.max_tokens, log_user=f"{user_id}@{tid}")


@app.get("/api/ai/usage")
async def my_ai_usage(user_id: str = Depends(_require_user)):
    """查看自己的 AI 用量（当日 + 累计）。"""
    async with _registry_transaction() as db:
        today_personal = await _ai_usage_count(user_id, None)
        rows = await (await db.execute(
            "SELECT team_id, day, count FROM ai_usage WHERE user_id=? ORDER BY day DESC LIMIT 200", (user_id,)
        )).fetchall()
    return {"today_personal": today_personal,
            "quota_user_daily": AI_USER_DAILY_QUOTA,
            "records": [{"team_id": r["team_id"], "day": r["day"], "count": r["count"]} for r in rows]}


@app.get("/api/teams/{tid}/ai/usage")
async def team_ai_usage(tid: str, user_id: str = Depends(_require_user)):
    """团队 AI 用量（admin+ 可看）。"""
    await _require_team_role(tid, user_id, "admin")
    day = _ai_today()
    async with _registry_transaction() as db:
        today = await _ai_usage_count(user_id, tid)  # 该用户当日团队用量
        rows = await (await db.execute(
            "SELECT user_id, day, count FROM ai_usage WHERE team_id=? ORDER BY day DESC LIMIT 200", (tid,)
        )).fetchall()
    return {"today_self": today, "quota_team_daily": AI_TEAM_DAILY_QUOTA,
            "records": [{"user_id": r["user_id"], "day": r["day"], "count": r["count"]} for r in rows]}


# ==================== 数据模型 ====================
class RunRequest(BaseModel):
    language: str
    code: str
    stdin: str = ""


class RunResponse(BaseModel):
    stdout: str = ""
    stderr: str = ""
    compile_output: str = ""
    exit_code: Optional[int] = None
    status: str = ""
    time: str = ""
    memory: str = ""
    language_name: str = ""


class DocCreateRequest(BaseModel):
    title: str = ""
    content: str = ""
    path: str = ""  # 父文件夹完整路径，'' 表示根
    # 端到端加密元数据（客户端加密后传入，后端只透传存储）
    is_encrypted: Optional[bool] = None
    enc_salt: Optional[str] = None  # base64 编码的 PBKDF2 盐
    enc_iv: Optional[str] = None    # base64 编码的 AES-GCM IV
    enc_iters: Optional[int] = None  # PBKDF2 迭代次数


class DocUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    version: Optional[int] = None
    path: Optional[str] = None  # 移动到指定父文件夹（重命名/移动）
    # 端到端加密元数据
    is_encrypted: Optional[bool] = None
    enc_salt: Optional[str] = None
    enc_iv: Optional[str] = None
    enc_iters: Optional[int] = None


class ShareCreateRequest(BaseModel):
    expires_days: int = SHARE_MAX_AGE_DAYS
    password: Optional[str] = None
    max_views: Optional[int] = None  # None=不限，0=无效，>0=限制次数
    burn_after_read: bool = False  # 阅后即焚
    mode: str = "readonly"  # readonly | editable


class ShareUpdateRequest(BaseModel):
    """编辑已存在分享的属性：仅更新显式传入的字段。
    password: None=不变；""=清除；非空=设置新密码。"""
    expires_days: Optional[int] = None
    password: Optional[str] = None
    max_views: Optional[int] = None
    burn_after_read: Optional[bool] = None
    mode: Optional[str] = None


class ShareVerifyRequest(BaseModel):
    password: Optional[str] = None


# ==================== 工具函数 ====================
def b64e(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def b64d(s) -> str:
    if not s:
        return ""
    try:
        return base64.b64decode(s).decode("utf-8", errors="replace")
    except Exception:
        return ""


# ==================== API 路由 ====================
@app.get("/api/languages")
async def list_languages():
    seen = set()
    langs = []
    for alias, lid in LANGUAGE_ID_MAP.items():
        if lid in seen:
            continue
        seen.add(lid)
        langs.append({
            "alias": alias,
            "language_id": lid,
            "name": LANGUAGE_DISPLAY_NAME.get(lid, str(lid)),
        })
    return {"languages": langs}


@app.post("/api/run", response_model=RunResponse)
async def run(req: RunRequest):
    lang_key = req.language.lower()
    language_id = LANGUAGE_ID_MAP.get(lang_key)
    if language_id is None:
        raise HTTPException(400, f"不支持的语言: {req.language}")

    if len(req.code.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise HTTPException(413, f"源代码过大，超过 {MAX_SOURCE_BYTES} 字节限制")
    if len(req.stdin.encode("utf-8")) > MAX_STDIN_BYTES:
        raise HTTPException(413, f"stdin 输入过大，超过 {MAX_STDIN_BYTES} 字节限制")

    payload = {
        "language_id": language_id,
        "source_code": b64e(req.code),
        "stdin": b64e(req.stdin),
    }
    headers = {}
    if SANDBOX_API_TOKEN:
        headers["X-Judge0-Token"] = SANDBOX_API_TOKEN

    logger.info("提交运行请求 language=%s id=%d 代码长度=%d",
                lang_key, language_id, len(req.code))

    async with httpx.AsyncClient(timeout=JUDGE0_SUBMIT_TIMEOUT) as client:
        try:
            submit_resp = await client.post(
                f"{JUDGE0_API_BASE}/submissions?base64_encoded=true&fields=*",
                json=payload,
                headers=headers,
            )
        except httpx.RequestError as e:
            logger.error("连接 Judge0 失败: %s", e)
            raise HTTPException(502, f"无法连接 Judge0 执行引擎: {e}")

        if submit_resp.status_code >= 400:
            logger.error("Judge0 提交失败 status=%s body=%s",
                         submit_resp.status_code, submit_resp.text)
            raise HTTPException(502, f"Judge0 提交失败: {submit_resp.text}")

        token = (submit_resp.json() or {}).get("token")
        if not token:
            raise HTTPException(502, "Judge0 未返回 token")

        loop = asyncio.get_event_loop()
        deadline = loop.time() + JUDGE0_POLL_TIMEOUT
        last_status = ""
        while loop.time() < deadline:
            await asyncio.sleep(JUDGE0_POLL_INTERVAL)
            try:
                r = await client.get(
                    f"{JUDGE0_API_BASE}/submissions/{token}?base64_encoded=true&fields=*",
                    headers=headers,
                )
            except httpx.RequestError as e:
                logger.warning("轮询 Judge0 出错: %s", e)
                continue
            if r.status_code >= 400:
                logger.warning("Judge0 查询 token=%s 失败 status=%s body=%s",
                               token, r.status_code, r.text)
                continue
            data = r.json() or {}
            status = data.get("status") or {}
            status_id = status.get("id")
            last_status = status.get("description", "")
            if status_id not in (1, 2):
                logger.info("运行完成 token=%s status=%s exit=%s",
                            token, last_status, data.get("exit_code"))
                return RunResponse(
                    stdout=b64d(data.get("stdout")),
                    stderr=b64d(data.get("stderr")),
                    compile_output=b64d(data.get("compile_output")),
                    exit_code=data.get("exit_code"),
                    status=last_status,
                    time=data.get("time") or "",
                    memory=str(data.get("memory") or ""),
                    language_name=LANGUAGE_DISPLAY_NAME.get(language_id, ""),
                )

        raise HTTPException(504, f"Judge0 执行超时（最后状态: {last_status}）")


