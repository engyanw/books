#!/usr/bin/env bash
# HTTPS 开发模式启动后端（自签名）。
#
# 复用项目根 cert/dev-*.pem（CN=localhost，SAN: localhost + 127.0.0.1）。
# 浏览器首次访问需手动信任自签名证书；前端 vite proxy 已设 secure:false 可直连。
#
# 用法： ./dev-https.sh   （在 backend/ 目录下执行）
# 端口： 8443（HTTPS 开发惯例端口）

set -e
cd "$(dirname "$0")"

export WATCHFILES_FORCE_POLLING=true   # WSL2/Windows 挂载下避免 --reload 卡死

CERT_DIR="$(cd .. && pwd)/cert"
KEY="${CERT_DIR}/dev-key.pem"
CRT="${CERT_DIR}/dev-cert.pem"
if [ ! -f "$KEY" ] || [ ! -f "$CRT" ]; then
  echo "缺少证书：$KEY / $CRT" >&2
  echo "请先在项目根执行：openssl req -x509 -newkey rsa:2048 -nodes -keyout cert/dev-key.pem -out cert/dev-cert.pem -days 3650 -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'" >&2
  exit 1
fi

exec uvicorn main:app \
  --host 0.0.0.0 --port 8443 \
  --ssl-keyfile  "$KEY" \
  --ssl-certfile "$CRT" \
  --reload --timeout-graceful-shutdown 25
