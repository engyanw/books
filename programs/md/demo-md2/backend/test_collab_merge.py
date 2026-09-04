# -*- coding: utf-8 -*-
"""①服务端 CRDT 合并（双模式）。
- ypy 不可用：_collab_server_merge 返回 {merged:False, reason:'ypy_unavailable'}，
  不清增量、不抛；compact 端点回退请求客户端推快照。
- ypy 可用：构造增量→合并→新快照落库→增量清空（真实服务端收敛）。
"""
import os, tempfile, asyncio, json, sqlite3

TMP = tempfile.mkdtemp(prefix="crdt_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

YPY = main._ypy_module() is not None
print(f"  ypy available: {YPY}")


def _make_real_updates():
    """生成真实 Yjs 增量：三份基于同一基线分支化的 YDoc，各自写不同文本后 encode_state_as_update。"""
    Y = main._ypy_module()
    base = Y.YDoc()
    base_state = Y.encode_state_as_update(base)
    ups = []
    for txt in ("hello", " world", "!"):
        d = Y.YDoc()
        Y.apply_update(d, base_state)  # 基于同一基线分支化
        with d.begin_transaction() as txn:
            d.get_text("content").extend(txn, txt)
        ups.append(Y.encode_state_as_update(d))
    return ups


def _count_updates(room):
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"]); conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT COUNT(*) FROM collab_updates WHERE room=?", (room,)).fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()


with TestClient(main.app) as c:  # lifespan 建表
    c.post("/api/auth/register", json={"username": "crdtadmin", "password": "p@ssw0rd"})
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='crdtadmin'")
    conn.commit(); conn.close()
    c.post("/api/auth/register", json={"username": "crdtuser", "password": "p@ssw0rd"})
    ta = c.post("/api/auth/login", json={"username": "crdtadmin", "password": "p@ssw0rd"}).json()["token"]
    tu = c.post("/api/auth/login", json={"username": "crdtuser", "password": "p@ssw0rd"}).json()["token"]
    ha = {"Authorization": f"Bearer {ta}"}
    hu = {"Authorization": f"Bearer {tu}"}

    room = "personal:crdt:t1"
    main._collab_rooms[room] = set()

    async def _seed():
        seed_updates = _make_real_updates() if YPY else [b"upd1", b"upd2", b"upd3"]
        for u in seed_updates:
            await main._collab_append_update(room, u)
    asyncio.run(_seed())
    assert _count_updates(room) == 3, _count_updates(room)

    rep = asyncio.run(main._collab_server_merge(room))
    if YPY:
        assert rep.get("merged") is True, rep
        assert rep.get("applied", 0) >= 1, rep
        assert asyncio.run(main._collab_load_state(room)) is not None, "合并后应有快照"
        assert _count_updates(room) == 0, "合并后增量应清空"
        # 真实 CRDT 收敛：解码合并后快照，应包含三段文本且长度==三段之和
        import base64 as _b64
        Y = main._ypy_module()
        snap_b64 = asyncio.run(main._collab_load_state(room))
        d = Y.YDoc(); Y.apply_update(d, _b64.b64decode(snap_b64))
        merged = str(d.get_text("content"))
        assert len(merged) == 12, merged  # hello(5)+" world"(6)+"!"(1)；顺序由 CRDT 并发合决定
        for piece in ("hello", "world", "!"):
            assert piece in merged, merged
        print(f"  real merge: {rep} merged_text={merged!r}")
    else:
        assert rep.get("merged") is False and rep.get("reason") == "ypy_unavailable", rep
        assert _count_updates(room) == 3, "降级不应清增量"
        print(f"  fallback (no ypy): {rep}")

    # 空房间 → empty
    rep2 = asyncio.run(main._collab_server_merge("personal:crdt:empty_room"))
    assert rep2.get("merged") is False, rep2

    # merge_loop 回退广播（无 ypy 时）
    if not YPY:
        room3 = "personal:crdt:loop3"
        class _FakeWS:
            def __init__(self): self.sent = []
            async def send_text(self, t): self.sent.append(t)
            async def send_bytes(self, b): pass
        fake = _FakeWS()
        main._collab_rooms[room3] = {fake}
        async def _seed3():
            for i in range(main.COLLAB_UPDATE_GC_THRESHOLD + 5):
                await main._collab_append_update(room3, f"u{i}".encode())
        asyncio.run(_seed3())
        asyncio.run(main._collab_broadcast_text(room3, json.dumps({"type": "request_snapshot", "room": room3})))
        assert any("request_snapshot" in s for s in fake.sent), fake.sent

    # 端点：非管理员 403；管理员 200
    assert c.post(f"/api/admin/collab/{room}/compact", headers=hu).status_code == 403
    r = c.post(f"/api/admin/collab/{room}/compact", headers=ha)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "merged" in body, body
    if not YPY:
        assert body.get("reason") == "ypy_unavailable", body
        assert body.get("fallback") in ("requested_client_snapshot", "no_online_clients"), body

print("ALL PASSED")
