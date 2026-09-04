# -*- coding: utf-8 -*-
"""A1 回归：SQLite per-user 连接池 LRU 全局上限。

模拟 >MAX_USER_POOLS 个用户访问，断言：
  - 池数量收缩到上限内；
  - 全局 idle 连接数封顶；
  - 被淘汰用户下次访问可幂等重建并正常读写。
"""
import os, shutil, tempfile, asyncio

TMP = tempfile.mkdtemp(prefix="poollru_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 小上限以便测试快速触发淘汰
os.environ["MAX_USER_POOLS"] = "5"
os.environ["MAX_TEAM_POOLS"] = "3"
os.environ["MAX_TOTAL_IDLE_CONNECTIONS"] = "20"
os.environ["USER_DB_POOL_SIZE"] = "2"

import main  # noqa: E402


async def _scenario():
    N = 12  # > MAX_USER_POOLS(5)
    # 每个用户取连接再归还，模拟并发访问后释放
    for i in range(N):
        uid = f"u{i}"
        db = await main._get_db(uid)
        # 确认连接可用
        row = await db.execute("SELECT 1 AS v")
        rec = await row.fetchone()
        assert rec["v"] == 1
        await main._put_db(uid, db)

    # 1) 池数量收缩到上限内
    assert len(main._user_db_pools) <= main.MAX_USER_POOLS, (
        f"用户池数量 {len(main._user_db_pools)} 超上限 {main.MAX_USER_POOLS}")
    # 2) 全局 idle 封顶
    idle = main._total_idle_connections()
    assert idle <= main.MAX_TOTAL_IDLE_CONNECTIONS, (
        f"全局 idle {idle} 超上限 {main.MAX_TOTAL_IDLE_CONNECTIONS}")

    # 3) 被淘汰用户重建可读：取一个大概率被淘汰的早期用户
    evicted_uid = "u0"
    # u0 若仍在池中，强制淘汰它以便测试重建路径
    if evicted_uid in main._user_db_pools:
        pool = main._user_db_pools.pop(evicted_uid)
        await main._close_pool_entries(pool)
        main._user_db_initialized.discard(evicted_uid)
    assert evicted_uid not in main._user_db_pools

    db = await main._get_db(evicted_uid)  # 重建
    row = await db.execute("SELECT 42 AS v")
    rec = await row.fetchone()
    assert rec["v"] == 42
    await main._put_db(evicted_uid, db)
    assert evicted_uid in main._user_db_pools

    # 4) LRU 顺序：最近访问的应在尾部
    assert list(main._user_db_pools)[-1] == evicted_uid

    # 5) 团队池同样封顶
    for i in range(8):
        tid = f"t{i}"
        db = await main._get_team_db(tid)
        await main._put_team_db(tid, db)
    assert len(main._team_db_pools) <= main.MAX_TEAM_POOLS, (
        f"团队池数量 {len(main._team_db_pools)} 超上限 {main.MAX_TEAM_POOLS}")


    # 5) 团队池同样封顶
    for i in range(8):
        tid = f"t{i}"
        db = await main._get_team_db(tid)
        await main._put_team_db(tid, db)
    assert len(main._team_db_pools) <= main.MAX_TEAM_POOLS, (
        f"团队池数量 {len(main._team_db_pools)} 超上限 {main.MAX_TEAM_POOLS}")


async def _run():
    try:
        await _scenario()
        print("ALL PASSED")
    finally:
        # 关闭所有连接，避免 aiosqlite 后台线程阻塞进程退出
        await main._shutdown()


asyncio.run(_run())
shutil.rmtree(TMP, ignore_errors=True)
