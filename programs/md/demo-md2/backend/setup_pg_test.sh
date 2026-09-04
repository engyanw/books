#!/bin/bash
# 一次性建立 PostgreSQL 测试库与角色（sudo -u postgres 走 peer 鉴权）
set -e
sudo -u postgres psql -p 5432 -c "DROP DATABASE IF EXISTS demo_md2_test;" || true
sudo -u postgres psql -p 5432 -c "DROP ROLE IF EXISTS demo_md2;" || true
sudo -u postgres psql -p 5432 -c "CREATE ROLE demo_md2 WITH LOGIN PASSWORD 'md2pass' SUPERUSER;"
sudo -u postgres psql -p 5432 -c "CREATE DATABASE demo_md2_test OWNER demo_md2;"
echo "PG test DB ready: postgresql://demo_md2:md2pass@127.0.0.1:5432/demo_md2_test"
