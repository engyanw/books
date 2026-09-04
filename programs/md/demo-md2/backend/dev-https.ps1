# HTTPS 开发模式启动后端（PowerShell，自签名证书）
#
# ⚠️ Windows 已知限制：uvicorn 原生 SSL（asyncio ssl）在 Windows 上做服务端时，
#   可能对 schannel(curl) / openssl(node/vite) 客户端都出现"连接被服务端 abrupt 关闭、
#   missing close_notify"（curl 56 / vite socket hang up），即便 --reload 去掉也一样。
#   这是 uvicorn+asyncio-SSL 在 Windows 的互操作问题，非应用/证书问题。
#   → dev 期推荐改用：.\dev.ps1（HTTP 后端）+ 前端 vite https（vite 自带证书），
#     浏览器看到的仍是 https，满足安全上下文/远程访问；后端只在 vite 服务端经回环 http 转发。
#   → 生产用 nginx/Caddy 终止 TLS（Linux+openssl），无此问题。
#   本脚本仅在 SSL 能正常握手的环境（如 Linux）下使用。
#
# 复用项目根 cert\dev-*.pem（CN=localhost，SAN: localhost + 127.0.0.1）。
# 浏览器首次访问需手动信任自签名证书；前端 vite proxy 已设 secure:false 可直连。
#
# 用法：
#   1) 若用虚拟环境，先激活： .venv\Scripts\Activate.ps1   （否则需 uvicorn 在 PATH）
#   2) 在 backend 目录执行：  .\dev-https.ps1
#   或从仓库根目录执行：       powershell -ExecutionPolicy Bypass -File backend\dev-https.ps1
# 端口： 8443（HTTPS 开发惯例端口）

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$env:WATCHFILES_FORCE_POLLING = 'true'   # WSL2/Windows 挂载下避免 --reload 卡死

# --- 自签名证书路径（与前端 vite 共用）---
$CertDir  = Join-Path (Split-Path $PSScriptRoot -Parent) 'cert'
$KeyFile  = Join-Path $CertDir 'dev-key.pem'
$CertFile = Join-Path $CertDir 'dev-cert.pem'
if (-not (Test-Path -LiteralPath $KeyFile) -or -not (Test-Path -LiteralPath $CertFile)) {
    Write-Host "缺少证书：$KeyFile / $CertFile" -ForegroundColor Red
    Write-Host "在项目根执行（含局域网IP以避免远程访问证书名不匹配）：" -ForegroundColor Yellow
    Write-Host "  openssl req -x509 -newkey rsa:2048 -nodes -keyout cert/dev-key.pem -out cert/dev-cert.pem -days 825 -subj `"/CN=localhost`" -addext `"subjectAltName=DNS:localhost,IP:127.0.0.1,IP:<你的局域网IP>`""
    exit 1
}

Write-Host "启动 HTTPS uvicorn -> https://0.0.0.0:8443" -ForegroundColor Cyan
Write-Host "  cert: $CertFile" -ForegroundColor DarkGray

uvicorn main:app --host 0.0.0.0 --port 8443 --ssl-keyfile $KeyFile --ssl-certfile $CertFile --reload --timeout-graceful-shutdown 25
