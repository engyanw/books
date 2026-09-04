#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# SLO 负载基线运行器：拉起后端 → 跑 locust headless → 管道给 check_slo.py 判定门禁。
# 用于本地复现与 nightly CI。失败（任一 SLO 违例）→ 非 0 退出，CI 标红。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$ROOT/backend"
HOST="http://127.0.0.1:8000"
USERS="${SLO_USERS:-20}"
RATE="${SLO_RATE:-2}"
RUN_TIME="${SLO_RUN_TIME:-30s}"
MAX_P99="${SLO_MAX_P99_MS:-2000}"

# --- 后端：干净临时数据目录 + 允许注册 ---
export AUTH_ALLOW_REGISTER=true
export DOC_DATA_DIR="${DOC_DATA_DIR:-/tmp/md2_slo_data}"
export REGISTRY_DB_PATH="$DOC_DATA_DIR/registry.db"
export DOC_DB_PATH="$DOC_DATA_DIR/legacy.db"
export PYTHONUNBUFFERED=1
rm -rf "$DOC_DATA_DIR"; mkdir -p "$DOC_DATA_DIR"

echo "[baseline] 启动后端 uvicorn ..."
( cd "$BACKEND" && exec python -m uvicorn main:app --host 127.0.0.1 --port 8000 ) &
BACKEND_PID=$!
cleanup() { kill "$BACKEND_PID" 2>/dev/null || true; wait "$BACKEND_PID" 2>/dev/null || true; }
trap cleanup EXIT

# 轮询 /ready 等待就绪（最多 40s）
for _ in $(seq 1 40); do
  if curl -sf "$HOST/ready" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -sf "$HOST/ready" >/dev/null || { echo "[baseline] 后端未就绪"; exit 1; }

echo "[baseline] locust: -u $USERS -r $RATE -t $RUN_TIME (p99 阈值 ${MAX_P99}ms)"
python -m locust -f "$ROOT/deploy/load/locustfile.py" --host "$HOST" \
  --headless -u "$USERS" -r "$RATE" -t "$RUN_TIME" --json 2>/dev/null \
  | SLO_MAX_P99_MS="$MAX_P99" python "$ROOT/deploy/load/check_slo.py"
