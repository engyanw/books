@app.post("/api/docs/{doc_id}/versions/{vid}/restore")
async def restore_doc_version(doc_id: str, vid: int, user_id: str = Depends(_require_user)):
    """将某历史版本恢复为当前内容（产生新版本，保留历史）。"""
    async with _db_transaction(user_id) as db:
        cur = await (await db.execute("SELECT version, title, content, classification FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not cur:
            raise HTTPException(404, "文档不存在")
        ver = await (await db.execute("SELECT title, content FROM doc_versions WHERE id=? AND doc_id=?", (vid, doc_id))).fetchone()
        if not ver:
            raise HTTPException(404, "版本不存在")
        # 先把当前版本存入历史
        now = _utcnow_iso()
        new_version = cur["version"] + 1
        await db.execute(
            "INSERT INTO doc_versions (doc_id, version, title, content, created_at, created_by) VALUES (?,?,?,?,?,?)",
            (doc_id, cur["version"], cur["title"], cur["content"], now, user_id),
        )
        await _prune_doc_versions(db, doc_id)
        await db.execute(
            "UPDATE documents SET title=?, content=?, updated_at=?, version=? WHERE doc_id=?",
            (ver["title"], ver["content"], now, new_version, doc_id),
        )
    await _audit(user_id, None, "doc.restore", "version", str(vid), f"->v{new_version}")
    return {"doc_id": doc_id, "version": new_version, "restored_from": vid}


# ==================== E2：并行草稿（branch-like drafts）+ 合并 ====================
def _three_way_merge(base: str, a: str, b: str) -> tuple[str, bool]:
    """三方合并：base 为共同祖先，a/b 为两侧修改。返回 (合并文本, 是否含冲突)。
    无冲突区域两侧改动直接采纳；同一区域两侧都改则产生 <<<<<<< ======= >>>>>>> 冲突标记。
    """
    import difflib
    base_lines = base.splitlines(keepends=True)
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    # 用两个 SequenceMatcher 以 base 为锚，逐块推进
    sm_a = difflib.SequenceMatcher(None, base_lines, a_lines)
    sm_b = difflib.SequenceMatcher(None, base_lines, b_lines)
    # 合并两侧变更：对 base 的每个区段，判断 a 改了没、b 改了没
    ops_a = sm_a.get_opcodes()
    ops_b = sm_b.get_opcodes()
    # 简化：若任一侧完全等于 base（无变更），直接取另一侧（fast-forward）
    if a_lines == base_lines:
        return b, False
    if b_lines == base_lines:
        return a, False
    if a_lines == b_lines:
        return a, False
    # 两边都改了基线 → 冲突，产出冲突标记供人工解决
    merged = (
        "<<<<<<< branch\n"
        + "".join(a_lines)
        + "=======\n"
        + "".join(b_lines)
        + ">>>>>>> main\n"
    )
    return merged, True


class BranchCreateRequest(BaseModel):
    pass  # 基于当前已发布版本开分支


@app.post("/api/docs/{doc_id}/branches", status_code=201)
async def create_branch(doc_id: str, user_id: str = Depends(_require_user)):
    """基于当前已发布版本开一个并行草稿分支（记录基线 content 用于三方合并）。"""
    async with _db_transaction(user_id) as db:
        cur = await (await db.execute("SELECT version, content, title FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not cur:
            raise HTTPException(404, "文档不存在")
        bid = "br-" + secrets.token_urlsafe(8)
        now = _utcnow_iso()
        await db.execute(
            "INSERT INTO doc_branches (branch_id, doc_id, base_version, base_content, head_content, status, author, created_at, updated_at) "
            "VALUES (?,?,?,?,?, 'open', ?, ?, ?)",
            (bid, doc_id, cur["version"], cur["content"] or "", cur["content"] or "", user_id, now, now),
        )
    await _audit(user_id, None, "branch.create", "doc", doc_id, f"base=v{cur['version']} bid={bid}")
    return {"branch_id": bid, "base_version": cur["version"]}


@app.get("/api/docs/{doc_id}/branches")
async def list_branches(doc_id: str, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT branch_id, base_version, status, author, created_at, updated_at, merged_at "
            "FROM doc_branches WHERE doc_id=? ORDER BY created_at DESC", (doc_id,)
        )).fetchall()
    return {"items": [
        {"branch_id": r["branch_id"], "base_version": r["base_version"], "status": r["status"],
         "author": r["author"], "created_at": r["created_at"], "updated_at": r["updated_at"], "merged_at": r["merged_at"]}
        for r in rows
    ]}


@app.get("/api/docs/{doc_id}/branches/{bid}")
async def get_branch(doc_id: str, bid: str, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM doc_branches WHERE branch_id=? AND doc_id=?", (bid, doc_id))).fetchone()
    if not row:
        raise HTTPException(404, "分支不存在")
    return {"branch_id": row["branch_id"], "base_version": row["base_version"], "status": row["status"],
            "head_content": _doc_atrest_decrypt(row["head_content"]), "author": row["author"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "merged_at": row["merged_at"]}


class BranchUpdateRequest(BaseModel):
    head_content: str


@app.put("/api/docs/{doc_id}/branches/{bid}")
async def update_branch(doc_id: str, bid: str, req: BranchUpdateRequest, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT status FROM doc_branches WHERE branch_id=? AND doc_id=?", (bid, doc_id))).fetchone()
        if not row:
            raise HTTPException(404, "分支不存在")
        if row["status"] != "open":
            raise HTTPException(409, "分支已结束，不可编辑")
        await db.execute("UPDATE doc_branches SET head_content=?, updated_at=? WHERE branch_id=?",
                          (_doc_atrest_encrypt(req.head_content), _utcnow_iso(), bid))
    return {"ok": True, "branch_id": bid}


@app.post("/api/docs/{doc_id}/branches/{bid}/merge")
async def merge_branch(doc_id: str, bid: str, user_id: str = Depends(_require_user)):
    """将分支合并回主干：基于 base_content 三方合并当前主干与分支 head。
    无冲突→快进合并产生新版本；有冲突→写入冲突标记内容，状态置 conflict 待人工解决。"""
    async with _db_transaction(user_id) as db:
        br = await (await db.execute("SELECT * FROM doc_branches WHERE branch_id=? AND doc_id=?", (bid, doc_id))).fetchone()
        if not br:
            raise HTTPException(404, "分支不存在")
        if br["status"] != "open":
            raise HTTPException(409, "分支已处理")
        cur = await (await db.execute("SELECT version, content, title FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not cur:
            raise HTTPException(404, "文档不存在")
        base = _doc_atrest_decrypt(br["base_content"] or "")
        main_content = _doc_atrest_decrypt(cur["content"] or "")
        head = _doc_atrest_decrypt(br["head_content"] or "")
        merged, conflict = _three_way_merge(base, head, main_content)
        now = _utcnow_iso()
        new_version = cur["version"] + 1
        # 存合并前主干快照（沿用库内已存密文形态）
        await db.execute("INSERT INTO doc_versions (doc_id, version, title, content, created_at, created_by) VALUES (?,?,?,?,?,?)",
                          (doc_id, cur["version"], cur["title"], cur["content"], now, user_id))
        await _prune_doc_versions(db, doc_id)
        await db.execute("UPDATE documents SET content=?, updated_at=?, version=? WHERE doc_id=?",
                          (_doc_atrest_encrypt(merged), now, new_version, doc_id))
        new_status = "conflict" if conflict else "merged"
        await db.execute("UPDATE doc_branches SET status=?, merged_at=?, updated_at=? WHERE branch_id=?",
                          (new_status, now, now, bid))
    await _audit(user_id, None, "branch.merge", "doc", doc_id, f"bid={bid} conflict={conflict} ->v{new_version}")
    return {"merged": True, "conflict": conflict, "version": new_version, "status": new_status}


# ==================== 回收站 API ====================
@app.get("/api/trash")
async def list_trash(user_id: str = Depends(_require_user)):
    """列出当前用户回收站文档（已软删除）。"""
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT doc_id, title, path, kind, deleted_at, updated_at FROM documents WHERE deleted_at IS NOT NULL AND user_id=? ORDER BY deleted_at DESC",
            (user_id,)
        )).fetchall()
    return {"items": [
        {
            "doc_id": r["doc_id"],
            "title": r["title"],
            "path": r["path"] or "",
            "kind": r["kind"] or "file",
            "deleted_at": r["deleted_at"],
            "updated_at": r["updated_at"],
        } for r in rows
    ]}


async def _unique_title(db, user_id: str, path: str, title: str) -> str:
    """在 (user, path) 下寻找不与现存未删除文档重名的标题；重名则加 " (n)" 后缀。"""
    base = title
    candidate = base
    n = 1
    while True:
        dup = await (await db.execute(
            "SELECT 1 FROM documents WHERE user_id=? AND path=? AND title=? AND deleted_at IS NULL",
            (user_id, path, candidate),
        )).fetchone()
        if not dup:
            return candidate
        n += 1
        candidate = f"{base} ({n})"


@app.post("/api/trash/{doc_id}/restore")
async def restore_trash(doc_id: str, mode: str = "auto", title: Optional[str] = None,
                        user_id: str = Depends(_require_user)):
    """从回收站还原文档。

    - mode=auto（默认）：若还原后会与同目录下现存文档重名，返回 409 + 冲突信息（含建议的新标题），
      不静默还原出重名文档。调用方可据此提示用户选择"覆盖 / 重命名 / 取消"。
    - mode=overwrite：把同名现存文档软删除（移入回收站），再还原本文档。
    - mode=rename：用 title 作为还原后的新标题（调用方应使用 409 返回的 suggested_title 以避免再次冲突）。
    """
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        row = await (await db.execute(
            "SELECT path, title FROM documents WHERE doc_id=? AND deleted_at IS NOT NULL AND user_id=?",
            (doc_id, user_id),
        )).fetchone()
        if not row:
            raise HTTPException(404, "回收站中不存在该文档")
        path = row["path"] or ""
        orig_title = row["title"]
        # 目标标题：rename 模式优先用传入 title，否则用原标题
        desired = (title.strip() if (mode == "rename" and title and title.strip()) else orig_title)
        conflict_row = await (await db.execute(
            "SELECT doc_id FROM documents WHERE user_id=? AND path=? AND title=? AND deleted_at IS NULL AND doc_id<>?",
            (user_id, path, desired, doc_id),
        )).fetchone()
        if conflict_row and mode not in ("overwrite", "rename"):
            # auto 模式：不静默还原出重名，返回 409 + 建议名，交由前端提示
            suggested = await _unique_title(db, user_id, path, desired)
            raise HTTPException(409, detail={
                "message": "当前目录下已存在同名文档",
                "conflict": True,
                "existing_doc_id": conflict_row["doc_id"],
                "existing_title": desired,
                "suggested_title": suggested,
            })
        if conflict_row and mode == "overwrite":
            # 把同名现存文档软删除（移入回收站），再还原本文档
            await db.execute(
                "UPDATE documents SET deleted_at=?, updated_at=? WHERE doc_id=?",
                (now, now, conflict_row["doc_id"]),
            )
            new_title = desired
        elif mode == "rename":
            # rename 绝不制造重名：若目标名冲突则自动加后缀
            new_title = await _unique_title(db, user_id, path, desired) if conflict_row else desired
        else:
            new_title = desired
        await db.execute(
            "UPDATE documents SET deleted_at=NULL, title=?, updated_at=? WHERE doc_id=?",
            (new_title, now, doc_id),
        )
    logger.info("还原文档 doc_id=%s mode=%s title=%s", doc_id, mode, new_title)
    return {"restored": True, "title": new_title}


@app.delete("/api/trash/{doc_id}")
async def purge_trash(doc_id: str, user_id: str = Depends(_require_user)):
    """永久删除回收站中的文档。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT doc_id FROM documents WHERE doc_id = ? AND deleted_at IS NOT NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "回收站中不存在该文档")
        await db.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    logger.info("永久清空回收站文档 doc_id=%s", doc_id)
    return {"purged": True}


@app.delete("/api/trash")
async def empty_trash(user_id: str = Depends(_require_user)):
    """清空当前用户的回收站。"""
    async with _db_transaction(user_id) as db:
        cur = await db.execute("DELETE FROM documents WHERE deleted_at IS NOT NULL AND user_id=?", (user_id,))
        count = cur.rowcount
    logger.info("清空回收站共 %d 篇 user=%s", count, user_id)
    return {"purged": True, "count": count}


# ==================== 文档元信息（标签/收藏/最近打开/搜索）====================
class DocMetaRequest(BaseModel):
    tags: Optional[str] = None
    starred: Optional[bool] = None
    classification: Optional[str] = None  # public/internal/confidential


@app.put("/api/docs/{doc_id}/meta")
async def update_doc_meta(doc_id: str, req: DocMetaRequest, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT doc_id, share_code FROM documents WHERE doc_id = ? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        sets = []
        params = []
        if req.tags is not None:
            sets.append("tags=?")
            params.append(req.tags)
        if req.starred is not None:
            sets.append("starred=?")
            params.append(1 if req.starred else 0)
        if req.classification is not None:
            cls = req.classification if req.classification in ("public", "internal", "confidential") else "internal"
            # 机密文档若正在公开分享则禁止提升为机密（DLP）
            if cls == "confidential" and row["share_code"]:
                raise HTTPException(409, "文档正在公开分享，不能设为机密。请先取消分享。")
            sets.append("classification=?")
            params.append(cls)
        if not sets:
            return {"updated": False}
        params.append(doc_id)
        await db.execute(f"UPDATE documents SET {', '.join(sets)} WHERE doc_id=?", params)
    return {"updated": True}


@app.put("/api/teams/{tid}/docs/{doc_id}/meta")
async def update_team_doc_meta(tid: str, doc_id: str, req: DocMetaRequest, user_id: str = Depends(_require_user)):
    """更新团队文档元数据（tags/starred/classification，需 doc.edit 权限）。

    镜像个人 update_doc_meta。原先前端在团队空间收藏/打标仍走个人 /api/docs/{id}/meta
    → 文档不在个人库 → 404，故补团队版。收藏为团队级标记（团队内可见）。
    """
    await _require_team_permission(tid, user_id, "doc.edit")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute(
            "SELECT doc_id, share_code FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,),
        )).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        sets = []
        params = []
        if req.tags is not None:
            sets.append("tags=?")
            params.append(req.tags)
        if req.starred is not None:
            sets.append("starred=?")
            params.append(1 if req.starred else 0)
        if req.classification is not None:
            cls = req.classification if req.classification in ("public", "internal", "confidential") else "internal"
            if cls == "confidential" and row["share_code"]:
                raise HTTPException(409, "文档正在公开分享，不能设为机密。请先取消分享。")
            sets.append("classification=?")
            params.append(cls)
        if not sets:
            return {"updated": False}
        params.append(doc_id)
        await db.execute(f"UPDATE documents SET {', '.join(sets)} WHERE doc_id=?", params)
    action_bits = []
    if req.starred is not None:
        action_bits.append(f"star={'on' if req.starred else 'off'}")
    if req.tags is not None:
        action_bits.append("tags")
    if req.classification is not None:
        action_bits.append(f"class={req.classification}")
    await _audit(user_id, tid, "team doc meta: " + ",".join(action_bits), "doc", doc_id)
    return {"updated": True}


@app.post("/api/docs/{doc_id}/open")
async def mark_opened(doc_id: str, user_id: str = Depends(_require_user)):
    """标记文档为最近打开（更新 last_opened_at）。"""
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT doc_id FROM documents WHERE doc_id = ? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        await db.execute("UPDATE documents SET last_opened_at=? WHERE doc_id=?", (now, doc_id))
    return {"last_opened_at": now}



# ==================== 云端文件夹 API ====================
def _node_full_path(row) -> str:
    """节点（文件/文件夹）的完整路径 = 父 path + '/' + title，根则 = title。"""
    title = row["title"] or ""
    path = row["path"] or ""
    return f"{path}/{title}" if path else title


@app.post("/api/folders", status_code=201)
async def create_folder(req: FolderCreateRequest, user_id: str = Depends(_require_user)):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "文件夹名称不能为空")
    if "/" in name:
        raise HTTPException(400, "文件夹名称不能包含 /")
    doc_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    async with _db_transaction(user_id) as db:
        await db.execute(
            "INSERT INTO documents (doc_id, title, content, created_at, updated_at, kind, path, user_id) VALUES (?, ?, '', ?, ?, 'folder', ?, ?)",
            (doc_id, name, now, now, req.path or "", user_id),
        )
    logger.info("创建文件夹 doc_id=%s name=%s path=%s user=%s", doc_id, name, req.path, user_id)
    return {"doc_id": doc_id, "name": name, "path": req.path or ""}


@app.put("/api/folders/{doc_id}")
async def rename_folder(doc_id: str, req: FolderRenameRequest, user_id: str = Depends(_require_user)):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "文件夹名称不能为空")
    if "/" in name:
        raise HTTPException(400, "文件夹名称不能包含 /")
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id = ? AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文件夹不存在")
        if (row["kind"] or "file") != "folder":
            raise HTTPException(400, "目标不是文件夹")
        old_full = _node_full_path(row)               # 旧完整路径
        parent_path = row["path"] or ""
        new_full = f"{parent_path}/{name}" if parent_path else name  # 新完整路径
        # 重名检查：同一用户+父目录下不得有其他同名（未删除）节点
        if name != row["title"]:
            dup = await (await db.execute(
                "SELECT 1 FROM documents WHERE user_id=? AND path=? AND title=? AND doc_id<>? AND deleted_at IS NULL",
                (user_id, parent_path, name, doc_id),
            )).fetchone()
            if dup:
                raise HTTPException(409, "当前目录下已存在同名文件夹")
        # 重命名该文件夹行
        now = _utcnow_iso()
        await db.execute("UPDATE documents SET title=?, updated_at=? WHERE doc_id=?", (name, now, doc_id))
        # 级联：当前用户的所有后代（path == old_full 或 path LIKE 'old_full/%'）path 前缀替换为 new_full
        like = old_full + "/%"
        descendants = await (await db.execute(
            "SELECT doc_id, path FROM documents WHERE user_id=? AND (path = ? OR path LIKE ?)",
            (user_id, old_full, like),
        )).fetchall()
        for d in descendants:
            dp = d["path"] or ""
            new_dp = new_full if dp == old_full else new_full + dp[len(old_full):]
            await db.execute("UPDATE documents SET path=?, updated_at=? WHERE doc_id=?", (new_dp, now, d["doc_id"]))
    logger.info("重命名文件夹 doc_id=%s -> %s (old=%s new=%s)", doc_id, name, old_full, new_full)
    return {"doc_id": doc_id, "name": name, "path": parent_path}


@app.post("/api/folders/{doc_id}/move")
async def move_folder(doc_id: str, req: FolderMoveRequest, user_id: str = Depends(_require_user)):
    """移动文件夹到新父目录（parent_path），并级联更新所有后代 path 前缀。"""
    new_parent = (req.parent_path or "").strip()
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id = ? AND user_id=?", (doc_id, user_id))).fetchone()
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
        # 目标父目录下同名检查（文件/文件夹均不可冲突）
        dup = await (await db.execute(
            "SELECT 1 FROM documents WHERE user_id=? AND path=? AND title=? AND doc_id<>? AND deleted_at IS NULL",
            (user_id, new_parent, name, doc_id),
        )).fetchone()
        if dup:
            raise HTTPException(409, "目标目录下已存在同名节点")
        now = _utcnow_iso()
        # 更新本文件夹的父路径
        await db.execute("UPDATE documents SET path=?, updated_at=? WHERE doc_id=?", (new_parent, now, doc_id))
        # 级联：所有后代（path == old_full 或 LIKE 'old_full/%'）前缀替换为 new_full
        like = old_full + "/%"
        descendants = await (await db.execute(
            "SELECT doc_id, path FROM documents WHERE user_id=? AND (path = ? OR path LIKE ?)",
            (user_id, old_full, like),
        )).fetchall()
        for d in descendants:
            dp = d["path"] or ""
            new_dp = new_full if dp == old_full else new_full + dp[len(old_full):]
            await db.execute("UPDATE documents SET path=?, updated_at=? WHERE doc_id=?", (new_dp, now, d["doc_id"]))
    logger.info("移动文件夹 doc_id=%s -> parent=%s (old=%s new=%s)", doc_id, new_parent, old_full, new_full)
    return {"doc_id": doc_id, "path": new_parent}


@app.delete("/api/folders/{doc_id}")
async def delete_folder(doc_id: str, user_id: str = Depends(_require_user)):
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id = ? AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文件夹不存在")
        if (row["kind"] or "file") != "folder":
            raise HTTPException(400, "目标不是文件夹")
        old_full = _node_full_path(row)
        # 删除该文件夹 + 当前用户的所有后代（path == old_full 或 path LIKE 'old_full/%'）
        like = old_full + "/%"
        now = _utcnow_iso()
        # 含正在分享的文档则禁止删除：先取消分享
        shared = await (await db.execute(
            "SELECT title FROM documents WHERE user_id=? AND share_code IS NOT NULL AND deleted_at IS NULL AND (doc_id = ? OR path = ? OR path LIKE ?)",
            (user_id, doc_id, old_full, like),
        )).fetchall()
        if shared:
            names = "、".join(r["title"] for r in shared[:5])
            raise HTTPException(409, f"文件夹下有 {len(shared)} 篇文档正在分享（{names}），请先取消分享后再删除")
        # 软删除：整体移入回收站，与单文档删除一致，避免永久销毁
        cur = await db.execute(
            "UPDATE documents SET deleted_at=? WHERE user_id=? AND (doc_id = ? OR path = ? OR path LIKE ?)",
            (now, user_id, doc_id, old_full, like),
        )
        deleted = cur.rowcount
    logger.info("软删除文件夹 doc_id=%s full=%s 共移入回收站 %d 行", doc_id, old_full, deleted)
    return {"deleted": True, "count": deleted}


# ==================== 分享链接 API ====================
def _hash_share_password(pw: str) -> str:
    """分享密码哈希（sha256+盐），避免明文存储。"""
    if not pw:
        return ""
    return hashlib.sha256(f"md-share::{pw}".encode("utf-8")).hexdigest()


@app.post("/api/docs/{doc_id}/share")
async def create_share(doc_id: str, req: ShareCreateRequest, user_id: str = Depends(_require_user)):
    expires_days = min(req.expires_days, SHARE_MAX_AGE_DAYS)
    mode = req.mode if req.mode in ("readonly", "editable") else "readonly"
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id = ? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        # DLP：机密文档禁止公开分享
        classification = row["classification"] if "classification" in row.keys() else "internal"
        if classification == "confidential":
            raise HTTPException(403, "该文档为机密级别，禁止公开分享。请先降低数据分级后再分享。")
        if row["share_code"]:
            expires_at = row["share_expires_at"]
            if expires_at and expires_at > _utcnow_iso():
                return {
                    "share_code": row["share_code"],
                    "share_expires_at": expires_at,
                    "has_password": bool(row["share_password"]),
                    "max_views": row["share_max_views"],
                    "burn_after_read": bool(row["share_burn_after_read"]),
                    "mode": row["share_mode"] or "readonly",
                }
        code = _generate_share_code()
        from datetime import timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
        await db.execute(
            "UPDATE documents SET share_code=?, share_expires_at=?, share_password=?, share_max_views=?, share_burn_after_read=?, share_mode=?, share_views=0 WHERE doc_id=?",
            (code, expires_at, _hash_share_password(req.password or ""), req.max_views, 1 if req.burn_after_read else 0, mode, doc_id),
        )
    # 在共享注册库登记路由：share_code → 属主用户（供访客跨用户定位）
    async with _registry_transaction() as rdb:
        await rdb.execute(
            "INSERT OR REPLACE INTO shares (share_code, owner_user_id, doc_id, created_at) VALUES (?, ?, ?, ?)",
            (code, user_id, doc_id, _utcnow_iso()),
        )
    logger.info("创建分享 doc_id=%s code=%s mode=%s pwd=%s", doc_id, code, mode, bool(req.password))
    return {
        "share_code": code,
        "share_expires_at": expires_at,
        "has_password": bool(req.password),
        "max_views": req.max_views,
        "burn_after_read": req.burn_after_read,
        "mode": mode,
    }


def _share_info(row) -> dict:
    """由文档行构造分享信息（不含正文）。"""
    return {
        "doc_id": row["doc_id"],
        "title": row["title"],
        "path": row["path"] or "",
        "kind": row["kind"] or "file",
        "share_code": row["share_code"],
        "share_url": f"/s/{row['share_code']}",
        "share_expires_at": row["share_expires_at"],
        "has_password": bool(row["share_password"]),
        "max_views": row["share_max_views"],
        "views": row["share_views"],
        "burn_after_read": bool(row["share_burn_after_read"]),
        "mode": row["share_mode"] or "readonly",
        "updated_at": row["updated_at"],
    }


@app.get("/api/shares")
async def list_shared_docs(user_id: str = Depends(_require_user)):
    """列出当前用户正在分享的文档（含分享属性）。"""
    async with _db_transaction(user_id) as db:
        rows = await (await db.execute(
            "SELECT doc_id, title, path, kind, share_code, share_expires_at, share_password, share_max_views, share_views, share_burn_after_read, share_mode, updated_at "
            "FROM documents WHERE share_code IS NOT NULL AND deleted_at IS NULL AND user_id=? ORDER BY updated_at DESC",
            (user_id,),
        )).fetchall()
    return {"items": [_share_info(r) for r in rows]}


@app.put("/api/docs/{doc_id}/share")
async def update_share(doc_id: str, req: ShareUpdateRequest, user_id: str = Depends(_require_user)):
    """编辑已存在分享的属性（不重新生成 share_code）。仅更新显式传入字段。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        if not row["share_code"]:
            raise HTTPException(400, "该文档未分享，请先创建分享")
        expires_at = row["share_expires_at"]
        if req.expires_days is not None:
            expires_days = min(max(1, req.expires_days), SHARE_MAX_AGE_DAYS)
            from datetime import timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
        share_password = row["share_password"]
        if req.password is not None:
            share_password = _hash_share_password(req.password)  # "" -> 清除，非空 -> 新哈希
        max_views = req.max_views if req.max_views is not None else row["share_max_views"]
        burn = req.burn_after_read if req.burn_after_read is not None else bool(row["share_burn_after_read"])
        mode = (req.mode if req.mode in ("readonly", "editable") else None) or (row["share_mode"] or "readonly")
        await db.execute(
            "UPDATE documents SET share_expires_at=?, share_password=?, share_max_views=?, share_burn_after_read=?, share_mode=? WHERE doc_id=?",
            (expires_at, share_password, max_views, 1 if burn else 0, mode, doc_id),
        )
    logger.info("更新分享 doc_id=%s mode=%s pwd=%s", doc_id, mode, bool(share_password))
    return {
        "share_code": row["share_code"],
        "share_expires_at": expires_at,
        "has_password": bool(share_password),
        "max_views": max_views,
        "burn_after_read": burn,
        "mode": mode,
    }


@app.delete("/api/docs/{doc_id}/share")
async def cancel_share(doc_id: str, user_id: str = Depends(_require_user)):
    """取消分享：清空分享字段并移除注册库路由。"""
    async with _db_transaction(user_id) as db:
        row = await (await db.execute("SELECT share_code FROM documents WHERE doc_id=? AND deleted_at IS NULL AND user_id=?", (doc_id, user_id))).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        code = row["share_code"]
        if not code:
            return {"ok": True, "note": "该文档未分享"}
        await db.execute(
            "UPDATE documents SET share_code=NULL, share_expires_at=NULL, share_password=NULL, share_max_views=NULL, share_views=0, share_burn_after_read=0, share_mode='readonly' WHERE doc_id=?",
            (doc_id,),
        )
    await _drop_share_route(code)
    logger.info("取消分享 doc_id=%s code=%s", doc_id, code)
    return {"ok": True}


# ---------- 团队文档分享（团队库隔离，路由登记 team_id）----------
# 历史 bug：前端无视 activeTeamId 全部 POST /api/docs/{id}/share，而该端点只查属主个人库，
# 团队文档不在个人库 → 404。这里镜像个人端点，写入团队库并在 shares 注册 team_id 路由。

@app.post("/api/teams/{tid}/docs/{doc_id}/share")
async def create_team_share(tid: str, doc_id: str, req: ShareCreateRequest, user_id: str = Depends(_require_user)):
    """创建团队文档分享。需 doc.edit 权限（默认 member/admin/owner）。"""
    await _require_team_permission(tid, user_id, "doc.edit")
    expires_days = min(req.expires_days, SHARE_MAX_AGE_DAYS)
    mode = req.mode if req.mode in ("readonly", "editable") else "readonly"
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute(
            "SELECT * FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,)
        )).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        classification = row["classification"] if "classification" in row.keys() else "internal"
        if classification == "confidential":
            raise HTTPException(403, "该文档为机密级别，禁止公开分享。请先降低数据分级后再分享。")
        if row["share_code"]:
            expires_at = row["share_expires_at"]
            if expires_at and expires_at > _utcnow_iso():
                return {
                    "share_code": row["share_code"],
                    "share_expires_at": expires_at,
                    "has_password": bool(row["share_password"]),
                    "max_views": row["share_max_views"],
                    "burn_after_read": bool(row["share_burn_after_read"]),
                    "mode": row["share_mode"] or "readonly",
                }
        code = _generate_share_code()
        from datetime import timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
        await db.execute(
            "UPDATE documents SET share_code=?, share_expires_at=?, share_password=?, share_max_views=?, share_burn_after_read=?, share_mode=?, share_views=0 WHERE doc_id=?",
            (code, expires_at, _hash_share_password(req.password or ""), req.max_views, 1 if req.burn_after_read else 0, mode, doc_id),
        )
    # 注册库登记路由：team_id 非空 → 访问时开团队库
    async with _registry_transaction() as rdb:
        await rdb.execute(
            "INSERT OR REPLACE INTO shares (share_code, owner_user_id, team_id, doc_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (code, user_id, tid, doc_id, _utcnow_iso()),
        )
    await _audit(user_id, tid, "doc.share.create", "document", doc_id, f"mode={mode} code={code}")
    logger.info("创建团队分享 team=%s doc_id=%s code=%s mode=%s", tid, doc_id, code, mode)
    return {
        "share_code": code,
        "share_expires_at": expires_at,
        "has_password": bool(req.password),
        "max_views": req.max_views,
        "burn_after_read": req.burn_after_read,
        "mode": mode,
    }


@app.put("/api/teams/{tid}/docs/{doc_id}/share")
async def update_team_share(tid: str, doc_id: str, req: ShareUpdateRequest, user_id: str = Depends(_require_user)):
    """编辑团队文档分享属性。需 doc.edit 权限。"""
    await _require_team_permission(tid, user_id, "doc.edit")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute(
            "SELECT * FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,)
        )).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        if not row["share_code"]:
            raise HTTPException(400, "该文档未分享，请先创建分享")
        expires_at = row["share_expires_at"]
        if req.expires_days is not None:
            expires_days = min(max(1, req.expires_days), SHARE_MAX_AGE_DAYS)
            from datetime import timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
        share_password = row["share_password"]
        if req.password is not None:
            share_password = _hash_share_password(req.password)
        max_views = req.max_views if req.max_views is not None else row["share_max_views"]
        burn = req.burn_after_read if req.burn_after_read is not None else bool(row["share_burn_after_read"])
        mode = (req.mode if req.mode in ("readonly", "editable") else None) or (row["share_mode"] or "readonly")
        await db.execute(
            "UPDATE documents SET share_expires_at=?, share_password=?, share_max_views=?, share_burn_after_read=?, share_mode=? WHERE doc_id=?",
            (expires_at, share_password, max_views, 1 if burn else 0, mode, doc_id),
        )
    await _audit(user_id, tid, "doc.share.update", "document", doc_id, f"mode={mode}")
    logger.info("更新团队分享 team=%s doc_id=%s mode=%s", tid, doc_id, mode)
    return {
        "share_code": row["share_code"],
        "share_expires_at": expires_at,
        "has_password": bool(share_password),
        "max_views": max_views,
        "burn_after_read": burn,
        "mode": mode,
    }


@app.delete("/api/teams/{tid}/docs/{doc_id}/share")
async def cancel_team_share(tid: str, doc_id: str, user_id: str = Depends(_require_user)):
    """取消团队文档分享。需 doc.edit 权限。"""
    await _require_team_permission(tid, user_id, "doc.edit")
    async with _team_db_transaction(tid) as db:
        row = await (await db.execute(
            "SELECT share_code FROM documents WHERE doc_id=? AND deleted_at IS NULL", (doc_id,)
        )).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        code = row["share_code"]
        if not code:
            return {"ok": True, "note": "该文档未分享"}
        await db.execute(
            "UPDATE documents SET share_code=NULL, share_expires_at=NULL, share_password=NULL, share_max_views=NULL, share_views=0, share_burn_after_read=0, share_mode='readonly' WHERE doc_id=?",
            (doc_id,),
        )
    await _drop_share_route(code)
    await _audit(user_id, tid, "doc.share.cancel", "document", doc_id, f"code={code}")
    logger.info("取消团队分享 team=%s doc_id=%s code=%s", tid, doc_id, code)
    return {"ok": True}


@app.get("/api/teams/{tid}/shares")
async def list_team_shared_docs(tid: str, user_id: str = Depends(_require_user)):
    """列出团队中正在分享的文档。需 doc.read 权限（默认 viewer+）。"""
    await _require_team_permission(tid, user_id, "doc.read")
    async with _team_db_transaction(tid) as db:
        rows = await (await db.execute(
            "SELECT doc_id, title, path, kind, share_code, share_expires_at, share_password, share_max_views, share_views, share_burn_after_read, share_mode, updated_at "
            "FROM documents WHERE share_code IS NOT NULL AND deleted_at IS NULL ORDER BY updated_at DESC"
        )).fetchall()
    return {"items": [_share_info(r) for r in rows]}


async def _share_route(code: str):
    """通过共享注册库把分享码路由到 (owner_user_id, team_id)。
    team_id 非空 → 团队文档分享，需开团队库；否则 → 属主个人库。"""
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT owner_user_id, team_id FROM shares WHERE share_code=?", (code,)
        )).fetchone()
    if not row:
        return (None, None)
    return (row["owner_user_id"], row["team_id"])


async def _share_owner(code: str) -> str | None:
    """通过共享注册库把分享码路由到属主用户 user_id。"""
    owner, _ = await _share_route(code)
    return owner


def _share_db_ctx(owner_user_id, team_id):
    """根据分享路由返回对应的事务上下文：team_id 非空→团队库，否则属主个人库。"""
    if team_id:
        return _team_db_transaction(team_id)
    return _db_transaction(owner_user_id)


async def _drop_share_route(code: str):
    """从注册库移除分享码路由（阅后即焚/过期清理时调用）。"""
    async with _registry_transaction() as db:
        await db.execute("DELETE FROM shares WHERE share_code=?", (code,))


@app.get("/api/share/{code}")
async def get_shared_doc(code: str, password: Optional[str] = None):
    owner, team_id = await _share_route(code)
    if not owner and not team_id:
        raise HTTPException(404, "分享链接不存在或已过期")
    async with _share_db_ctx(owner, team_id) as db:
        row = await (await db.execute(
            "SELECT * FROM documents WHERE share_code = ? AND deleted_at IS NULL", (code,)
        )).fetchone()
        if not row:
            raise HTTPException(404, "分享链接不存在或已过期")
        if row["share_expires_at"] and row["share_expires_at"] < _utcnow_iso():
            raise HTTPException(410, "分享链接已过期")
        # 密码校验
        if row["share_password"]:
            if _hash_share_password(password or "") != row["share_password"]:
                raise HTTPException(401, "密码错误")
        # 访问次数限制
        max_views = row["share_max_views"]
        if max_views is not None and max_views > 0 and row["share_views"] >= max_views:
            raise HTTPException(410, "分享链接访问次数已达上限")
        # 阅后即焚：首次访问后立即删除分享码
        new_views = row["share_views"] + 1
        if row["share_burn_after_read"]:
            await db.execute(
                "UPDATE documents SET share_views=?, share_code=NULL, share_expires_at=NULL WHERE doc_id=?",
                (new_views, row["doc_id"]),
            )
        else:
            await db.execute("UPDATE documents SET share_views=? WHERE doc_id=?", (new_views, row["doc_id"]))
    # 通知属主：分享文档被访问（非首次也通知，便于感知）
    if owner:
        await _notify(owner, "share.access", detail=f"分享文档「{row['title']}」被访问（第 {new_views} 次）", link=f"/s/{code}")
    if row["share_burn_after_read"]:
        await _drop_share_route(code)
    return {
        "doc_id": row["doc_id"],
        "title": row["title"],
        "content": _doc_atrest_decrypt(row["content"]),
        "updated_at": row["updated_at"],
        "mode": row["share_mode"] or "readonly",
        "views": new_views,
        "max_views": max_views,
    }


@app.put("/api/share/{code}")
async def update_shared_doc(code: str, req: DocUpdateRequest):
    """可编辑分享模式下的内容回写。"""
    owner, team_id = await _share_route(code)
    if not owner and not team_id:
        raise HTTPException(404, "分享链接不存在或已过期")
    async with _share_db_ctx(owner, team_id) as db:
        row = await (await db.execute("SELECT * FROM documents WHERE share_code = ? AND deleted_at IS NULL", (code,))).fetchone()
        if not row:
            raise HTTPException(404, "分享链接不存在或已过期")
        if (row["share_mode"] or "readonly") != "editable":
            raise HTTPException(403, "该分享链接为只读模式")
        if row["share_expires_at"] and row["share_expires_at"] < _utcnow_iso():
            raise HTTPException(410, "分享链接已过期")
        # 正文：客户端传入为明文（落库前静态加密）；未传则沿用库内已存形态
        if req.content is not None:
            content = _doc_atrest_encrypt(req.content)
            plain_for_size = req.content
        else:
            content = row["content"]
            plain_for_size = _doc_atrest_decrypt(row["content"])
        title = req.title if req.title is not None else row["title"]
        if len(plain_for_size.encode("utf-8")) > DOC_MAX_CONTENT_BYTES:
            raise HTTPException(413, f"文档内容超过 {DOC_MAX_CONTENT_BYTES} 字节限制")
        now = _utcnow_iso()
        new_version = row["version"] + 1
        await db.execute("UPDATE documents SET title=?, content=?, updated_at=?, version=? WHERE doc_id=?", (title, content, now, new_version, row["doc_id"]))
    return {"version": new_version, "updated_at": now}


@app.get("/s/{code}")
async def share_page(code: str):
    # 仅校验存在性，密码/次数校验由 /api/share/{code} 负责，前端按需弹出密码框
    owner, team_id = await _share_route(code)
    if not owner and not team_id:
        raise HTTPException(404, "分享链接不存在或已过期")
    async with _share_db_ctx(owner, team_id) as db:
        row = await (await db.execute(
            "SELECT share_code, share_expires_at, share_password, share_mode, deleted_at FROM documents WHERE share_code = ?", (code,)
        )).fetchone()
    if not row or row["deleted_at"]:
        raise HTTPException(404, "分享链接不存在或已过期")
    if row["share_expires_at"] and row["share_expires_at"] < _utcnow_iso():
        raise HTTPException(410, "分享链接已过期")
    has_password = bool(row["share_password"])
    mode = row["share_mode"] or "readonly"
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>分享文档</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:860px;margin:0 auto;padding:24px 16px;color:#24292f;line-height:1.6}}
h1,h2,h3,h4,h5,h6{{margin-top:24px;margin-bottom:8px}}
pre{{background:#f6f8fa;padding:16px;border-radius:6px;overflow-x:auto}}
code{{background:#f6f8fa;padding:2px 6px;border-radius:3px;font-size:85%}}
pre code{{background:none;padding:0}}
blockquote{{border-left:4px solid #d0d7de;padding-left:16px;color:#656d76;margin:0}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d0d7de;padding:8px 12px}}tr:nth-child(even){{background:#f6f8fa}}
img{{max-width:100%}}a{{color:#0969da}}
.footer{{margin-top:40px;padding-top:16px;border-top:1px solid #d0d7de;color:#656d76;font-size:12px;text-align:center}}
.pw-box{{max-width:360px;margin:80px auto;text-align:center}}
.pw-box input{{width:100%;padding:10px 12px;border:1px solid #d0d7de;border-radius:6px;font-size:14px;box-sizing:border-box;margin-top:12px}}
.pw-box button{{width:100%;padding:10px 12px;background:#0969da;color:#fff;border:0;border-radius:6px;font-size:14px;cursor:pointer;margin-top:8px}}
.pw-box .err{{color:#cf222e;margin-top:8px;font-size:13px}}
.editor-bar{{margin-bottom:12px;padding:8px;background:#f6f8fa;border-radius:6px;display:flex;gap:8px;align-items:center}}
.editor-bar button{{padding:6px 12px;background:#0969da;color:#fff;border:0;border-radius:4px;cursor:pointer}}
.editor-bar .status{{color:#656d76;font-size:12px;margin-left:auto}}
#editor{{width:100%;height:300px;font-family:Consolas,monospace;border:1px solid #d0d7de;border-radius:6px;padding:8px;font-size:13px;box-sizing:border-box;display:none}}
</style>
</head><body>
<div id="pwGate" class="pw-box" style="display:none">
  <h3>🔒 该文档已加密</h3>
  <p>请输入访问密码</p>
  <input id="pwInput" type="password" placeholder="访问密码" autofocus>
  <button id="pwBtn">确认访问</button>
  <div id="pwErr" class="err"></div>
</div>
<div id="editorBar" class="editor-bar" style="display:none">
  <button id="btnSave">保存修改</button>
  <span class="status" id="saveStatus">未修改</span>
</div>
<textarea id="editor"></textarea>
<div id="content"></div>
<div class="footer">由 Markdown 编辑器分享</div>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
const CODE = "{code}";
const HAS_PASSWORD = {str(has_password).lower()};
const MODE = "{mode}";
const pwGate = document.getElementById('pwGate');
const pwInput = document.getElementById('pwInput');
const pwBtn = document.getElementById('pwBtn');
const pwErr = document.getElementById('pwErr');
const contentEl = document.getElementById('content');
const editorBar = document.getElementById('editorBar');
const editorEl = document.getElementById('editor');
const btnSave = document.getElementById('btnSave');
const saveStatus = document.getElementById('saveStatus');

function loadDoc(pw) {{
  const url = '/api/share/' + CODE + (pw ? ('?password=' + encodeURIComponent(pw)) : '');
  fetch(url).then(r => {{ if (r.status === 401) throw new Error('PASSWORD'); if (!r.ok) throw new Error('HTTP '+r.status); return r.json(); }})
    .then(d => {{
      pwGate.style.display = 'none';
      document.title = d.title || '分享文档';
      if (MODE === 'editable') {{
        editorBar.style.display = 'flex';
        editorEl.style.display = 'block';
        editorEl.value = d.content;
        contentEl.innerHTML = marked.parse(d.content);
        btnSave.onclick = () => {{
          fetch('/api/share/' + CODE, {{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{content:editorEl.value,title:d.title}})}})
            .then(r=>r.ok?r.json():Promise.reject(r)).then(()=>{{saveStatus.textContent='已保存 '+new Date().toLocaleTimeString();contentEl.innerHTML=marked.parse(editorEl.value);}}).catch(()=>{{saveStatus.textContent='保存失败';}});
        }};
        editorEl.addEventListener('input',()=>{{contentEl.innerHTML=marked.parse(editorEl.value);saveStatus.textContent='未保存';}});
      }} else {{
        contentEl.innerHTML = marked.parse(d.content);
      }}
    }})
    .catch(e => {{
      if (e.message === 'PASSWORD') {{
        pwGate.style.display = 'block';
        pwErr.textContent = '密码错误或未提供';
      }} else {{
        contentEl.innerHTML = '<p>加载失败：' + (e.message||'未知错误') + '</p>';
      }}
    }});
}}

if (HAS_PASSWORD) {{
  pwGate.style.display = 'block';
  pwBtn.onclick = () => loadDoc(pwInput.value);
  pwInput.addEventListener('keydown', e => {{ if (e.key === 'Enter') loadDoc(pwInput.value); }});
}} else {{
  loadDoc(null);
}}
</script></body></html>"""
    return HTMLResponse(content=html)


# ==================== PlantUML 本地渲染 ====================
class PlantumlRenderRequest(BaseModel):
    code: str
    format: str = "svg"


def _render_plantuml_local(code: str, fmt: str = "svg") -> Optional[bytes]:
    if not PLANTUML_LOCAL_ENABLED:
        return None
    import subprocess
    import tempfile
    try:
        cmd = PLANTUML_COMMAND.split() if PLANTUML_COMMAND else None
        if not cmd and PLANTUML_JAR_PATH:
            cmd = ["java", "-jar", PLANTUML_JAR_PATH, f"-t{fmt}", "-pipe", "-charset", "UTF-8"]
        elif not cmd:
            try:
                import plantuml
                return None
            except ImportError:
                return None
        if not cmd:
            return None
        result = subprocess.run(
            cmd,
            input=code.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        logger.warning("PlantUML 本地渲染失败: %s", result.stderr.decode("utf-8", errors="replace")[:200])
        return None
    except FileNotFoundError:
        logger.warning("PlantUML 命令未找到，请设置 PLANTUML_JAR_PATH 或 PLANTUML_COMMAND")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("PlantUML 本地渲染超时")
        return None
    except Exception as e:
        logger.error("PlantUML 本地渲染异常: %s", e)
        return None


@app.post("/api/plantuml/render")
async def render_plantuml_local(req: PlantumlRenderRequest):
    if not PLANTUML_LOCAL_ENABLED:
        raise HTTPException(403, "PlantUML 本地渲染已禁用")
    if len(req.code.encode("utf-8")) > 65536:
        raise HTTPException(413, "PlantUML 源码过大")
    svg_data = _render_plantuml_local(req.code, req.format)
    if svg_data is None:
        raise HTTPException(503, "PlantUML 本地渲染不可用，请配置 PLANTUML_JAR_PATH 或 PLANTUML_COMMAND")
    if req.format == "svg":
        svg_text = svg_data.decode("utf-8", errors="replace")
        return {"svg": svg_text}
    return Response(content=svg_data, media_type=f"image/{req.format}")
