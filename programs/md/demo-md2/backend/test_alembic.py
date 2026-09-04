# -*- coding: utf-8 -*-
"""alembic 迁移框架：heads/stamp/upgrade 可用。"""
import os, tempfile, subprocess, sys

TMP = tempfile.mkdtemp(prefix="alb_")
REG = os.path.join(TMP, "registry.db")
# 测试进程自身也指向临时库（避免默认 data/registry.db 的 WSL 磁盘 I/O 问题）
os.environ["REGISTRY_DB_PATH"] = REG
os.environ["DOC_DATA_DIR"] = TMP
env = {**os.environ, "REGISTRY_DB_PATH": REG, "DOC_DATA_DIR": TMP}

def run(*args):
    return subprocess.run([sys.executable, "-m", "alembic", *args],
                          cwd=os.path.dirname(os.path.abspath(__file__)),
                          env=env, capture_output=True, text=True)

# heads 列出最新迁移
r = run("heads")
assert r.returncode == 0, r.stderr
assert "0003_registry_schema" in r.stdout, r.stdout

# stamp 到 head → 写入 alembic_version（head=最新迁移）
r = run("stamp", "head")
assert r.returncode == 0, r.stderr

import sqlite3
conn = sqlite3.connect(REG)
rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
conn.close()
assert rows == [("0003_registry_schema",)], rows

# 2) upgrade head：模拟一个 pre-0002 的库（有 users/teams 表但无 org_id），
# 先 stamp 到 0001 基线，再 upgrade head 应用 0002（org 隔离）。
import sqlite3
# 重建一个干净库，手工建 pre-0002 的 users/teams（无 org_id）
os.remove(REG)
conn = sqlite3.connect(REG)
conn.executescript("""
    CREATE TABLE users (user_id TEXT PRIMARY KEY, username TEXT, password_hash TEXT, created_at TEXT, is_admin INTEGER);
    CREATE TABLE teams (team_id TEXT PRIMARY KEY, name TEXT, slug TEXT, owner_user_id TEXT, created_at TEXT);
""")
conn.commit(); conn.close()

# stamp 0001（基线，不建表）
r = run("stamp", "0001_baseline")
assert r.returncode == 0, r.stderr + r.stdout

# upgrade head → 应用 0002（建 organizations + 给 users/teams 加 org_id）
r = run("upgrade", "head")
assert r.returncode == 0, r.stderr + r.stdout
conn2 = sqlite3.connect(REG)
tables = [t[0] for t in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
assert "organizations" in tables, tables
assert "org_id" in [c[1] for c in conn2.execute("PRAGMA table_info(users)").fetchall()]
assert "org_id" in [c[1] for c in conn2.execute("PRAGMA table_info(teams)").fetchall()]
ver = conn2.execute("SELECT version_num FROM alembic_version").fetchone()
conn2.close()
assert ver == ("0003_registry_schema",), ver

# 3) 全新空库（不预建任何表，不依赖应用运行时 DDL）→ alembic upgrade head
#    应构建完整注册库 schema，证明 alembic 真正接管表结构（C1）。
REG2 = os.path.join(TMP, "fresh.db")
env2 = {**env, "REGISTRY_DB_PATH": REG2}
r2 = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                    env=env2, capture_output=True, text=True)
assert r2.returncode == 0, r2.stderr + r2.stdout
conn3 = sqlite3.connect(REG2)
tables2 = [t[0] for t in conn3.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in ("users", "teams", "team_members", "team_roles", "audit_log", "notifications",
          "reviews", "review_steps", "workflow_definitions", "workflow_instances",
          "api_tokens", "revoked_tokens", "sessions", "organizations", "templates",
          "ai_usage", "collab_state", "shares", "webhooks"):
    assert t in tables2, f"alembic 未建表 {t}: {tables2}"
ver2 = conn3.execute("SELECT version_num FROM alembic_version").fetchone()
conn3.close()
assert ver2 == ("0003_registry_schema",), ver2

print("ALL PASSED")
