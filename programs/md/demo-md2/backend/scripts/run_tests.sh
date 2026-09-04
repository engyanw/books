#!/usr/bin/env bash
# 运行全部后端集成测试。
# 每个测试文件在模块顶部设置独立环境变量后 import main，
# 因此必须作为独立子进程运行（同进程 import main 只生效一次）。
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
ran=0
for t in test_*.py; do
  [ -f "$t" ] || continue
  ran=$((ran + 1))
  if python "$t" >/tmp/mde_test_$$.out 2>&1; then
    echo "  ✓ $t"
  else
    echo "  ✗ $t"
    cat /tmp/mde_test_$$.out | sed 's/^/      /'
    fail=$((fail + 1))
  fi
done
rm -f /tmp/mde_test_$$.out
echo "-----------------------------------"
echo "运行 $ran 个测试文件，失败 $fail 个"
[ "$fail" -eq 0 ] || exit 1
