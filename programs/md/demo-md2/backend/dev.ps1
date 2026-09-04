# 开发模式启动后端（PowerShell）
#
# 在 WSL2 下项目位于 Windows 挂载（C:\ ...，9p/DrvFs）时，inotify 不可靠，
# uvicorn --reload 会在 "WatchFiles detected changes ... Finished server process"
# 之后卡住、不再拉起新进程。强制 watchfiles 轮询可避免此问题。
#
# 用法：
#   1) 若用虚拟环境，先激活： .venv\Scripts\Activate.ps1
#   2) 在 backend 目录执行：  .\dev.ps1
#   或从仓库根目录执行：       powershell -ExecutionPolicy Bypass -File backend\dev.ps1

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$env:WATCHFILES_FORCE_POLLING = 'true'

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
