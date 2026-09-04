# -*- coding: utf-8 -*-
"""任务队列（进程内模式）+ PresenceBus 单实例行为。
不依赖 TestClient：直接在事件循环里测 taskqueue 模块。"""
import os, tempfile, asyncio, json

TMP = tempfile.mkdtemp(prefix="tq_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 不设 REDIS_URL → 进程内模式

import taskqueue  # noqa: E402
from taskqueue import enqueue, register_task, get_redis, presence_bus, PresenceBus  # noqa: E402


async def main_test():
    # 1) 无 REDIS_URL 时 get_redis 返回 None
    r = await get_redis()
    assert r is None, "无 REDIS_URL 应回 None"

    # 2) 进程内任务：enqueue 后异步执行
    results = []
    async def job(x, y=0):
        results.append(x + y)
    register_task("add", job)
    await enqueue("add", 1, y=2)
    await asyncio.sleep(0.05)
    assert results == [3], f"任务未执行: {results}"

    # 3) 未知任务名不报错
    await enqueue("nope")

    # 4) PresenceBus.publish 无 Redis 时为 no-op（不抛错）
    async def noop_dispatch(room, msg):
        pass
    presence_bus.register_room("room1", noop_dispatch)
    await presence_bus.publish("room1", {"type": "presence", "action": "join"})

    # 5) INSTANCE_ID 存在且非空（用于跨实例去重）
    assert taskqueue.INSTANCE_ID and len(taskqueue.INSTANCE_ID) >= 8

asyncio.run(main_test())
print("ALL PASSED")
