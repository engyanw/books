#!/bin/bash
# 建立非超级用户角色 md2_rls，用于验证 PG 行级安全（RLS）多租户隔离。
# demo_md2 是 SUPERUSER → 天然 BYPASSRLS，无法验证策略生效；
# md2_rls 为普通 LOGIN 角色，受 RLS 策略约束，故能证明"DB 层强制 org 隔离"。
#
# 用法：./setup_pg_rls.sh   （先运行 ./setup_pg_test.sh 建好 demo_md2_test 与 schema）
set -e

PSQL="sudo -u postgres psql -p 5432"

# 1) 角色（幂等：存在则改密/属性）
$PSQL -tAc "SELECT 1 FROM pg_roles WHERE rolname='md2_rls'" | grep -q 1 \
  && $PSQL -c "ALTER ROLE md2_rls WITH LOGIN PASSWORD 'rlspass' NOSUPERUSER NOBYPASSRLS;" \
  || $PSQL -c "CREATE ROLE md2_rls WITH LOGIN PASSWORD 'rlspass' NOSUPERUSER NOBYPASSRLS;"

# 2) 授予 schema 与表权限（RLS 表 + 读取 org 解析函数）
$PSQL -d demo_md2_test -c "GRANT USAGE ON SCHEMA public TO md2_rls;"
$PSQL -d demo_md2_test -c "GRANT SELECT, INSERT, UPDATE, DELETE ON users, teams, team_members, team_roles, audit_log, notifications TO md2_rls;"
# BIGSERIAL 序列权限（audit_log.id / notifications.id）
$PSQL -d demo_md2_test -c "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO md2_rls;"
# 可调用引导函数 app_resolve_org（默认 EXECUTE 已授 PUBLIC，显式确认）
$PSQL -d demo_md2_test -c "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO md2_rls;"

echo "RLS role ready: postgresql://md2_rls:rlspass@127.0.0.1:5432/demo_md2_test"
echo "提示：先确保 schema 已建（启动 app 或运行 test_pg.py 触发 _init_pg_schema）。"
