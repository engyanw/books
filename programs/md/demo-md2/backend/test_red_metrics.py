# -*- coding: utf-8 -*-
"""P1-B1：RED 指标（Rate/Errors/Duration）+ 分布式追踪占位 + 告警阈值。

验证：
- observe_request 累计请求计数/错误/延迟直方图
- render_prometheus 输出含 http_requests_total / http_errors_total / duration histogram
- snapshot 给出每路由 avg 延迟
- 5xx 计入 errors，4xx 不计
- span() 无 OTel 时为 no-op 不抛错
- 告警阈值：错误率/延迟超限可判定（_alert_check）
"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="red_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402
from observability import observe_request, render_prometheus, snapshot, span, _norm_path  # noqa: E402

# 1) 路径模板归一：id 段归一为 :id，避免基数爆炸
assert _norm_path("GET", "/api/docs/abc1234567890") == "/api/docs/:id", _norm_path("GET", "/api/docs/abc1234567890")
assert _norm_path("GET", "/api/docs") == "/api/docs"

# 2) observe_request 累计 + 5xx 计 errors，4xx 不计
observe_request("GET", "/api/docs", 200, 0.02)
observe_request("GET", "/api/docs", 200, 0.05)
observe_request("POST", "/api/docs", 500, 0.5)
observe_request("GET", "/api/docs/xyz1234567890", 404, 0.01)  # 4xx 不计 errors
snap = snapshot()
route_get = next(r for r in snap["routes"] if r["method"] == "GET" and r["path"] == "/api/docs")
assert route_get["count"] == 2 and route_get["errors"] == 0, route_get
route_post = next(r for r in snap["routes"] if r["method"] == "POST" and r["path"] == "/api/docs")
assert route_post["count"] == 1 and route_post["errors"] == 1, route_post
assert snap["total_errors"] == 1

# 3) render_prometheus 含 RED 指标
prom = render_prometheus()
assert "http_requests_total" in prom and "http_errors_total" in prom, prom
assert "http_request_duration_seconds_bucket" in prom and "http_request_duration_seconds_sum" in prom, prom
assert 'method="GET",path="/api/docs"' in prom, prom

# 4) span() 无 OTel 不抛错
with span("test.span", k="v"):
    pass

# 5) 端到端：经中间件的真实请求被计入 /metrics
with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "redu", "password": "pw123456"})
    c.post("/api/auth/login", json={"username": "redu", "password": "pw123456"})
    m = c.get("/metrics").text
    assert "http_requests_total" in m, m
    # 触发一个 5xx（访问不存在的路由 → 404，不计 errors；登录后访问 docs 计 200）
    # 这里验证 /api/auth/login 路由被记录
    assert "auth/login" in m, m

# 6) 告警阈值判定（错误率/平均延迟）
def _alert_check(snap, error_rate_pct=5, avg_latency_ms=2000):
    issues = []
    for r in snap["routes"]:
        rate = r["errors"] / r["count"] * 100 if r["count"] else 0
        if rate > error_rate_pct:
            issues.append(f"{r['method']} {r['path']} 错误率 {rate:.1f}% 超阈值 {error_rate_pct}%")
        if r["avg_duration_ms"] > avg_latency_ms:
            issues.append(f"{r['method']} {r['path']} 平均延迟 {r['avg_duration_ms']}ms 超阈值 {avg_latency_ms}ms")
    return issues

issues = _alert_check(snapshot())
assert any("POST /api/docs" in i and "错误率" in i for i in issues), issues  # 1/1=100% 错误率应告警

print("ALL PASSED")
