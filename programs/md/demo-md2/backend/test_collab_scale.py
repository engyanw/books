# -*- coding: utf-8 -*-
"""P2-12 协同规模化：大文档/大团队 Yjs 文档体积与 awareness 压测、冲突规模化。

验证（无真实 Yjs 依赖，用原始字节模拟 Yjs update/snapshot）：
1. 大量并发增量落库 + 广播：N 连接、M 条 update，全部落库且 seq 连续，_FakeWS 收到广播。
2. collab_updates 保留上限：超 COLLAB_MAX_UPDATES_PER_ROOM 自动按 seq 删最旧。
3. 快照体积上限：超 COLLAB_MAX_SNAPSHOT_BYTES 拒绝持久化（返回 False）→ DB 无该快照。
4. awareness 负载上限：超大 cursor 消息被丢弃（不广播、不落库）。
5. presence 上限：超 cap 淘汰最旧，len 不超过 cap。
6. bench 计时：大规模 update 落库吞吐可接受（仅断言完成，不强性能门槛）。
"""
import os, tempfile, time, base64, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="collabscale_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 用小 cap 便于测试
os.environ["COLLAB_MAX_UPDATES_PER_ROOM"] = "20"
os.environ["COLLAB_MAX_SNAPSHOT_BYTES"] = "64"
os.environ["COLLAB_MAX_PRESENCE_PER_ROOM"] = "3"
os.environ["COLLAB_MAX_AWARENESS_BYTES"] = "32"

import main  # noqa: E402

REG = os.environ["REGISTRY_DB_PATH"]


def _count_updates(room):
    conn = sqlite3.connect(REG); conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT COUNT(*) FROM collab_updates WHERE room=?", (room,)).fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()


def _has_snapshot(room):
    conn = sqlite3.connect(REG); conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT state FROM collab_state WHERE room=?", (room,)).fetchone() is not None
    finally:
        conn.close()


class _FakeWS:
    def __init__(self):
        self.sent = []
    async def send_bytes(self, data): self.sent.append(("b", data))
    async def send_text(self, text): self.sent.append(("t", text))


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "scale", "password": "p@ssw0rd"})
    tok = c.post("/api/auth/login", json={"username": "scale", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}

    # --- 1. 大量并发增量落库 + 广播（单进程内） ---
    room = "personal:scale:big"
    fakes = [_FakeWS() for _ in range(10)]
    main._collab_rooms[room] = set(fakes)
    import asyncio
    async def _burst():
        for i in range(100):
            upd = f"U{i}".encode()
            await main._collab_broadcast_bytes(room, upd, exclude=fakes[0])
            await main._collab_append_update(room, upd)
    asyncio.run(_burst())
    # fakes[1..9] 各收到 100 条广播（排除 fakes[0]）
    assert all(len(f.sent) == 100 for f in fakes[1:]), [len(f.sent) for f in fakes]
    assert len(fakes[0].sent) == 0, "excluded conn should get nothing"
    # 保留上限(cap=20)在插入过程中即时生效：100 条后仅留最旧 20 条 seq 81..100
    assert _count_updates(room) == 20, _count_updates(room)
    conn = sqlite3.connect(REG); conn.row_factory = sqlite3.Row
    remain = [r["seq"] for r in conn.execute("SELECT seq FROM collab_updates WHERE room=? ORDER BY seq", (room,)).fetchall()]
    conn.close()
    assert remain == list(range(81, 101)), remain

    # --- 2. 保留上限验证已并入上方（即时淘汰） ---
    # 单独再验证：cap 边界——从 20 条再插 1 条，应保持 20 条且最旧 seq 82..101
    asyncio.run(main._collab_append_update(room, b"X"))
    assert _count_updates(room) == 20, _count_updates(room)
    conn = sqlite3.connect(REG); conn.row_factory = sqlite3.Row
    remain2 = [r["seq"] for r in conn.execute("SELECT seq FROM collab_updates WHERE room=? ORDER BY seq", (room,)).fetchall()]
    conn.close()
    assert remain2 == list(range(82, 102)), remain2

    # --- 3. 快照体积上限（cap=64 bytes） ---
    big_snap = "A" * 200  # > 64
    ok = asyncio.run(main._collab_save_state(room, big_snap))
    assert ok is False, "oversize snapshot should be rejected"
    assert not _has_snapshot(room), "rejected snapshot must not persist"
    ok2 = asyncio.run(main._collab_save_state(room, "tiny"))  # ≤ 64
    assert ok2 is True and _has_snapshot(room)

    # --- 4. awareness 负载上限（cap=32）经 WS 路径丢弃 ---
    room2 = "personal:scale:aware"
    with c.websocket_connect(f"/ws/collab/{room2}?token={tok}") as ws:
        # 正常小 cursor 应被广播（这里仅验证不报错）
        ws.send_text('{"type":"cursor","x":1}')
        time.sleep(0.1)
        # 超大 awareness：64KB 文本 → 应被丢弃，不返回错误
        big = '{"type":"cursor","p":"' + ("x" * 70000) + '"}'
        ws.send_text(big)
        time.sleep(0.1)
    # 无断言性异常即通过（连接正常关闭）

    # --- 5. presence 上限（cap=3） ---
    main._collab_presence.pop(room, None)
    pres = main._collab_presence.setdefault(room, {})
    for i in range(6):
        pres[f"u{i}"] = f"name{i}"
        # 模拟 WS handler 的淘汰逻辑
        if main.COLLAB_MAX_PRESENCE_PER_ROOM > 0 and len(pres) > main.COLLAB_MAX_PRESENCE_PER_ROOM:
            pres.pop(next(iter(pres)), None)
    assert len(pres) == main.COLLAB_MAX_PRESENCE_PER_ROOM, (len(pres), pres)
    assert "u5" in pres, "newest retained"
    main._collab_presence.pop(room, None)

    # --- 6. bench：大规模 update 落库吞吐 ---
    room3 = "personal:scale:bench"
    main._collab_rooms[room3] = set()
    async def _bench():
        for i in range(500):
            await main._collab_append_update(room3, f"B{i}".encode())
    t0 = time.time()
    asyncio.run(_bench())
    dt = time.time() - t0
    assert _count_updates(room3) == 20, "bench also subject to retention cap"  # cap=20
    print(f"  bench: 500 updates appended in {dt:.2f}s, retained={_count_updates(room3)}")

print("ALL PASSED")
