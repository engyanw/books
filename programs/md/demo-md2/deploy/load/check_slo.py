#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 locust --json 输出，按 SLO 门禁判定 pass/fail。

SLO（nightly 基线，-u 20 -r 2 -t 30s）：
- 失败率 = 0（核心链路不得 5xx/连接错误）
- 全路由 p99 ≤ SLO_MAX_P99_MS（默认 2000ms；与 alerts.yml 的 p99 告警阈值对齐）
- /ready 在负载下 100% 成功

用法：
  locust ... --json | python deploy/load/check_slo.py
  locust ... --json > stats.json  # 离线
  python deploy/load/check_slo.py < stats.json
"""
import json
import os
import sys

SLO_MAX_P99_MS = float(os.environ.get("SLO_MAX_P99_MS", "2000"))
SLO_MAX_FAILURE_RATE = float(os.environ.get("SLO_MAX_FAILURE_RATE", "0.0"))


def _p99(entry):
    """locust --json 每条记录的 99 分位键名有版本差异（"99%"/"99"/"99.9%"）。取 99 分位。"""
    for k in ("99%", "99", "percentile_99", "response_time_percentile_99"):
        if k in entry and entry[k] is not None:
            try:
                return float(entry[k])
            except (TypeError, ValueError):
                continue
    return None


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("SLO FAIL: locust 无输出")
        return 1
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # locust 可能在 JSON 前后混入日志行：取首个 [ 到末尾 ]
        i, j = raw.find("["), raw.rfind("]")
        if i < 0 or j < 0:
            print("SLO FAIL: 无法解析 locust JSON")
            return 1
        try:
            data = json.loads(raw[i:j + 1])
        except json.JSONDecodeError:
            print("SLO FAIL: JSON 解析失败")
            return 1

    entries = data.get("stats", data) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        print("SLO FAIL: stats 非列表")
        return 1

    violations = []
    worst_p99 = 0.0
    total_req = 0
    total_fail = 0
    for e in entries:
        name = e.get("Name") or e.get("name") or e.get("path") or "?"
        nreq = e.get("Request Count") or e.get("num_requests") or e.get("requests") or 0
        nfail = e.get("Failure Count") or e.get("num_failures") or e.get("failures") or 0
        total_req += nreq
        total_fail += nfail
        rate = nfail / nreq if nreq else 0.0
        if rate > SLO_MAX_FAILURE_RATE:
            violations.append(f"{name}: 失败率 {rate:.1%}（{nfail}/{nreq}）")
        p99 = _p99(e)
        if p99 is not None:
            worst_p99 = max(worst_p99, p99)
            if p99 > SLO_MAX_P99_MS:
                violations.append(f"{name}: p99 {p99:.0f}ms > {SLO_MAX_P99_MS:.0f}ms")

    print(f"SLO 报告: 总请求 {total_req}  失败 {total_fail}  最高 p99 {worst_p99:.0f}ms  阈值 p99<{SLO_MAX_P99_MS:.0f}ms")
    if violations:
        print("SLO FAIL:")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("SLO PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
