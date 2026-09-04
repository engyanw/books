# -*- coding: utf-8 -*-
"""P0-A1/A2：共享限流 + Yjs 协同态持久化与跨实例同步。

- allow_rate：Redis 模式跨实例计数（无 Redis 回退进程内滑动窗口）。
- Yjs 快照持久化：客户端提交全量快照 → 落库；新连接恢复历史态。
- 增量二进制跨实例分发：_collab_local_dispatch 解码 base64 后发给本地连接。
"""
import os, shutil, tempfile, asyncio, sqlite3, base64
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="collabp_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402
from taskqueue import allow_rate  # noqa: E402


def _state_of(room):
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"]); conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT state FROM collab_state WHERE room=?", (room,)).fetchone()
    conn.close()
    return r["state"] if r else None


# 1) 共享速率限制（进程内回退路径，Redis 不可用时）
async def _rate_tests():
    assert await allow_rate("k1", 2, 60) is True
    assert await allow_rate("k1", 2, 60) is True
    assert await allow_rate("k1", 2, 60) is False
    assert await allow_rate("k2", 2, 60) is True  # 不同 key 互不影响
    assert await allow_rate("k3", 1, 0.05) is True
    assert await allow_rate("k3", 1, 0.05) is False
    await asyncio.sleep(0.08)
    assert await allow_rate("k3", 1, 0.05) is True  # 窗口过期后恢复


# 2) _collab_local_dispatch 解码 base64 → 发 bytes 给本地连接（异步单测，无需 TestClient）
class _FakeWS:
    def __init__(self): self.sent = []
    async def send_bytes(self, data): self.sent.append(("bytes", data))
    async def send_text(self, text): self.sent.append(("text", text))

async def _dispatch_tests():
    room = "personal:unit:dispatch"
    fake = _FakeWS()
    main._collab_rooms[room] = {fake}
    await main._collab_local_dispatch(room, {"type": "yjs_update", "b64": base64.b64encode(b"xyz").decode()})
    assert fake.sent == [("bytes", b"xyz")], fake.sent
    # snapshot → 文本广播
    fake2 = _FakeWS(); main._collab_rooms[room] = {fake2}
    await main._collab_local_dispatch(room, {"type": "yjs_snapshot", "b64": "QUFBQQ==", "room": room})
    assert any("yjs_snapshot" in t and "QUFBQQ==" in t for (_, t) in fake2.sent), fake2.sent
    main._collab_rooms.pop(room, None)


asyncio.run(_rate_tests())
asyncio.run(_dispatch_tests())

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "cu", "password": "p@ssw0rd"})
    tok = c.post("/api/auth/login", json={"username": "cu", "password": "p@ssw0rd"}).json()["token"]
    room = "personal:cu:snapdoc"

    # 3) 快照持久化 + 新连接恢复
    with c.websocket_connect(f"/ws/collab/{room}?token={tok}") as ws1:
        ws1.send_text('{"type":"yjs_snapshot","b64":"AAECAwQ="}')
        import time as _t; _t.sleep(0.15)
        assert _state_of(room) == "AAECAwQ=", _state_of(room)

    # 新连接 ws2 应在连接时收到持久化快照
    with c.websocket_connect(f"/ws/collab/{room}?token={tok}") as ws2:
        first = ws2.receive_text()
        assert '"yjs_snapshot"' in first and "AAECAwQ=" in first, first

    # 4) 快照覆盖：新快照替换旧快照
    with c.websocket_connect(f"/ws/collab/{room}?token={tok}") as ws3:
        ws3.send_text('{"type":"yjs_snapshot","b64":"AAAA"}')
        _t.sleep(0.15)
    assert _state_of(room) == "AAAA", _state_of(room)

    # 5) C1：增量更新落库 + 重连回放 + 快照清增量
    room2 = "personal:cu:incr"
    # 发若干二进制增量（无需先有快照，纯增量也落库）
    with c.websocket_connect(f"/ws/collab/{room2}?token={tok}") as ws4:
        ws4.send_bytes(b"\x01\x02\x03")
        ws4.send_bytes(b"\x04\x05\x06")
        _t.sleep(0.2)
    # 增量已落库
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"]); conn.row_factory = sqlite3.Row
    cnt = conn.execute("SELECT COUNT(*) AS c FROM collab_updates WHERE room=?", (room2,)).fetchone()["c"]
    conn.close()
    assert cnt == 2, f"应落库 2 条增量，实际 {cnt}"

    # 新连接应回放全部待 apply 增量（无快照 → 不发 snapshot，只发 bytes）
    with c.websocket_connect(f"/ws/collab/{room2}?token={tok}") as ws5:
        recv = []
        try:
            for _ in range(2):
                msg = ws5.receive()
                if msg.get("bytes"):
                    recv.append(msg["bytes"])
        except Exception:
            pass
        assert b"\x01\x02\x03" in recv and b"\x04\x05\x06" in recv, f"未回放增量: {recv}"

    # 提交全量快照后增量被清空
    with c.websocket_connect(f"/ws/collab/{room2}?token={tok}") as ws6:
        ws6.send_text('{"type":"yjs_snapshot","b64":"AAAA"}')
        _t.sleep(0.2)
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"]); conn.row_factory = sqlite3.Row
    cnt2 = conn.execute("SELECT COUNT(*) AS c FROM collab_updates WHERE room=?", (room2,)).fetchone()["c"]
    conn.close()
    assert cnt2 == 0, f"快照后增量应清空，实际 {cnt2}"

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
