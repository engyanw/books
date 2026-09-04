# -*- coding: utf-8 -*-
"""异步任务队列 + Redis 共享状态抽象层。

设计目标：单机部署零依赖（进程内 asyncio 即可），多实例部署设 REDIS_URL 后
自动切换为分布式：任务入 Redis 队列由 worker 消费，协同 presence 走 pub/sub
跨实例广播。这样多副本 backend 可共享状态，不丢失协同/定时任务。

对外接口：
    enqueue(name, *args, **kwargs)   提交后台任务（发邮件/备份/导出等）
    register_task(name, func)       注册可被队列调度的协程
    get_redis() / close_redis()     Redis 客户端（无则 None）
    PresenceBus                     协同房间跨实例 presence/cursor 广播
    start_worker()                  启动 Redis 模式任务消费循环（无 Redis 时 no-op）
"""
import asyncio
import json
import logging
import os
import secrets
import time
from collections import defaultdict
from typing import Awaitable, Callable, Optional

logger = logging.getLogger("taskqueue")

REDIS_URL = os.environ.get("REDIS_URL", "").strip()  # redis://[:pass@]host:6379/0

# 本实例唯一标识，用于 pubsub 跳过自身发布的消息（避免回声/重复投递）
INSTANCE_ID = secrets.token_hex(8)

_redis = None
_redis_checked = False

async def get_redis():
    """惰性获取 Redis 异步客户端；未配置或连接失败返回 None（回退进程内模式）。"""
    global _redis, _redis_checked
    if not REDIS_URL:
        return None
    if _redis_checked and _redis is None:
        return None
    if _redis is not None:
        return _redis
    _redis_checked = True
    try:
        import redis.asyncio as aioredis  # redis-py 自带 asyncio 支持
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("Redis 已连接（分布式模式）: %s", REDIS_URL)
    except ImportError:
        logger.warning("未安装 redis 包，回退进程内模式（pip install redis）")
        _redis = None
    except Exception as e:
        logger.warning("Redis 连接失败，回退进程内模式: %s", e)
        _redis = None
    return _redis


async def close_redis():
    global _redis
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None


# ==================== 任务队列 ====================
_registry: dict[str, Callable[..., Awaitable]] = {}


def register_task(name: str, func: Callable[..., Awaitable]):
    """注册一个可被队列调度的协程函数。"""
    _registry[name] = func


async def enqueue(name: str, *args, **kwargs):
    """提交后台任务。
    - Redis 模式：序列化入 mde:tasks 队列，由任意实例的 worker 消费（负载均衡）。
    - 进程内模式：立即 asyncio.create_task 执行。
    注意：args/kwargs 必须可 JSON 序列化（Redis 模式）。
    """
    if name not in _registry:
        logger.warning("未知任务名，已丢弃: %s", name)
        return
    r = await get_redis()
    if r is not None:
        try:
            await r.rpush("mde:tasks", json.dumps(
                {"name": name, "args": list(args), "kwargs": kwargs}, default=str
            ))
            return
        except Exception as e:
            logger.warning("入队失败，回退进程内: %s", e)
    asyncio.create_task(_run_local(name, list(args), kwargs))


async def _run_local(name: str, args: list, kwargs: dict):
    func = _registry.get(name)
    if func is None:
        return
    try:
        await func(*args, **kwargs)
    except Exception as e:
        logger.warning("任务[%s]执行失败: %s", name, e)


async def worker_loop():
    """Redis 模式下的任务消费循环。无 Redis 时立即返回（进程内任务无需消费）。"""
    r = await get_redis()
    if r is None:
        return
    logger.info("任务 worker 启动（Redis 模式）")
    while True:
        try:
            item = await r.blpop("mde:tasks", timeout=5)
            if not item:
                continue
            _, payload = item
            try:
                data = json.loads(payload)
            except Exception:
                logger.warning("丢弃无法解析的任务载荷")
                continue
            await _run_local(data.get("name", ""), data.get("args", []), data.get("kwargs", {}))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("任务消费异常: %s", e)
            await asyncio.sleep(1)


# ==================== 协同房间跨实例广播 ====================
class PresenceBus:
    """协同编辑房间 presence/cursor 的跨实例广播。

    单实例（无 Redis）：直接回调本地分发器。
    多实例（Redis）：每实例订阅 mde:presence:{room} 频道，
    发布消息到频道 → 各实例收到后分发到本地 WebSocket 连接。
    这样多副本后端能感知彼此的在线用户与光标。
    """

    def __init__(self):
        self._local_dispatch: dict[str, Callable[[str, dict], Awaitable]] = {}
        self._pubsubs: set = set()
        self._started = False

    def register_room(self, room: str, dispatch: Callable[[str, dict], Awaitable]):
        """注册房间本地分发器（room 内消息 → 广播给本地连接）。
        返回时若 Redis 可用会订阅对应频道。"""
        self._local_dispatch[room] = dispatch

    async def unregister_room(self, room: str):
        self._local_dispatch.pop(room, None)

    async def publish(self, room: str, msg: dict):
        """发布消息到 Redis 频道（供其他实例消费）。
        本地分发由调用方在协程内自行完成（可排除发送者），避免重复投递。
        无 Redis 时本方法为 no-op（调用方本地广播已覆盖本实例）。"""
        r = await get_redis()
        if r is None:
            return
        try:
            await r.publish(f"mde:presence:{room}", json.dumps(
                {**msg, "room": room, "_origin": INSTANCE_ID}, default=str
            ))
        except Exception as e:
            logger.warning("Redis 发布失败: %s", e)

    async def ensure_subscriber(self):
        """启动 Redis 订阅循环（仅 Redis 模式）。同一频道多房间由 publish 的 room 字段路由。"""
        if self._started:
            return
        r = await get_redis()
        if r is None:
            return
        self._started = True
        # 用 pattern 订阅所有房间频道
        pubsub = r.pubsub()
        await pubsub.psubscribe("mde:presence:*")
        self._pubsubs.add(pubsub)
        asyncio.create_task(self._consume_pubsub(pubsub))

    async def _consume_pubsub(self, pubsub):
        try:
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                try:
                    msg = json.loads(message["data"])
                except Exception:
                    continue
                # 跳过本实例自己发布的消息（调用方已在本地分发，避免回声）
                if msg.pop("_origin", None) == INSTANCE_ID:
                    continue
                chan = message.get("channel", "")
                room = msg.get("room", "") or (chan.split("mde:presence:", 1)[-1] if "mde:presence:" in chan else "")
                if not room:
                    continue
                local = self._local_dispatch.get(room)
                if local:
                    try:
                        await local(room, msg)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("pubsub 消费异常: %s", e)


presence_bus = PresenceBus()


# ==================== 共享速率限制 ====================
# Redis 模式：INCR + EXPIRE 实现跨实例计数（多副本共享同一限流窗口）。
# 无 Redis：回退进程内滑动窗口（单实例部署够用，多实例下限流会按实例数放大）。
_local_rate_store: dict[str, list[float]] = defaultdict(list)


async def allow_rate(key: str, max_count: int, window: float) -> bool:
    """共享速率限制：返回 True 放行（未超限），False 超限。

    key: 限流维度键（如 ip:1.2.3.4 或 /api/ai/chat:uid）
    max_count: 窗口内允许次数
    window: 窗口秒数
    """
    r = await get_redis()
    if r is not None:
        try:
            rk = f"mde:rate:{key}"
            cnt = await r.incr(rk)
            if cnt == 1:
                await r.expire(rk, int(window))
            return cnt <= max_count
        except Exception as e:
            logger.warning("Redis 限流失败回退进程内: %s", e)
    # 进程内滑动窗口回退
    now = time.time()
    arr = _local_rate_store[key]
    _local_rate_store[key] = [t for t in arr if now - t < window]
    if len(_local_rate_store[key]) >= max_count:
        return False
    _local_rate_store[key].append(now)
    return True
