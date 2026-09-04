#!/usr/bin/env bash
# 开发模式启动后端。
#
# 在 WSL2 下，若项目位于 Windows 挂载（/mnt/c ...，9p/DrvFs），inotify 不可靠，
# uvicorn --reload 会出现在 "WatchFiles detected changes ... Finished server process"
# 之后卡住、不再拉起新进程的问题。强制 watchfiles 轮询可避免此问题。
#
# 用法： ./dev.sh   （在 backend/ 目录下执行）

set -e
cd "$(dirname "$0")"

export WATCHFILES_FORCE_POLLING=true

exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload --timeout-graceful-shutdown 25
