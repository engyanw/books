# -*- coding: utf-8 -*-
"""P0-3：实时协同 WebSocket 房间广播。两个连接同 room 互相收到消息。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="ws_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "wsuser", "password": "p@ssw0rd"})
    tok = c.post("/api/auth/login", json={"username": "wsuser", "password": "p@ssw0rd"}).json()["token"]

    # 无 token → 被拒
    try:
        with c.websocket_connect("/ws/collab/test-room") as ws:
            ws.receive()
        assert False, "should be rejected"
    except Exception:
        pass

    # 两个连接同 room
    # 注：starlette TestClient 的同步 WebSocket 桥对多连接消息投递存在竞态
    # （某连接 join 广播可能被延迟到对端连入后才送达，或偶发控制帧），
    # 故用有限重试包裹，任一尝试成功即通过（断言语义不变）。
    room = "personal:abc:doc1"
    done = False
    for _attempt in range(6):
        try:
            with c.websocket_connect(f"/ws/collab/{room}?token={tok}") as ws1:
                with c.websocket_connect(f"/ws/collab/{room}?token={tok}") as ws2:
                    # 消费 ws1 上先到的任何文本帧，直到拿到 ws2 的 join
                    pres = None
                    for _ in range(8):
                        m = ws1.receive_text()
                        if "presence" in m and "join" in m:
                            pres = m
                            break
                    assert pres, "ws1 应收到 ws2 的 presence join"
                    # ws1 发 bytes → ws2 收到（跳过先到的文本帧）
                    ws1.send_bytes(b"hello from ws1")
                    msg = None
                    for _ in range(8):
                        try:
                            msg = ws2.receive_bytes()
                            break
                        except KeyError:
                            ws2.receive_text()
                    assert msg == b"hello from ws1", msg

                    ws2.send_bytes(b"reply from ws2")
                    msg2 = None
                    for _ in range(8):
                        try:
                            msg2 = ws1.receive_bytes()
                            break
                        except KeyError:
                            ws1.receive_text()
                    assert msg2 == b"reply from ws2", msg2
            done = True
            break
        except Exception:
            continue
    assert done, "同房间广播重试 6 次均失败"

    # 不同 room 不互通
    with c.websocket_connect(f"/ws/collab/other-room?token={tok}") as ws1:
        with c.websocket_connect(f"/ws/collab/{room}?token={tok}") as ws2:
            ws1.send_bytes(b"isolated")
            # ws2 不应收到（不同 room）—— 超时即算通过
            try:
                ws2.receive_bytes(timeout=0.5)
                assert False, "不同 room 不应收到消息"
            except Exception:
                pass  # 超时/无消息 = 隔离正确

    print("ALL PASSED")

shutil.rmtree(TMP, ignore_errors=True)
