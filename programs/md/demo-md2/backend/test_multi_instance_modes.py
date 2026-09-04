# -*- coding: utf-8 -*-
"""#6 多实例失效模式 回归套件（验证既有约束，锁紧失效行为）。

覆盖多实例部署的关键失效模式（既有代码已实现，本测试锁定以防退化）：
  1. 默认单实例：_am_leader() 恒 True（LEADER_ELECTION_ENABLED 关闭）。
  2. SQLite leader CAS（无 Redis，选举开启）：首实例获取租约；第二实例在租约期内被拒，
     租约过期后可接管。
  3. REDIS_REQUIRED=1 但无 REDIS_URL：限流退化为进程内计数（不抛、不静默放大），
     _check_rate_limit / _check_endpoint_rate_limit 均放行且记录降级。
  4. _storage_mode_info：返回 backend/multi_instance/unsafe/recommendation 结构。
  5. MULTI_INSTANCE_STRICT=1 + 不一致拓扑（leader 选举开 + sqlite + 非共享 FS）→
     子进程 asyncio.run(main._startup()) 抛 RuntimeError（拒绝启动而非静默降级）。
"""
import os, shutil, tempfile, asyncio, subprocess, sys
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="mi_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"

import main  # noqa: E402

with TestClient(main.app) as c:  # 触发 startup：初始化 registry 库 + leader_lease 表
    # --- 1) 默认单实例：_am_leader 恒 True ---
    assert main.LEADER_ELECTION_ENABLED is False, "默认应关闭 leader 选举"
    assert asyncio.run(main._am_leader()) is True, "单实例下 _am_leader 应恒 True"
    assert main._ops_state["leader_is_leader"] == 1, main._ops_state

    # --- 4) _storage_mode_info 结构（默认 sqlite 单实例，非多实例，安全）---
    info = main._storage_mode_info()
    for k in ("backend", "multi_instance", "unsafe", "recommendation"):
        assert k in info, info
    assert info["multi_instance"] is False, info
    assert info["unsafe"] is False, info
    print("storage_mode_info OK:", {k: info[k] for k in ("backend", "multi_instance", "unsafe", "recommendation")})

    # --- 2) SQLite leader CAS（开启选举 + 无 Redis）---
    main.LEADER_ELECTION_ENABLED = True

    async def _clear_lease():
        async with main._registry_transaction() as db:
            await db.execute("DELETE FROM leader_lease WHERE id=1")
    asyncio.run(_clear_lease())

    orig_inst = main._INSTANCE_ID
    # 首实例获取租约
    got = asyncio.run(main._renew_leader_lease())
    assert got is True, "首实例应获取 leader 租约"
    # 第二实例（不同 instance_id）在租约期内被拒
    main._INSTANCE_ID = "other-instance-xxxx"
    got2 = asyncio.run(main._renew_leader_lease())
    assert got2 is False, "租约未过期时第二实例不应抢到 leader"
    # 让租约过期 → 第二实例接管
    async def _expire_lease():
        import time as _t
        async with main._registry_transaction() as db:
            await db.execute("UPDATE leader_lease SET expires_at=? WHERE id=1", (str(int(_t.time()) - 10),))
    asyncio.run(_expire_lease())
    got3 = asyncio.run(main._renew_leader_lease())
    assert got3 is True, "租约过期后第二实例应接管 leader"

    async def _holder():
        async with main._registry_transaction() as db:
            r = await (await db.execute("SELECT holder FROM leader_lease WHERE id=1")).fetchone()
            return r["holder"] if r else None
    assert asyncio.run(_holder()) == "other-instance-xxxx", "holder 应为接管实例"
    main._INSTANCE_ID = orig_inst
    main.LEADER_ELECTION_ENABLED = False
    print("leader CAS OK")

    # --- 3) REDIS_REQUIRED=1 + 无 REDIS_URL：限流降级（进程内），不抛 ---
    saved_req, saved_url = main.REDIS_REQUIRED, main.REDIS_URL
    main.REDIS_REQUIRED = True
    main.REDIS_URL = ""
    try:
        main._rate_warn_throttle = 0.0
        ok = asyncio.run(main._check_rate_limit("9.9.9.9"))
        assert ok is True, "无 Redis 时限流应退化为进程内放行（不抛、不阻断）"
        ok2 = asyncio.run(main._check_endpoint_rate_limit("u", "/api/upload"))
        assert ok2 is True, "端点限流同样退化为进程内"
    finally:
        main.REDIS_REQUIRED, main.REDIS_URL = saved_req, saved_url
    print("redis-required degrade OK")

# --- 5) MULTI_INSTANCE_STRICT=1 + 不一致拓扑 → _startup() 抛 RuntimeError ---
strict_py = """
import os, sys, tempfile, asyncio
os.environ["DOC_DATA_DIR"] = tempfile.mkdtemp()
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"
os.environ["LEADER_ELECTION_ENABLED"] = "true"      # 多实例
os.environ["MULTI_INSTANCE_STRICT"] = "true"        # 严格：不一致即拒（config 校验 =="true"）
os.environ["DOC_DATA_DIR_SHARED"] = "false"          # sqlite + 非共享 FS = 不安全
import main
rejected = False
try:
    asyncio.run(main._startup())
    print("STARTED-OK", flush=True)
except RuntimeError as e:
    print("REJECTED:", str(e)[:80], flush=True)
    rejected = True
# 强制退出：_startup 初始化的 sqlite 连接池有 idle 连接，正常退出会卡 atexit；
# 测试只关心 guard 是否抛 RuntimeError，用 os._exit 绕过清理（先 flush 输出）。
sys.stdout.flush()
os._exit(0 if rejected else 1)
"""
env = {**os.environ, "PYTHONPATH": os.path.dirname(os.path.abspath(main.__file__))}
r = subprocess.run([sys.executable, "-c", strict_py], capture_output=True, text=True, timeout=90, env=env)
out = (r.stdout or "") + (r.stderr or "")
assert "REJECTED" in out, f"严格模式应拒绝启动；实际输出：{out!r}"
assert "多实例" in out, out
print("strict-reject OK:", [ln for ln in out.splitlines() if ln.startswith("REJECTED")][0])

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
