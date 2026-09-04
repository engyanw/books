def _ypy_module():
    """惰性导入 y-py（Yjs 的 Python CRDT 绑定，PyPI 包名 y-py，导入名 y_py）。不可用时返回 None。
    服务端 CRDT 合并依赖此库；未安装时降级为客户端驱动快照（见 _collab_merge_loop）。"""
    # PyPI 包名 y-py，导入名 y_py；旧版 PyPI 曾有同名 stub 包 `ypy`（0.2 空 stub，无 YDoc），
    # 故优先 y_py，再回退 ypy 以防误装。
    for mod_name in ("y_py", "ypy"):
        try:
            mod = __import__(mod_name)
            if hasattr(mod, "YDoc") and hasattr(mod, "apply_update") and hasattr(mod, "encode_state_as_update"):
                return mod
        except Exception:
            continue
    return None


async def _collab_server_merge(room: str) -> dict:
    """服务端 CRDT 合并：用 ypy 把该 room 的最新快照 + 全部待 apply 增量合并为一份新快照，
    落库并清空增量。返回 {merged, snapshot_bytes, applied}。
    ypy 不可用时返回 {merged: False, reason: 'ypy_unavailable'}，调用方应回退请求客户端推快照。"""
    y = _ypy_module()
    if y is None:
        return {"merged": False, "reason": "ypy_unavailable"}
    import base64 as _b64
    snap_b64 = await _collab_load_state(room)
    updates = await _collab_load_updates(room)
    if not updates and not snap_b64:
        return {"merged": False, "reason": "empty"}
    try:
        ydoc = y.YDoc()
        if snap_b64:
            try:
                y.apply_update(ydoc, _b64.b64decode(snap_b64))
            except Exception:
                # 旧快照可能为非 Yjs 编码（裸字节 base64）；跳过基线，仅合并增量
                pass
        applied = 0
        for upd_bytes in updates:
            try:
                y.apply_update(ydoc, upd_bytes)
                applied += 1
            except Exception:
                continue
        new_state = y.encode_state_as_update(ydoc)
        new_b64 = _b64.b64encode(new_state).decode("ascii")
        await _collab_save_state(room, new_b64)
        await _collab_clear_updates(room)
        return {"merged": True, "snapshot_bytes": len(new_state), "applied": applied}
    except Exception as e:
        logger.warning("服务端 CRDT 合并失败 room=%s: %s", room, e)
        return {"merged": False, "reason": f"error: {e}"}


# ==================== 后台任务 leader 选举 ====================
_INSTANCE_ID = secrets.token_urlsafe(8)  # 本进程唯一标识


async def _renew_leader_lease() -> bool:
    """尝试获取/续租 leader 租约；返回本实例当前是否 leader。
    未启用 → 恒为 True（单实例向后兼容）。Redis 模式用 SET NX EX；SQLite 用注册库单行 CAS。"""
    if not LEADER_ELECTION_ENABLED:
        return True
    now = int(time.time())
    expires = now + LEADER_LEASE_TTL_SECONDS
    if REDIS_URL:
        r = await get_redis()
        if r is not None:
            try:
                cur = await r.get(LEADER_KEY)
                if cur is None or cur.decode() if isinstance(cur, (bytes, bytearray)) else cur == _INSTANCE_ID:
                    pass
                # 续租：仅当当前持有者是自己时
                if cur is not None and (cur.decode() if isinstance(cur, (bytes, bytearray)) else cur) == _INSTANCE_ID:
                    await r.set(LEADER_KEY, _INSTANCE_ID, ex=LEADER_LEASE_TTL_SECONDS)
                    return True
                # 抢占
                ok = await r.set(LEADER_KEY, _INSTANCE_ID, nx=True, ex=LEADER_LEASE_TTL_SECONDS)
                return bool(ok)
            except Exception as e:
                logger.warning("Redis leader 续租失败: %s", e)
                return False
        # Redis 配了但不可用 → 退化为 SQLite 租约
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT holder, expires_at FROM leader_lease WHERE id=1")).fetchone()
        now_iso = _utcnow_iso()
        if not row:
            await db.execute(
                "INSERT INTO leader_lease (id, holder, acquired_at, expires_at) VALUES (1, ?, ?, ?)",
                (_INSTANCE_ID, now_iso, str(expires)),
            )
            return True
        holder = row["holder"]
        try:
            exp = int(row["expires_at"])
        except (TypeError, ValueError):
            exp = 0
        if holder == _INSTANCE_ID or exp < now:
            await db.execute(
                "UPDATE leader_lease SET holder=?, acquired_at=?, expires_at=? WHERE id=1",
                (_INSTANCE_ID, now_iso, str(expires)),
            )
            return True
        return False


async def _am_leader() -> bool:
    """后台循环守卫：未启用选举 → True（向后兼容）；启用 → 续租并返回是否 leader。"""
    return await _renew_leader_lease()


async def _leader_loop():
    """心跳循环：周期性续租，保持 leader 身份（leader 才执行后台任务的副作用）。
    非常驻，仅当启用选举时由 startup 拉起。"""
    while True:
        try:
            await asyncio.sleep(LEADER_RENEW_INTERVAL_SECONDS)
            now_leader = await _renew_leader_lease()
            # 记录 leader 身份变迁（用于抖动告警）：从非主→主为一次抢主
            if now_leader and not _ops_state["leader_is_leader"]:
                _ops_state["leader_changes"] += 1
            _ops_state["leader_is_leader"] = 1 if now_leader else 0
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            logger.warning("leader 心跳异常: %s", e)


async def _collab_merge_loop():
    """后台合并/GC：对累积增量超阈值或快照过期的 room 做合并。
    ① ypy 可用 → 服务端 CRDT 合并：Y.applyUpdate(全部增量) → 落新快照 → 清增量（真正服务端收敛）。
    ② ypy 不可用 → 请求在线客户端推全量快照（落库后清增量），由客户端做 CRDT 合并。"""
    while True:
        try:
            await asyncio.sleep(60)
            if not await _am_leader():
                continue
            async with _registry_transaction() as db:
                rows = await (await db.execute(
                    "SELECT room, COUNT(*) AS c, MAX(ts) AS last FROM collab_updates GROUP BY room"
                )).fetchall()
            now = _utcnow_iso()
            for r in rows:
                need = False
                if r["c"] and r["c"] >= COLLAB_UPDATE_GC_THRESHOLD:
                    need = True
                # 简单时间比较：增量存在且快照较旧（用 ts 字符串比较）
                if not need and r["last"]:
                    snap = await _collab_load_state_row(r["room"])
                    if snap and snap["updated_at"] < r["last"]:
                        # 粗略老化判断：留待快照推进
                        pass
                if not need:
                    continue
                # ① 优先服务端 CRDT 合并（ypy 可用时：apply 全部增量→落新快照→清增量）
                merged = await _collab_server_merge(r["room"])
                if merged.get("merged"):
                    logger.info("服务端 CRDT 合并 room=%s applied=%d bytes=%d",
                                r["room"], merged.get("applied", 0), merged.get("snapshot_bytes", 0))
                    continue
                # ② ypy 不可用 → 回退：请在线客户端推全量快照（落库后清增量）
                conns = _collab_rooms.get(r["room"])
                if conns:
                    msg = json.dumps({"type": "request_snapshot", "room": r["room"]})
                    await _collab_broadcast_text(r["room"], msg)
                # 无连接时不安全清增量（可能丢失未合并的编辑），保留待下次重连 apply
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("协同合并循环异常: %s", e)


async def _collab_load_state_row(room: str):
    try:
        async with _registry_transaction() as db:
            return await (await db.execute("SELECT state, updated_at FROM collab_state WHERE room=?", (room,))).fetchone()
    except Exception:
        return None


async def _collab_local_dispatch(room: str, msg: dict):
    """跨实例入站分发：把其他实例广播来的消息发给本房间本进程内的全部连接。
    仅被 pubsub 消费路径调用（不含本实例自己发的，故无需排除发送者）。"""
    conns = _collab_rooms.get(room)
    if not conns:
        return
    mtype = msg.get("type")
    if mtype == "yjs_update":
        # 增量二进制：解码后发给本地连接
        try:
            data = base64.b64decode(msg.get("b64", ""))
        except Exception:
            return
        await _collab_broadcast_bytes(room, data)
        return
    if mtype == "yjs_snapshot":
        # 全量快照：以文本形式发给本地连接（客户端合并，CRDT 幂等）
        await _collab_broadcast_text(room, json.dumps(msg, default=str))
        return
    # presence/cursor 等
    await _collab_broadcast_text(room, json.dumps(msg, default=str))


@app.websocket("/ws/collab/{room}")
async def collab_ws(ws: WebSocket, room: str):
    """协同编辑 WebSocket：同 room 广播 + 在线状态 + 光标。
    presence/cursor 走 PresenceBus（Redis 模式下跨实例共享）；Yjs 二进制走本地广播。"""
    token = ws.query_params.get("token", "")
    uid = None
    uname = ""
    payload = _parse_token(token)
    if payload and payload.get("uid"):
        uid = payload["uid"]
        uname = payload.get("uname", "")
    else:
        uid = await _api_token_user(token)
    if not uid:
        await ws.close(code=4001)
        return
    if not uname:
        async with _registry_transaction() as db:
            u = await (await db.execute("SELECT username FROM users WHERE user_id=?", (uid,))).fetchone()
            uname = u["username"] if u else uid[:8]
    await ws.accept()
    conns = _collab_rooms.setdefault(room, set())
    conns.add(ws)
    presence = _collab_presence.setdefault(room, {})
    presence[uid] = uname
    # P2-12 大团队 awareness 上限：presence 超 cap 时淘汰最久未活跃，防广播风暴
    if COLLAB_MAX_PRESENCE_PER_ROOM > 0 and len(presence) > COLLAB_MAX_PRESENCE_PER_ROOM:
        oldest = next(iter(presence))
        presence.pop(oldest, None)
    # 注册房间本地分发器（幂等；仅 Redis 模式下被 pubsub 路径调用）
    presence_bus.register_room(room, _collab_local_dispatch)
    # 连接建立后下发已持久化的 Yjs 快照（若有）→ 新客户端可恢复历史编辑态
    snap = await _collab_load_state(room)
    if snap:
        await ws.send_text(json.dumps({"type": "yjs_snapshot", "b64": snap, "room": room}))
    # 下发快照之后待 apply 的增量更新（按 seq 升序，客户端 CRDT 合并）
    for upd in await _collab_load_updates(room):
        try:
            await ws.send_bytes(upd)
        except Exception:
            pass
    # 广播 join：本地（排除自己）+ 跨实例（Redis）
    join_msg = json.dumps({"type": "presence", "user": uname, "action": "join", "uid": uid, "room": room})
    await _collab_broadcast_text(room, join_msg, exclude=ws)
    await presence_bus.publish(room, {"type": "presence", "user": uname, "action": "join", "uid": uid, "room": room})
    logger.info("协同 WebSocket 连接 room=%s uid=%s (当前 %d 连接)", uid, uid, len(conns))
    try:
        while True:
            data = await ws.receive()
            if data.get("type") == "websocket.disconnect":
                break
            msg = data.get("bytes") or data.get("text")
            if msg is None:
                continue
            # 文本 JSON 消息：presence/cursor/yjs_snapshot
            if isinstance(msg, str) and msg.startswith("{"):
                try:
                    obj = json.loads(msg)
                    otype = obj.get("type")
                    if otype == "cursor":
                        # P2-12 awareness 负载上限：超限丢弃，防异常大 payload
                        if COLLAB_MAX_AWARENESS_BYTES > 0 and len(msg) > COLLAB_MAX_AWARENESS_BYTES:
                            logger.warning("awareness 负载超限丢弃 room=%s size=%d", room, len(msg))
                            continue
                        obj["room"] = room
                        await _collab_broadcast_text(room, json.dumps(obj), exclude=ws)
                        await presence_bus.publish(room, obj)
                        continue
                    if otype == "yjs_snapshot":
                        # 客户端提交全量快照 → 持久化 + 广播给本房间他人 + 跨实例
                        # 全量快照已包含全部状态，清空该 room 的增量
                        b64 = obj.get("b64", "")
                        obj["room"] = room
                        saved = await _collab_save_state(room, b64)
                        if not saved:
                            # P2-12 快照超限：回执错误，不广播
                            await ws.send_text(json.dumps({"type": "yjs_snapshot_rejected", "reason": "oversize", "room": room}))
                            continue
                        await _collab_clear_updates(room)
                        await _collab_broadcast_text(room, json.dumps(obj, default=str), exclude=ws)
                        await presence_bus.publish(room, obj)
                        continue
                except Exception:
                    pass
            # Yjs 二进制增量更新：本地广播（排除自己）+ 跨实例（base64 经 Redis pub/sub）+ 落库
            if isinstance(msg, bytes):
                with span("collab.yjs_update", room=room, bytes=len(msg)):
                    await _collab_broadcast_bytes(room, msg, exclude=ws)
                    await presence_bus.publish(room, {"type": "yjs_update", "b64": base64.b64encode(msg).decode("ascii"), "room": room})
                    await _collab_append_update(room, msg)
            else:
                # 其余纯文本（非 JSON）消息：本地广播
                await _collab_broadcast_text(room, msg, exclude=ws)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("协同 WebSocket 异常 room=%s: %s", room, e)
    finally:
        conns.discard(ws)
        presence.pop(uid, None)
        # 广播 leave：本地 + 跨实例
        leave_msg = json.dumps({"type": "presence", "user": uname, "action": "leave", "uid": uid, "room": room})
        await _collab_broadcast_text(room, leave_msg)
        await presence_bus.publish(room, {"type": "presence", "user": uname, "action": "leave", "uid": uid, "room": room})
        if not conns:
            _collab_rooms.pop(room, None)
            _collab_presence.pop(room, None)
            await presence_bus.unregister_room(room)
        logger.info("协同 WebSocket 断开 room=%s uid=%s", room, uid)


# ==================== 速率限制 ====================
# 多实例部署下走 Redis 共享计数（taskqueue.allow_rate），单实例回退进程内。
# 按端点限流配置：{路径: {window秒, max次数}}
_endpoint_limits = {
    "/api/ai/chat": {"window": 60, "max": 10},
    "/api/upload": {"window": 3600, "max": 100},
    "/api/docs/bulk-import": {"window": 86400, "max": 1},
}


_rate_warn_throttle = 0.0  # 上次告警的单调时间，用于节流避免日志洪泛


async def _check_rate_limit(client_ip: str) -> bool:
    if not RATE_LIMIT_ENABLED:
        return True
    # D5：多实例 + 无 Redis 时显式告警并退化（不静默放大为 N×实例的限额）
    if REDIS_REQUIRED and not REDIS_URL:
        _warn_redis_required_rate_limit()
    return await allow_rate(f"ip:{client_ip}", RATE_LIMIT_PER_MINUTE, 60)


async def _check_endpoint_rate_limit(key: str, path: str) -> bool:
    """按端点+用户/IP 的细粒度限流（Redis 共享）。"""
    cfg = _endpoint_limits.get(path)
    if not cfg:
        return True
    if REDIS_REQUIRED and not REDIS_URL:
        _warn_redis_required_rate_limit()
    return await allow_rate(f"{path}:{key}", cfg["max"], cfg["window"])


def _warn_redis_required_rate_limit():
    """REDIS_REQUIRED=1 但未配 Redis 时，限流退化为进程内——节流告警一次/30s。"""
    import time as _time
    now = _time.monotonic()
    global _rate_warn_throttle
    if now - _rate_warn_throttle > 30:
        _rate_warn_throttle = now
        logger.warning(
            "REDIS_REQUIRED=1 但未配 REDIS_URL：限流退化为进程内计数，"
            "多实例下实际限额为 单实例限额×实例数，请配置 REDIS_URL 以恢复共享计数"
        )


# ==================== 生命周期事件 ====================
@app.on_event("startup")
async def _startup():
    """启动时初始化数据库（PG 或 SQLite）；按需迁移；启动定时调度。"""
    from pg_adapter import init_pg_pool, is_pg
    if is_pg() or (DATABASE_URL and _asyncpg_available):
        await init_pg_pool()
        await _init_pg_schema()  # PG 单库承载全部表（registry + documents + ai_configs）
        logger.info("数据库初始化完成（PostgreSQL 共享池 + 统一 schema）")
    else:
        reg = await _init_registry_db()
        await reg.close()
        await _migrate_legacy_db()
        logger.info("数据库初始化完成（共享注册库 + 每用户文档库）")
    # P1-3：多实例一致性约束告警
    _mi = _storage_mode_info()
    if _mi["unsafe"]:
        msg = ("多实例不一致风险：LEADER_ELECTION/MULTI_INSTANCE_HA 已开但 SQLite per-user 模式且"
               " data 目录非共享 FS → 请求路径写不协调，同一用户 docs.db 可能并发损坏。"
               "建议切 PG（DATABASE_URL）或设 DOC_DATA_DIR_SHARED=true。")
        if MULTI_INSTANCE_STRICT:
            raise RuntimeError(msg)
        logger.warning("[多实例告警] %s", msg)
    elif _mi["backend"] == "sqlite_per_user" and _mi["multi_instance"]:
        logger.info("多实例模式：SQLite + 共享 FS 降级（非并发安全，建议 PG）")
    else:
        logger.info("存储模式：%s，多实例=%s", _mi["backend"], _mi["multi_instance"])
    # 启动定时发布后台调度（每 60s 检查到期文档）
    _bg_tasks.append(asyncio.create_task(_scheduled_publish_loop()))
    await _load_revoked_tokens()  # 加载已吊销 token 名单（SLO/登出）
    await _audit_retention_cleanup()  # 按留存策略清理过期审计
    # 任务队列与协同共享状态（Redis 模式才真正分布式；否则进程内 no-op）
    register_task("send_email", _send_email)
    _bg_tasks.append(asyncio.create_task(worker_loop()))
    await presence_bus.ensure_subscriber()
    logger.info("任务队列已就绪（%s）", "Redis 分布式" if REDIS_URL else "进程内")
    # 定时备份 + 恢复演练（BACKUP_INTERVAL_HOURS>0 启用；默认关闭，避免单测/开发侧副作用）
    if BACKUP_INTERVAL_HOURS > 0:
        _bg_tasks.append(asyncio.create_task(_backup_loop()))
        logger.info("定时备份已启用：每 %.1f 小时，保留 %d 份，目录 %s", BACKUP_INTERVAL_HOURS, BACKUP_KEEP, BACKUP_DIR)
    if BACKUP_DRILL_INTERVAL_HOURS > 0:
        _bg_tasks.append(asyncio.create_task(_backup_drill_loop()))
        logger.info("定时恢复演练已启用：每 %.1f 小时", BACKUP_DRILL_INTERVAL_HOURS)
    # E5：断链检测后台扫描（LINK_CHECK_INTERVAL_HOURS>0 启用，默认关闭）
    if LINK_CHECK_INTERVAL_HOURS > 0:
        _bg_tasks.append(asyncio.create_task(_link_check_loop()))
        logger.info("断链检查已启用：每 %.1f 小时", LINK_CHECK_INTERVAL_HOURS)
    # 工作流 SLA 超时扫描（每 60s 检查到期阶段 → 提醒/升级）
    _bg_tasks.append(asyncio.create_task(_workflow_sla_loop()))
    logger.info("工作流 SLA 扫描已启用")
    # 协同增量合并/GC 循环（请求客户端推全量快照以清增量）
    _bg_tasks.append(asyncio.create_task(_collab_merge_loop()))
    # leader 选举心跳（仅启用时实际选主；未启用 _am_leader 恒 True）
    if LEADER_ELECTION_ENABLED:
        _bg_tasks.append(asyncio.create_task(_leader_loop()))
        logger.info("后台任务 leader 选举已启用（instance=%s，TTL=%ds）", _INSTANCE_ID, LEADER_LEASE_TTL_SECONDS)
    # 未读通知邮件摘要循环（EMAIL_DIGEST_ENABLED=1 且 SMTP 已配置时实际投递）
    if EMAIL_DIGEST_ENABLED:
        _bg_tasks.append(asyncio.create_task(_digest_loop()))
        logger.info("通知摘要邮件已启用：每 %d 秒扫描", EMAIL_DIGEST_INTERVAL_SECONDS)


async def _workflow_sla_scan_once():
    """单次扫描：检查运行中工作流的当前阶段是否超时，超时则提醒/升级。供 loop 与测试调用。"""
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        insts = await (await db.execute(
            "SELECT wi.id AS inst_id, wi.review_id, wi.workflow_def_id, wi.team_id, wd.definition_json "
            "FROM workflow_instances wi JOIN workflow_definitions wd ON wi.workflow_def_id=wd.id "
            "WHERE wi.status='running'"
        )).fetchall()
        escalated = 0
        for inst in insts:
            rid = inst["review_id"]
            cur = await (await db.execute(
                "SELECT MIN(stage) AS s FROM review_steps WHERE review_id=? AND status='pending'", (rid,)
            )).fetchone()
            stage = cur["s"] if cur and cur["s"] is not None else None
            if stage is None:
                continue
            sla_row = await (await db.execute(
                "SELECT deadline, escalated FROM workflow_sla WHERE instance_id=? AND stage=?", (inst["inst_id"], stage)
            )).fetchone()
            if not sla_row or sla_row["escalated"]:
                continue
            if sla_row["deadline"] > now:
                continue  # 未到期
            try:
                definition = json.loads(inst["definition_json"])
                stage_def = definition.get("steps", [{}])[stage] if stage < len(definition.get("steps", [])) else {}
            except Exception:
                stage_def = {}
            requester_row = await (await db.execute("SELECT requester_user_id FROM reviews WHERE id=?", (rid,))).fetchone()
            requester = requester_row["requester_user_id"] if requester_row else None
            pending = await (await db.execute(
                "SELECT DISTINCT reviewer_user_id FROM review_steps WHERE review_id=? AND status='pending'", (rid,)
            )).fetchall()
            for p in pending:
                await _notify(p["reviewer_user_id"], "review.sla.remind",
                              detail=f"评审超时提醒（阶段 {stage + 1}），请尽快处理", link=f"/?review={rid}")
            if requester:
                await _notify(requester, "review.sla.escalated",
                              detail=f"文档评审阶段 {stage + 1} 已超时并升级", link=f"/?review={rid}")
            esc_name = stage_def.get("escalate_to")
            if esc_name:
                esc_user = await (await db.execute("SELECT user_id FROM users WHERE username=?", (esc_name,))).fetchone()
                if esc_user:
                    exists = await (await db.execute(
                        "SELECT 1 FROM review_steps WHERE review_id=? AND reviewer_user_id=? AND status='pending'",
                        (rid, esc_user["user_id"])
                    )).fetchone()
                    if not exists:
                        await db.execute(
                            "INSERT INTO review_steps (review_id, step, reviewer_user_id, status, mode, stage) "
                            "VALUES (?,?,?, 'pending', 'parallel', ?)",
                            (rid, stage + 1, esc_user["user_id"], stage),
                        )
                        await _notify(esc_user["user_id"], "review.sla.escalated",
                                      detail=f"评审已升级给你（阶段 {stage + 1}）", link=f"/?review={rid}")
            await db.execute("UPDATE workflow_sla SET escalated=1, escalated_at=? WHERE instance_id=? AND stage=?",
                             (now, inst["inst_id"], stage))
            await _audit(requester or "system", inst["team_id"], "workflow.sla.escalate", "workflow", inst["inst_id"],
                         f"stage={stage}")
            escalated += 1
        return escalated


async def _workflow_sla_loop():
    """工作流 SLA 超时扫描循环（每 60s）。仅 leader 执行扫描（多实例去重）。"""
    while True:
        try:
            await asyncio.sleep(60)
            if not await _am_leader():
                continue
            await _workflow_sla_scan_once()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("工作流 SLA 扫描异常: %s", e)


async def _backup_loop():
    """内置定时备份：周期性打包 DOC_DATA_DIR 并按 BACKUP_KEEP 轮转。
    多实例部署下应仅一个实例启用（用 BACKUP_INTERVAL_HOURS 控制），避免重复备份。"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from backup import create_backup, drill as _drill
    while True:
        try:
            await asyncio.sleep(int(BACKUP_INTERVAL_HOURS * 3600))
            if not await _am_leader():
                continue
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, create_backup, str(_data_dir()), BACKUP_DIR, BACKUP_KEEP)
            _ops_state["backup_last_success"] = time.time()
            logger.info("定时备份完成")
        except asyncio.CancelledError:
            break
        except Exception as e:
            _ops_state["backup_last_failure"] = time.time()
            _ops_state["backup_failures"] += 1
            logger.warning("定时备份失败: %s", e)


async def _backup_drill_loop():
    """内置定时恢复演练：校验最新备份的完整性与可恢复性（不覆盖运行数据）。"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from backup import drill
    while True:
        try:
            await asyncio.sleep(int(BACKUP_DRILL_INTERVAL_HOURS * 3600))
            if not await _am_leader():
                continue
            loop = asyncio.get_event_loop()
            rep = await loop.run_in_executor(None, drill, BACKUP_DIR, str(_data_dir()))
            if rep.get("ok"):
                logger.info("恢复演练通过: 恢复 %d 文件（期望 %d）", rep.get("restored_files"), rep.get("expected_files"))
            else:
                logger.error("恢复演练失败: %s", rep)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("恢复演练异常: %s", e)


async def _scheduled_publish_loop():
    """后台定时任务：每 60s 遍历所有用户库，检查到期的定时发布。"""
    while True:
        try:
            await asyncio.sleep(60)
            if not await _am_leader():
                continue
            now = _utcnow_iso()
            users_dir = _data_dir() / "users"
            if users_dir.exists():
                for udb_path in users_dir.glob("*/docs.db"):
                    try:
                        uid = udb_path.parent.name
                        async with _db_transaction(uid) as db:
                            try:
                                rows = await (await db.execute(
                                    "SELECT doc_id FROM documents WHERE deleted_at IS NULL AND user_id=? "
                                    "AND scheduled_publish_at IS NOT NULL AND scheduled_publish_at <= ? AND status='approved'",
                                    (uid, now),
                                )).fetchall()
                                for r in rows:
                                    await db.execute("UPDATE documents SET status='published', scheduled_publish_at=NULL WHERE doc_id=?", (r["doc_id"],))
                                    await _audit(uid, None, "doc.scheduled_publish", "doc", r["doc_id"], None)
                            except sqlite3.OperationalError:
                                pass  # 列不存在（旧库）
                    except Exception:
                        pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("定时发布调度异常: %s", e)

@app.on_event("shutdown")
async def _shutdown():
    """优雅关闭：先 cancel 并等待后台任务 drain，再关闭所有连接池。"""
    # 1) 取消所有后台任务并等待其退出（各自循环捕获 CancelledError 后 break）
    for t in _bg_tasks:
        t.cancel()
    if _bg_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*_bg_tasks, return_exceptions=True),
                timeout=20,
            )
        except asyncio.TimeoutError:
            logger.warning("部分后台任务 20s 内未退出，强制继续关闭")
        _bg_tasks.clear()
    # 2) 关闭连接池（PG 或 SQLite）
    from pg_adapter import close_pg_pool, is_pg
    if is_pg():
        await close_pg_pool()
        logger.info("PostgreSQL 连接池已关闭")
        return
    while _registry_pool:
        db = _registry_pool.pop()
        await db.close()
    for pool in _user_db_pools.values():
        while pool:
            db = pool.pop()
            await db.close()
    for pool in _team_db_pools.values():
        while pool:
            db = pool.pop()
            await db.close()
    await close_redis()
    logger.info("数据库连接池已关闭（含团队库）")


# ==================== 鉴权中间件 ====================
def _client_ip(request: Request) -> str:
    """取真实客户端 IP（信任首段 X-Forwarded-For；否则取连接对端）。"""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ip_in_list(ip: str, cidrs: list) -> bool:
    """判断 ip 是否命中 CIDR/IP 列表。非法 ip 视为不命中。"""
    import ipaddress as _ipa
    try:
        addr = _ipa.ip_address(ip)
    except ValueError:
        return False
    for c in cidrs:
        try:
            if "/" in c:
                if addr in _ipa.ip_network(c, strict=False):
                    return True
            elif _ipa.ip_address(c) == addr:
                return True
        except ValueError:
            continue
    return False


def _ip_filter_response(request: Request) -> "Response | None":
    """应用层 IP 白/黑名单。命中黑名单→403；白名单非空且未命中→403。健康探针豁免。返回 None 表示放行。"""
    if request.url.path in IP_FILTER_EXEMPT_PATHS:
        return None
    if not IP_ALLOWLIST and not IP_BLOCKLIST:
        return None
    ip = _client_ip(request)
    if IP_BLOCKLIST and _ip_in_list(ip, IP_BLOCKLIST):
        return Response(status_code=403, content=f"来源 IP 被禁止访问：{ip}")
    if IP_ALLOWLIST and not _ip_in_list(ip, IP_ALLOWLIST):
        return Response(status_code=403, content=f"来源 IP 不在白名单：{ip}")
    return None


@app.middleware("http")
async def auth_and_rate_limit(request: Request, call_next):
    # 应用层 IP 白/黑名单（先于鉴权/限流）
    blocked = _ip_filter_response(request)
    if blocked is not None:
        return blocked
    if API_TOKEN and request.url.path.startswith("/api/") and not request.url.path.startswith("/api/scim/v2/"):
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token != API_TOKEN:
            return Response(status_code=401, content="未授权访问")

    if request.url.path in ("/api/run", "/api/proxy-image", "/api/plantuml"):
        client_ip = request.client.host if request.client else "unknown"
        if not await _check_rate_limit(client_ip):
            return Response(status_code=429, content="请求过于频繁，请稍后再试")

    # RED 指标采集：Rate/Errors/Duration（不含 /metrics /health 自身，避免自激放大）
    _skip = request.url.path in ("/metrics", "/health", "/ready", "/api/admin/metrics")
    t0 = time.time()
    try:
        response = await call_next(request)
    except Exception:
        if not _skip:
            observe_request(request.method, request.url.path, 500, time.time() - t0)
        raise
    if not _skip:
        observe_request(request.method, request.url.path, response.status_code, time.time() - t0)
    return response


# ==================== 多用户鉴权 ====================
class AuthRequest(BaseModel):
    username: str = ""
    password: str = ""


def _hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 存储。格式：pbkdf2$iters$salt_b64$hash_b64"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return f"pbkdf2$200000${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False


def _issue_access_token(user_id: str, username: str) -> str:
    """签发 access token（短 TTL）。_require_user 仅接受 typ=access 的 token。"""
    now = int(time.time())
    payload = {"uid": user_id, "uname": username, "iat": now, "exp": now + AUTH_ACCESS_TTL,
               "jti": secrets.token_hex(8), "typ": "access"}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{body}.{sig}"


# 向后兼容别名：旧调用点签发的即 access token
def _issue_token(user_id: str, username: str) -> str:
    return _issue_access_token(user_id, username)


async def _issue_refresh_token(user_id: str, username: str, *, request: "Request | None" = None) -> str:
    """签发 refresh token（长 TTL，落表存哈希），仅 /api/auth/refresh 接受。"""
    now = int(time.time())
    rid = secrets.token_urlsafe(16)
    payload = {"uid": user_id, "uname": username, "iat": now, "exp": now + AUTH_REFRESH_TTL,
               "jti": rid, "typ": "refresh"}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    token = f"{body}.{sig}"
    th = _token_revocation_key(token)
    issued_iso = _utcnow_iso()
    exp_iso = datetime.fromtimestamp(now + AUTH_REFRESH_TTL, timezone.utc).isoformat()
    try:
        async with _registry_transaction() as db:
            await db.execute(
                "INSERT OR REPLACE INTO refresh_tokens (id, user_id, token_hash, issued_at, expires_at, revoked_at, rotated_from) "
                "VALUES (?,?,?,?,?,NULL,?)",
                (rid, user_id, th, issued_iso, exp_iso, None),
            )
    except Exception as e:
        logger.warning("持久化 refresh token 失败: %s", e)
    return token


async def _is_refresh_token_valid(token: str) -> tuple[bool, str | None]:
    """校验 refresh token：签名+未过期+未被吊销。返回 (ok, user_id)。"""
    payload = _parse_token(token)
    if not payload or payload.get("typ") != "refresh":
        return (False, None)
    th = _token_revocation_key(token)
    try:
        async with _registry_transaction() as db:
            row = await (await db.execute(
                "SELECT user_id, revoked_at FROM refresh_tokens WHERE token_hash=?", (th,)
            )).fetchone()
    except Exception:
        return (False, None)
    if not row or row["revoked_at"]:
        return (False, None)
    return (True, row["user_id"])


async def _revoke_refresh_token(token: str, uid: str):
    """吊销 refresh token（标记 revoked_at），可选写入 Redis 共享名单。"""
    th = _token_revocation_key(token)
    try:
        async with _registry_transaction() as db:
            await db.execute("UPDATE refresh_tokens SET revoked_at=? WHERE token_hash=?", (_utcnow_iso(), th))
    except Exception:
        pass
    try:
        r = await get_redis()
        if r is not None:
            await r.sadd("mde:revoked_refresh", th)
    except Exception:
        pass


def _parse_token(token: str) -> dict | None:
    if not token or "." not in token:
        return None
    body, sig = token.split(".", 1)
    expected = base64.urlsafe_b64encode(hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < int(time.time()):
        return None
    return payload


def _hash_api_token(tok: str) -> str:
    """API token 哈希（sha256+固定盐），仅存哈希。"""
    return hashlib.sha256(f"md-api-token::{tok}".encode("utf-8")).hexdigest()


# ==================== TOTP 2FA（stdlib 实现，RFC 6238）====================
import struct as _struct
import base64 as _b64mod


def _totp_generate_secret() -> str:
    """生成 20 字节随机密钥（base32 编码）。"""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def _totp_code(secret_b32: str, timestamp: int = None) -> str:
    """计算 TOTP 6 位码。"""
    if timestamp is None:
        timestamp = int(time.time())
    counter = timestamp // 30
    key = base64.b32decode(secret_b32)
    msg = _struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0f
    code = _struct.unpack(">I", h[offset:offset+4])[0] & 0x7fffffff
    return str(code % 1000000).zfill(6)


def _totp_verify(secret_b32: str, code: str, window: int = 1) -> bool:
    """验证 TOTP 码（允许 ±window 个 30s 时间窗偏移）。"""
    if not secret_b32 or not code:
        return False
    now = int(time.time())
    for delta in range(-window, window + 1):
        if hmac.compare_digest(_totp_code(secret_b32, now + delta * 30), str(code).strip()):
            return True
    return False


def _totp_uri(secret_b32: str, username: str) -> str:
    """生成 otpauth:// URI（供前端渲染二维码）。"""
    from urllib.parse import quote
    issuer = "MarkdownEditor"
    return f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret_b32}&issuer={quote(issuer)}&digits=6&period=30"


async def _api_token_user(token: str) -> str | None:
    """按 API token 哈希查 user_id；命中则更新 last_used。"""
    if not token:
        return None
    h = _hash_api_token(token)
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT id, user_id FROM api_tokens WHERE token_hash=?", (h,))).fetchone()
        if not row:
            return None
        await db.execute("UPDATE api_tokens SET last_used=? WHERE id=?", (_utcnow_iso(), row["id"]))
    return row["user_id"]


async def _require_user(request: Request) -> str:
    """依赖项：校验 Bearer token（HMAC 会话 token 或 API token），返回 user_id，否则 401。"""
    with span("auth.require_user"):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
        # 优先 HMAC 会话 token
        payload = _parse_token(token)
        if payload and payload.get("uid"):
            # refresh token 不得用于普通 API 访问（仅 /api/auth/refresh 接受）
            if payload.get("typ") == "refresh":
                raise HTTPException(status_code=401, detail="无效的访问凭证（请使用 access token）")
            uid = payload["uid"]
            # 吊销检查（SLO/登出后立即失效）
            if await _is_token_revoked(token):
                raise HTTPException(status_code=401, detail="会话已登出，请重新登录")
            # 更新会话活跃时间
            await _update_session(token, uid, request)
            return uid
        # 回退 API token（REST 自动化 / OAuth 三方令牌）
        uid = await _api_token_user(token)
        if uid:
            # OAuth 三方令牌（有 scope 行）只能访问 OPEN_API_ROUTES 声明的开放面；
            # 用户在控制台签发的 PAT/会话令牌无 scope 行 → 全权限（不变）。
            # 这收紧了此前 _require_user 对 OAuth 令牌不校验 scope 的越权暴露：
            # 三方 docs:read 令牌不得触达删除/管理员等未声明路由。
            if await _oauth_token_scopes(token):
                if not _oauth_route_allowed(request.method, request.url.path):
                    raise HTTPException(status_code=403, detail="OAuth 令牌仅限开放 API 路由（见 /api/v1/openapi）")
            return uid
        raise HTTPException(status_code=401, detail="未登录或登录已过期（可用 API Token）")


# 会话 token 吊销名单：内存缓存 + 持久化（多实例经 Redis 共享）
_revoked_set: set[str] = set()


def _token_revocation_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


async def _load_revoked_tokens():
    """启动时加载已吊销 token 哈希到内存（Redis 模式下用 sismember 查询）。"""
    try:
        async with _registry_transaction() as db:
            rows = await (await db.execute("SELECT token_hash FROM revoked_tokens")).fetchall()
        _revoked_set.update(r["token_hash"] for r in rows)
    except Exception:
        pass


async def _is_token_revoked(token: str) -> bool:
    key = _token_revocation_key(token)
    # Redis 共享名单（多实例）
    try:
        r = await get_redis()
        if r is not None:
            return bool(await r.sismember("mde:revoked", key))
    except Exception:
        pass
    return key in _revoked_set


async def _revoke_token(token: str, uid: str):
    """吊销会话 token（写入持久表 + Redis 共享 + 内存）。"""
    key = _token_revocation_key(token)
    now = _utcnow_iso()
    _revoked_set.add(key)
    try:
        async with _registry_transaction() as db:
            await db.execute(
                "INSERT OR IGNORE INTO revoked_tokens (token_hash, user_id, revoked_at) VALUES (?,?,?)",
                (key, uid, now),
            )
        # 删除对应会话记录
        sid = hashlib.sha256(token.encode()).hexdigest()[:16]
        async with _registry_transaction() as db:
            await db.execute("DELETE FROM sessions WHERE id=?", (sid,))
    except Exception:
        pass
    try:
        r = await get_redis()
        if r is not None:
            await r.sadd("mde:revoked", key)
    except Exception:
        pass


async def _update_session(token: str, uid: str, request: Request):
    """创建/更新会话记录（失败静默）。"""
    try:
        sid = hashlib.sha256(token.encode()).hexdigest()[:16]
        now = _utcnow_iso()
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent", "")[:200]
        async with _registry_transaction() as db:
            existing = await (await db.execute("SELECT id FROM sessions WHERE id=?", (sid,))).fetchone()
            if existing:
                await db.execute("UPDATE sessions SET last_active=?, ip=?, user_agent=? WHERE id=?", (now, ip, ua, sid))
            else:
                await db.execute(
                    "INSERT INTO sessions (id, user_id, ip, user_agent, created_at, last_active) VALUES (?,?,?,?,?,?)",
                    (sid, uid, ip, ua, now, now),
                )
    except Exception:
        pass


@app.get("/api/sessions")
async def list_sessions(user_id: str = Depends(_require_user)):
    """列出当前用户的活跃会话。"""
    async with _registry_transaction() as db:
        rows = await (await db.execute(
            "SELECT id, ip, user_agent, created_at, last_active FROM sessions WHERE user_id=? ORDER BY last_active DESC",
            (user_id,),
        )).fetchall()
    return {"items": [
        {"id": r["id"], "ip": r["ip"], "user_agent": r["user_agent"],
         "created_at": r["created_at"], "last_active": r["last_active"]}
        for r in rows
    ]}


@app.delete("/api/sessions/{sid}")
async def revoke_session(sid: str, user_id: str = Depends(_require_user)):
    """强制注销某会话（仅能注销自己的）。"""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT user_id FROM sessions WHERE id=?", (sid,))).fetchone()
        if not row:
            raise HTTPException(404, "会话不存在")
        if row["user_id"] != user_id:
            raise HTTPException(403, "只能注销自己的会话")
        await db.execute("DELETE FROM sessions WHERE id=?", (sid,))
    await _audit(user_id, None, "auth.session.revoke", "session", sid, None)
    return {"ok": True}


async def _auth_payload(user_id: str, username: str) -> dict:
    """构造登录/注册成功响应：access（短 TTL）+ refresh（长 TTL，可轮换）。
    保留 token 字段=access 以兼容旧前端。"""
    access = _issue_access_token(user_id, username)
    refresh = await _issue_refresh_token(user_id, username)
    return {"token": access, "access": access, "refresh": refresh, "user_id": user_id, "username": username}


@app.post("/api/auth/register")
async def auth_register(req: AuthRequest):
    if not AUTH_ALLOW_REGISTER:
        raise HTTPException(403, "管理员已关闭自助注册")
    username = (req.username or "").strip()
    password = req.password or ""
    if not username or not password:
        raise HTTPException(400, "用户名和密码不能为空")
    if len(username) > 32 or not re.match(r"^[A-Za-z0-9_.\-]+$", username):
        raise HTTPException(400, "用户名仅支持字母数字、下划线、点、短横线（≤32 字符）")
    if len(password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    user_id = secrets.token_urlsafe(12)
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        try:
            await db.execute(
                "INSERT INTO users (user_id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, username, _hash_password(password), now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "用户名已被占用")
        # 数据驻留：新用户落默认 region
        if DATA_RESIDENCY_ENABLED and RESIDENCY_DEFAULT_REGION:
            await db.execute("UPDATE users SET residency_region=? WHERE user_id=?",
                             (RESIDENCY_DEFAULT_REGION, user_id))
    # 认领迁移期未归属（user_id=''）的旧文档到新用户库（保留旧版"首个用户认领"语义）
    try:
        await _claim_unowned_docs(user_id)
    except Exception as e:
        logger.warning("认领未归属文档失败 user=%s: %s", user_id, e)
    # 为新用户播种 examples 示例文件夹（仅在用户库为空时）
    try:
        await _seed_examples(user_id)
    except Exception as e:
        logger.warning("播种示例文档失败 user=%s: %s", user_id, e)
    logger.info("注册用户 username=%s", username)
    return await _auth_payload(user_id, username)


@app.post("/api/auth/login")
async def auth_login(req: AuthRequest):
    username = (req.username or "").strip()
    password = req.password or ""
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT * FROM users WHERE username=?", (username,))).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    # SCIM/管理员停用的账号禁止登录
    if "active" in row.keys() and not row["active"]:
        raise HTTPException(403, "该账号已被停用")
    # 2FA：若已启用 TOTP，不直接发 token，要求二次验证
    if row["totp_secret"]:
        return {"requires_2fa": True, "user_id": row["user_id"], "username": username}
    return await _auth_payload(row["user_id"], username)


@app.get("/api/auth/me")
async def auth_me(user_id: str = Depends(_require_user)):
    async with _registry_transaction() as db:
        row = await (await db.execute(
            "SELECT username, is_admin, display_name, avatar_url, org_id FROM users WHERE user_id=?",
            (user_id,),
        )).fetchone()
    if not row:
        raise HTTPException(401, "用户不存在")
    return {
        "user_id": user_id,
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "display_name": row["display_name"] or row["username"],
        "avatar_url": row["avatar_url"],
        "org_id": row["org_id"],
    }


@app.post("/api/auth/logout")
async def auth_logout(request: Request, user_id: str = Depends(_require_user)):
    """登出：吊销本地会话 token（立即失效）；若启用 SSO 则返回 IdP 全局登出 URL。
    前端收到 sso_logout_url 时应跳转过去做单点登出（SLO）。"""
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
    if token and "." in token and _parse_token(token):
        await _revoke_token(token, user_id)
    # 同时吊销请求体中携带的 refresh token（若有）
    try:
        body = await request.json()
    except Exception:
        body = {}
    rtok = (body or {}).get("refresh_token") or ""
    if rtok:
        await _revoke_refresh_token(rtok, user_id)
    await _audit(user_id, None, "auth.logout", "user", user_id, None)
    sso_logout_url = await _build_sso_logout_url()
    return {"logged_out": True, "sso_logout_url": sso_logout_url}


@app.post("/api/auth/refresh")
async def auth_refresh(request: Request):
    """用 refresh token 换发新的 access + refresh（轮换：旧 refresh 立即吊销）。
    请求体 {"refresh_token": "..."} 或 Authorization: Bearer <refresh>。"""
    auth = request.headers.get("Authorization", "")
    tok = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
    if not tok:
        try:
            body = await request.json()
        except Exception:
            body = {}
        tok = (body or {}).get("refresh_token") or ""
    if not tok:
        raise HTTPException(400, "缺少 refresh_token")
    ok, uid = await _is_refresh_token_valid(tok)
    if not ok:
        raise HTTPException(401, "refresh token 无效或已过期")
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT username FROM users WHERE user_id=?", (uid,))).fetchone()
    if not row:
        raise HTTPException(401, "用户不存在")
    # 轮换：吊销旧 refresh，签发新 access + 新 refresh
    await _revoke_refresh_token(tok, uid)
    await _audit(uid, None, "auth.refresh", "user", uid, None)
    return await _auth_payload(uid, row["username"])


async def _build_sso_logout_url() -> str:
    """构造 SSO 全局登出 URL（OIDC end_session / SAML SLO）。无 SSO 配置返回空。"""
    from urllib.parse import urlencode as _ue
    # OIDC
    if _oidc_enabled():
        try:
            disc = await _oidc_discovery()
            end_ep = disc.get("end_session_endpoint") or os.environ.get("OIDC_END_SESSION_ENDPOINT", "")
            if end_ep:
                params = {}
                if OIDC_POST_LOGOUT_URL:
                    params["post_logout_redirect_uri"] = OIDC_POST_LOGOUT_URL
                sep = "&" if "?" in end_ep else "?"
                return f"{end_ep}{sep}{_ue(params)}" if params else end_ep
        except Exception:
            pass
    # SAML SLO（SP 发起，Redirect 绑定）
    if SAML_IDP_SLO_URL and SAML_SP_ENTITY_ID:
        # 简化：直接带 NameID+return，由 IdP 处理；完整 SLO 需签名 LogoutRequest
        sep = "&" if "?" in SAML_IDP_SLO_URL else "?"
        return f"{SAML_IDP_SLO_URL}{sep}{_ue({'return': OIDC_POST_LOGOUT_URL or '/'})}"
    return ""


# ==================== 企业 SSO（OIDC 授权码流程）====================
_oidc_states: dict[str, float] = {}  # state -> 过期时间戳（单次使用，5 分钟有效）
_OIDC_STATE_TTL = 300
_oidc_discovery_cache: dict = {}


def _oidc_enabled() -> bool:
    return bool(OIDC_ISSUER and OIDC_CLIENT_ID and OIDC_REDIRECT_URI)


async def _oidc_discovery() -> dict:
    """获取 IdP 发现文档（带缓存）。或用环境变量显式覆盖端点。"""
    if _oidc_discovery_cache.get(OIDC_ISSUER):
        return _oidc_discovery_cache[OIDC_ISSUER]
    disc = {}
    if OIDC_AUTHORIZATION_ENDPOINT and OIDC_TOKEN_ENDPOINT and OIDC_USERINFO_ENDPOINT:
        disc = {"authorization_endpoint": OIDC_AUTHORIZATION_ENDPOINT,
                "token_endpoint": OIDC_TOKEN_ENDPOINT,
                "userinfo_endpoint": OIDC_USERINFO_ENDPOINT}
    else:
        url = OIDC_ISSUER.rstrip("/") + "/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code != 200:
                raise HTTPException(502, f"OIDC 发现文档获取失败: HTTP {r.status_code}")
            disc = r.json()
    _oidc_discovery_cache[OIDC_ISSUER] = disc
    return disc


def _oidc_make_state() -> str:
    st = secrets.token_urlsafe(24)
    _oidc_states[st] = time.time() + _OIDC_STATE_TTL
    return st


def _oidc_consume_state(st: str) -> bool:
    exp = _oidc_states.pop(st, None)
    if not exp:
        return False
    return exp >= time.time()


@app.get("/api/auth/oidc/login")
async def oidc_login(request: Request):
    """重定向到 IdP 授权端点。"""
    if not _oidc_enabled():
        raise HTTPException(400, "OIDC 未配置（OIDC_ISSUER/CLIENT_ID/REDIRECT_URI）")
    disc = await _oidc_discovery()
    state = _oidc_make_state()
    params = {
        "response_type": "code",
        "client_id": OIDC_CLIENT_ID,
        "redirect_uri": OIDC_REDIRECT_URI,
        "scope": OIDC_SCOPES,
        "state": state,
    }
    from urllib.parse import urlencode as _ue
    auth_ep = disc.get("authorization_endpoint")
    if not auth_ep:
        raise HTTPException(500, "IdP 未提供 authorization_endpoint")
    return RedirectResponse(f"{auth_ep}?{_ue(params)}")


@app.get("/api/auth/oidc/callback")
async def oidc_callback(request: Request):
    """IdP 回调：换 token、取 userinfo、关联/创建本地用户、签发本地 token，跳转前端。"""
    if not _oidc_enabled():
        raise HTTPException(400, "OIDC 未配置")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    err = request.query_params.get("error")
    if err:
        raise HTTPException(400, f"IdP 返回错误: {err}")
    if not code or not state or not _oidc_consume_state(state):
        raise HTTPException(400, "无效或过期的 state（CSRF 校验失败）")
    disc = await _oidc_discovery()
    token_ep = disc.get("token_endpoint")
    userinfo_ep = disc.get("userinfo_endpoint")
    if not (token_ep and userinfo_ep):
        raise HTTPException(500, "IdP 未提供 token/userinfo 端点")
    # 换 token
    async with httpx.AsyncClient(timeout=15) as client:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OIDC_REDIRECT_URI,
            "client_id": OIDC_CLIENT_ID,
        }
        if OIDC_CLIENT_SECRET:
            data["client_secret"] = OIDC_CLIENT_SECRET
        r = await client.post(token_ep, data=data, headers={"Accept": "application/json"})
        if r.status_code != 200:
            raise HTTPException(401, f"换 token 失败: HTTP {r.status_code} {r.text[:200]}")
        access_token = r.json().get("access_token")
        if not access_token:
            raise HTTPException(502, "IdP 未返回 access_token")
        # 取 userinfo
        ur = await client.get(userinfo_ep, headers={"Authorization": f"Bearer {access_token}"})
        if ur.status_code != 200:
            raise HTTPException(501, f"userinfo 获取失败: HTTP {ur.status_code}")
        userinfo = ur.json()
    sub = userinfo.get("sub")
    if not sub:
        raise HTTPException(502, "userinfo 未包含 sub")
    username = userinfo.get("preferred_username") or userinfo.get("email") or f"oidc-{sub[:8]}"
    # 关联或创建本地用户（按 oidc_sub）
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT user_id, username FROM users WHERE oidc_sub=?", (sub,))).fetchone()
        if row:
            user_id = row["user_id"]; uname = row["username"]
        else:
            # 用户名冲突时加后缀
            base_uname = username
            uname = base_uname
            n = 1
            while await (await db.execute("SELECT 1 FROM users WHERE username=?", (uname,))).fetchone():
                n += 1; uname = f"{base_uname}-{n}"
            user_id = secrets.token_urlsafe(12)
            await db.execute(
                "INSERT INTO users (user_id, username, password_hash, created_at, is_admin, oidc_sub) VALUES (?,?,?,?,0,?)",
                (user_id, uname, "", now, sub),
            )
            await _claim_unowned_docs(user_id)
    token = _issue_token(user_id, uname)
    await _audit(user_id, None, "auth.oidc.login", "user", user_id, f"sub={sub}")
    from urllib.parse import urlencode as _ue
    return RedirectResponse(f"{OIDC_FRONTEND_URL}?{_ue({'token': token, 'username': uname})}")


# ==================== 企业 SSO：SAML 2.0 SP ====================
def _saml_enabled() -> bool:
    return bool(SAML_SP_ENTITY_ID and SAML_IDP_SSO_URL)


def _saml_build_authn_request(relay_state: str) -> str:
    """构造 SAML AuthnRequest XML（Redirect 绑定用：base64+deflate 编码前的原始 XML）。"""
    req_id = "_" + secrets.token_hex(16)
    issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    acs = SAML_ACS_URL or (SAML_SP_ENTITY_ID.rstrip("/") + "/api/auth/saml/acs")
    return (
        f'<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
        f'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
        f'ID="{req_id}" Version="2.0" IssueInstant="{issue_instant}" '
        f'Destination="{SAML_IDP_SSO_URL}" AssertionConsumerServiceURL="{acs}" '
        f'ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
        f'<saml:Issuer>{SAML_SP_ENTITY_ID}</saml:Issuer>'
        f'<samlp:NameIDPolicy AllowCreate="true" Format="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"/>'
        f'</samlp:AuthnRequest>'
    )


def _saml_encode_request(xml: str) -> str:
    """SAML Redirect 绑定编码：deflate → base64 → urlencode。"""
    import zlib
    from urllib.parse import quote
    return quote(base64.b64encode(zlib.compress(xml.encode("utf-8"))[2:-4]).decode())


# SAML RelayState 单次使用（CSRF），复用 OIDC state 表的机制
_saml_states: dict[str, float] = {}


def _saml_make_state() -> str:
    st = secrets.token_urlsafe(24)
    _saml_states[st] = time.time() + _OIDC_STATE_TTL
    return st


def _saml_consume_state(st: str) -> bool:
    exp = _saml_states.pop(st, None)
    return bool(exp and exp > time.time())


def _saml_parse_response(saml_response_b64: str) -> dict:
    """解析 SAMLResponse（base64 解码 → XML），提取 NameID 与属性。
    返回 {nameid, attributes, issuer, conditions_notbefore, conditions_notonorafter}。
    验签由调用方按 SAML_VERIFY_SIGNATURE 决定（xmlsec1）。"""
    import xml.etree.ElementTree as ET
    from urllib.parse import unquote
    raw = base64.b64decode(unquote(saml_response_b64))
    root = ET.fromstring(raw)
    ns = {
        "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
        "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }
    # 提取 Subject/NameID
    nameid_el = root.find(".//saml:Subject/saml:NameID", ns)
    nameid = nameid_el.text.strip() if nameid_el is not None and nameid_el.text else ""
    issuer_el = root.find(".//saml:Issuer", ns)
    issuer = issuer_el.text.strip() if issuer_el is not None and issuer_el.text else ""
    # 提取属性（AttributeStatement）
    attributes = {}
    for attr in root.findall(".//saml:Attribute", ns):
        aname = attr.get("Name", "")
        vals = [v.text for v in attr.findall("saml:AttributeValue", ns) if v.text]
        if aname:
            attributes[aname] = vals[0] if len(vals) == 1 else vals
    cond = root.find(".//saml:Conditions", ns)
    notbefore = cond.get("NotBefore") if cond is not None else None
    notonorafter = cond.get("NotOnOrAfter") if cond is not None else None
    return {"nameid": nameid, "attributes": attributes, "issuer": issuer,
            "notbefore": notbefore, "notonorafter": notonorafter}


async def _saml_verify_signature(saml_response_b64: str) -> bool:
    """用 xmlsec1 验证 SAMLResponse 签名（生产）。无 xmlsec1 或未配证书 → False。"""
    if not SAML_VERIFY_SIGNATURE:
        return True  # dev/受信内网模式
    if not SAML_IDP_CERT or not SAML_XMLSEC1:
        return False
    import tempfile as _tf
    tmp = _tf.mkdtemp(prefix="saml_")
    try:
        cert_path = _os_path(tmp, "idp.pem")
        Path(cert_path).write_text(SAML_IDP_CERT)
        xml_path = _os_path(tmp, "resp.xml")
        from urllib.parse import unquote
        Path(xml_path).write_bytes(base64.b64decode(unquote(saml_response_b64)))
        # xmlsec1 --verify --enabled-key-data x509 --pubkey-cert-pem <cert> --trusted-pem <cert>
        import subprocess as _sp
        r = _sp.run([SAML_XMLSEC1, "--verify", "--enabled-key-data", "x509",
                     "--trusted-pem", cert_path, "--insecure", xml_path],
                    capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception as e:
        logger.warning("SAML 验签异常: %s", e)
        return False
    finally:
        import shutil as _sh
        _sh.rmtree(tmp, ignore_errors=True)


def _os_path(tmp: str, name: str) -> str:
    return str(Path(tmp) / name)


@app.get("/api/auth/saml/login")
async def saml_login(request: Request):
    """SP 发起：重定向到 IdP SSO URL（带 SAMLRequest + RelayState）。"""
    if not _saml_enabled():
        raise HTTPException(503, "SAML 未配置（SAML_SP_ENTITY_ID/SAML_IDP_SSO_URL）")
    relay = _saml_make_state()
    xml = _saml_build_authn_request(relay)
    encoded = _saml_encode_request(xml)
    from urllib.parse import urlencode as _ue
    sep = "&" if "?" in SAML_IDP_SSO_URL else "?"
    return RedirectResponse(f"{SAML_IDP_SSO_URL}{sep}{_ue({'SAMLRequest': encoded, 'RelayState': relay})}")


@app.post("/api/auth/saml/acs")
async def saml_acs(request: Request):
    """Assertion Consumer Service：IdP POST SAMLResponse → 解析 → 关联/创建本地用户。"""
    if not _saml_enabled():
        raise HTTPException(503, "SAML 未配置")
    form = await request.form()
    saml_response = form.get("SAMLResponse", "")
    relay = form.get("RelayState", "")
    if not saml_response or not relay or not _saml_consume_state(relay):
        raise HTTPException(400, "无效或过期的 RelayState（CSRF 校验失败）")
    # 验签（生产必须通过；dev 模式 SAML_VERIFY_SIGNATURE=false 跳过）
    if not await _saml_verify_signature(saml_response):
        raise HTTPException(401, "SAML 签名验证失败（请配置 SAML_IDP_CERT 与 xmlsec1，或内网设 SAML_VERIFY_SIGNATURE=false）")
    info = _saml_parse_response(saml_response)
    sub = info["nameid"]
    if not sub:
        raise HTTPException(400, "SAMLResponse 未包含 NameID")
    # 用户名：优先属性，其次 NameID
    attrs = info["attributes"]
    username = (attrs.get("username") or attrs.get("Username")
                 or attrs.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")
                 or attrs.get("email")
                 or attrs.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress")
                 or f"saml-{sub[:8]}")
    if isinstance(username, list):
        username = username[0]
    now = _utcnow_iso()
    async with _registry_transaction() as db:
        row = await (await db.execute("SELECT user_id, username FROM users WHERE saml_sub=?", (sub,))).fetchone()
        if row:
            user_id = row["user_id"]; uname = row["username"]
        else:
            base_uname = username; uname = base_uname; n = 1
            while await (await db.execute("SELECT 1 FROM users WHERE username=?", (uname,))).fetchone():
                n += 1; uname = f"{base_uname}-{n}"
            user_id = secrets.token_urlsafe(12)
            await db.execute(
                "INSERT INTO users (user_id, username, password_hash, created_at, is_admin, saml_sub) VALUES (?,?,?,?,0,?)",
                (user_id, uname, "", now, sub),
            )
            await _claim_unowned_docs(user_id)
    token = _issue_token(user_id, uname)
    await _audit(user_id, None, "auth.saml.login", "user", user_id, f"sub={sub}")
    from urllib.parse import urlencode as _ue
    return RedirectResponse(f"{OIDC_FRONTEND_URL}?{_ue({'token': token, 'username': uname})}")


@app.get("/api/auth/saml/metadata")
async def saml_metadata():
    """SP 元数据 XML（供 IdP 注册本 SP：EntityID + ACS 端点）。"""
    if not SAML_SP_ENTITY_ID:
        raise HTTPException(503, "SAML 未配置")
    acs = SAML_ACS_URL or (SAML_SP_ENTITY_ID.rstrip("/") + "/api/auth/saml/acs")
    xml = (
        f'<?xml version="1.0"?>'
        f'<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" '
        f'entityID="{SAML_SP_ENTITY_ID}">'
        f'<SPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
        f'<NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified</NameIDFormat>'
        f'<AssertionConsumerService index="0" isDefault="true" '
        f'Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{acs}"/>'
        f'</SPSSODescriptor></EntityDescriptor>'
    )
    return Response(content=xml, media_type="application/xml")


# ==================== 每用户配置文件 ====================
@app.get("/api/settings")
async def get_settings(user_id: str = Depends(_require_user)):
    """读取当前用户的配置文件（data/configs/<uid>.json），不存在返回 {}。"""
    p = _config_path(user_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


@app.put("/api/settings")
async def put_settings(payload: dict, user_id: str = Depends(_require_user)):
    """原子写入当前用户的配置文件。"""
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode("utf-8")) > USER_SETTINGS_MAX_BYTES:
        raise HTTPException(413, f"配置超过 {USER_SETTINGS_MAX_BYTES} 字节限制")
    p = _config_path(user_id)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(raw, encoding="utf-8")
    os.replace(str(tmp), str(p))
    return {"ok": True}


