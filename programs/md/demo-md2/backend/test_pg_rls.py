# -*- coding: utf-8 -*-
"""P0-3 PG 行级安全（RLS）多租户隔离验证。

直接在 PG 上用两个非超级用户会话（角色 md2_rls）证明：
  - SET LOCAL app.org_id='orgA' 后只能看到 orgA 的 users/teams/audit_log 行；
  - 切到 orgB 后只能看到 orgB 的行；
  - 不设上下文（app.org_id 为空）则看不到任何 org 归属行（NULL≠''，严格策略）。
  - 超级用户 demo_md2 仍可见全部行（BYPASSRLS，保证现有 app 流程不受影响）。

前置：./setup_pg_test.sh + 启动 app 建 schema + ./setup_pg_rls.sh。
"""
import os, sys, traceback

DATABASE_URL = "postgresql://demo_md2:md2pass@127.0.0.1:5432/demo_md2_test"
RLS_URL = "postgresql://md2_rls:rlspass@127.0.0.1:5432/demo_md2_test"


def _rls_available() -> bool:
    """md2_rls 角色 + 授权是否就绪（需先 ./setup_pg_rls.sh）。未就绪则跳过，避免通用套件误报。"""
    try:
        import asyncio, asyncpg
        async def _p():
            c = await asyncpg.connect(RLS_URL)
            await c.close()
        asyncio.run(_p())
        return True
    except Exception:
        return False


if __name__ == "__main__" and not _rls_available():
    print("SKIP（md2_rls 角色未就绪：先运行 ./setup_pg_test.sh + 启动 app 建 schema + ./setup_pg_rls.sh）")
    raise SystemExit(0)
os.environ["DATABASE_URL"] = DATABASE_URL
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import asyncio
import asyncpg


async def _exec(dsn, sql, params=(), fetch=False):
    conn = await asyncpg.connect(dsn)
    try:
        if fetch:
            return await conn.fetch(sql, *params)
        await conn.execute(sql, *params)
        return None
    finally:
        await conn.close()


async def _rls_query(org_id, sql, params=()):
    """以 md2_rls 身份连接，事务内 SET LOCAL app.org_id 后查询。"""
    conn = await asyncpg.connect(RLS_URL)
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", org_id or "")
            return await conn.fetch(sql, *params)
    finally:
        await conn.close()


async def run():
    # 1) 超级用户：建 schema（触发 RLS DDL）—— 启动 app 即建；这里补建以确保幂等
    import main  # noqa: F401  导入即注册；lifespan 会 _init_pg_schema
    from fastapi.testclient import TestClient
    with TestClient(main.app):
        pass  # lifespan 完成建表 + RLS 策略 + 函数

    # 2) 超级用户写入两个 org 的样本数据（RLS 对超管无效）
    await _exec(DATABASE_URL, "DELETE FROM notifications WHERE org_id IN ('orgA','orgB')")
    await _exec(DATABASE_URL, "DELETE FROM audit_log WHERE org_id IN ('orgA','orgB')")
    await _exec(DATABASE_URL, "DELETE FROM team_members WHERE org_id IN ('orgA','orgB')")
    await _exec(DATABASE_URL, "DELETE FROM teams WHERE org_id IN ('orgA','orgB')")
    await _exec(DATABASE_URL, "DELETE FROM users WHERE org_id IN ('orgA','orgB')")

    await _exec(DATABASE_URL,
        "INSERT INTO users (user_id, username, password_hash, created_at, is_admin, org_id) "
        "VALUES ($1,$2,$3,NOW(),0,$4) ON CONFLICT (user_id) DO NOTHING",
        ("u_orgA", "rls_probe_a", "x", "orgA"))
    await _exec(DATABASE_URL,
        "INSERT INTO users (user_id, username, password_hash, created_at, is_admin, org_id) "
        "VALUES ($1,$2,$3,NOW(),0,$4) ON CONFLICT (user_id) DO NOTHING",
        ("u_orgB", "rls_probe_b", "x", "orgB"))
    await _exec(DATABASE_URL,
        "INSERT INTO teams (team_id, name, owner_user_id, created_at, org_id) "
        "VALUES ($1,$2,$3,NOW(),$4) ON CONFLICT (team_id) DO NOTHING",
        ("t_orgA", "TA", "u_orgA", "orgA"))
    await _exec(DATABASE_URL,
        "INSERT INTO teams (team_id, name, owner_user_id, created_at, org_id) "
        "VALUES ($1,$2,$3,NOW(),$4) ON CONFLICT (team_id) DO NOTHING",
        ("t_orgB", "TB", "u_orgB", "orgB"))
    await _exec(DATABASE_URL,
        "INSERT INTO audit_log (ts, user_id, action, org_id) VALUES (NOW(),$1,$2,$3)",
        ("u_orgA", "probe_a", "orgA"))
    await _exec(DATABASE_URL,
        "INSERT INTO audit_log (ts, user_id, action, org_id) VALUES (NOW(),$1,$2,$3)",
        ("u_orgB", "probe_b", "orgB"))

    # 3) orgA 视角：只能见 orgA 行
    a_users = await _rls_query("orgA", "SELECT user_id FROM users ORDER BY user_id")
    assert [r["user_id"] for r in a_users] == ["u_orgA"], a_users
    a_teams = await _rls_query("orgA", "SELECT team_id FROM teams ORDER BY team_id")
    assert [r["team_id"] for r in a_teams] == ["t_orgA"], a_teams
    a_audit = await _rls_query("orgA", "SELECT action FROM audit_log ORDER BY action")
    assert [r["action"] for r in a_audit] == ["probe_a"], a_audit

    # 4) orgB 视角：只能见 orgB 行（跨 org 不可见）
    b_users = await _rls_query("orgB", "SELECT user_id FROM users ORDER BY user_id")
    assert [r["user_id"] for r in b_users] == ["u_orgB"], b_users
    b_audit = await _rls_query("orgB", "SELECT action FROM audit_log ORDER BY action")
    assert [r["action"] for r in b_audit] == ["probe_b"], b_audit

    # 5) 不设上下文（空）：严格策略下 org 归属行均不可见
    none_audit = await _rls_query("", "SELECT action FROM audit_log WHERE org_id IN ('orgA','orgB')")
    assert len(none_audit) == 0, none_audit

    # 6) 引导函数：超管建的 app_resolve_org 旁路 RLS，md2_rls 可调用解析 org
    org_via_fn = await _rls_query("orgA", "SELECT app_resolve_org($1) AS o", ("u_orgB",))
    # 函数 SECURITY DEFINER 旁路 RLS → 即便在 orgA 上下文也能取到 u_orgB 的 org
    assert org_via_fn and org_via_fn[0]["o"] == "orgB", org_via_fn

    # 7) 超级用户仍可见全部（BYPASSRLS，保证 app 超管池不受影响）
    all_users = await _exec(DATABASE_URL, "SELECT count(*) AS c FROM users WHERE org_id IN ('orgA','orgB')", fetch=True)
    assert all_users and all_users[0]["c"] == 2, all_users

    # 清理
    await _exec(DATABASE_URL, "DELETE FROM notifications WHERE org_id IN ('orgA','orgB')")
    await _exec(DATABASE_URL, "DELETE FROM audit_log WHERE org_id IN ('orgA','orgB')")
    await _exec(DATABASE_URL, "DELETE FROM team_members WHERE org_id IN ('orgA','orgB')")
    await _exec(DATABASE_URL, "DELETE FROM teams WHERE org_id IN ('orgA','orgB')")
    await _exec(DATABASE_URL, "DELETE FROM users WHERE org_id IN ('orgA','orgB')")

    print("ALL PASSED")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
