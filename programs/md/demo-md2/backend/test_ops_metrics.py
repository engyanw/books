# -*- coding: utf-8 -*-
"""P1-3 运维指标暴露：/metrics 应输出 RED 指标 + 备份/leader 运维状态。
- http_requests_total / http_errors_total / http_request_duration_seconds_*（observability）
- md_backup_last_success_timestamp / _failure_timestamp / md_backup_failures_total
- md_leader_is_leader / md_leader_changes_total
- 连接池 gauge：md_total_idle_connections(_limit) / md_user_pool_entries
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="opsm_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

with TestClient(main.app) as c:
    # 触发一次被观测的请求以累计 RED 指标（/ready /metrics 自身被跳过避免自激）
    c.get("/api/languages")
    body = c.get("/metrics").text

    # RED 指标（observability 模块）
    assert "http_requests_total" in body, body
    assert "http_errors_total" in body, body
    assert "http_request_duration_seconds_bucket" in body, body

    # 运维状态（_ops_state，本测试未跑备份/leader 循环，仅断言字段已暴露）
    assert "md_backup_last_success_timestamp" in body, body
    assert "md_backup_last_failure_timestamp" in body, body
    assert "md_backup_failures_total" in body, body
    assert "md_leader_is_leader" in body, body
    assert "md_leader_changes_total" in body, body
    # 未启用选举 → leader_is_leader 应为 1
    for line in body.splitlines():
        if line.startswith("md_leader_is_leader"):
            assert line.split()[-1] == "1", line
        if line.startswith("md_backup_failures_total"):
            assert line.split()[-1] == "0", line

    # 连接池 gauge
    assert "md_total_idle_connections" in body, body
    assert "md_total_idle_connections_limit" in body, body
    assert "md_user_pool_entries" in body, body

    # 手动模拟一次备份成功/失败 → _ops_state 更新 → /metrics 反映
    main._ops_state["backup_last_success"] = 1700000000.0
    main._ops_state["backup_failures"] = 2
    main._ops_state["leader_changes"] = 3
    body2 = c.get("/metrics").text
    for line in body2.splitlines():
        if line.startswith("md_backup_last_success_timestamp"):
            assert line.split()[-1] == "1700000000.0", line
        if line.startswith("md_backup_failures_total"):
            assert line.split()[-1] == "2", line
        if line.startswith("md_leader_changes_total"):
            assert line.split()[-1] == "3", line

print("ALL PASSED")
