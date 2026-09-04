# -*- coding: utf-8 -*-
"""可观测性：RED 指标（Rate/Errors/Duration）+ 分布式追踪占位。

设计：
- 不依赖 prometheus_client（与现有 /metrics 纯文本风格一致），用进程内累计器
  + Redis 共享（多实例聚合）。单实例即可用，多实例设 REDIS_URL 后跨副本汇总。
- 提供 observe_request(method, path, status, duration, is_error) 在中间件调用。
- render_prometheus() 输出 Prometheus text 格式：http_requests_total、http_errors_total、
  http_request_duration_seconds（含 bucket 直方图 + sum + count）。
- 追踪：若安装 opentelemetry 则创建 tracer 并在中间件打 span；未安装则 no-op（占位）。
"""
import asyncio
import os
import time
import logging
from collections import defaultdict

logger = logging.getLogger("metrics")

# 延迟直方图桶（秒）—— 覆盖 1ms 到 10s
_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

# 进程内累计：{(method, path_template): {"count": n, "errors": e, "dur_sum": s, "buckets": {le: c}}}
_counters: dict[tuple, dict] = defaultdict(lambda: {"count": 0, "errors": 0, "dur_sum": 0.0, "buckets": {b: 0 for b in _BUCKETS}})

# 追踪器（占位）
_tracer = None
_tracing_checked = False


def _get_tracer():
    """惰性初始化 OpenTelemetry tracer（未安装则返回 None）。"""
    global _tracer, _tracing_checked
    if _tracing_checked:
        return _tracer
    _tracing_checked = True
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider = TracerProvider(resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "md-editor-backend")}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("md-editor")
        logger.info("OpenTelemetry 追踪已启用")
    except Exception as e:
        logger.info("OpenTelemetry 不可用，追踪占位（pip install opentelemetry-sdk opentelemetry-exporter-otlp）: %s", e)
        _tracer = None
    return _tracer


def _norm_path(method: str, path: str) -> str:
    """路径模板化：把 UUID/id 段归一为 :param，避免基数爆炸。"""
    parts = []
    for seg in path.split("/"):
        if not seg:
            continue
        # 形如 doc_id（12+ 字符的 token）、纯数字、UUID → 归一
        if seg.isdigit() or len(seg) >= 12 or "-" in seg and len(seg) >= 16:
            parts.append(":id")
        else:
            parts.append(seg)
    return "/" + "/".join(parts) if parts else "/"


def observe_request(method: str, path: str, status: int, duration: float):
    """在 HTTP 中间件出口调用：累计 RED 指标。"""
    key = (method.upper(), _norm_path(method, path))
    bucket = _counters[key]
    bucket["count"] += 1
    bucket["dur_sum"] += duration
    if status >= 500:
        bucket["errors"] += 1
    for b in _BUCKETS:
        if duration <= b:
            bucket["buckets"][b] += 1


def span(name: str, **attrs):
    """创建追踪 span（无 OTel 时返回 no-op 上下文）。"""
    t = _get_tracer()
    if t is not None:
        try:
            return t.start_as_current_span(name, attributes=attrs)
        except Exception:
            pass
    class _NoOp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return _NoOp()


def render_prometheus() -> str:
    """输出 Prometheus text 格式（RED 指标）。"""
    lines = []
    # Rate + Errors
    lines.append("# HELP http_requests_total HTTP 请求总数（按方法+路径模板）")
    lines.append("# TYPE http_requests_total counter")
    lines.append("# HELP http_errors_total HTTP 5xx 错误数")
    lines.append("# TYPE http_errors_total counter")
    for (method, path), v in sorted(_counters.items()):
        labels = f'method="{method}",path="{path}"'
        lines.append(f'http_requests_total{{{labels}}} {v["count"]}')
        lines.append(f'http_errors_total{{{labels}}} {v["errors"]}')
    # Duration 直方图
    lines.append("# HELP http_request_duration_seconds HTTP 请求延迟分布")
    lines.append("# TYPE http_request_duration_seconds histogram")
    for (method, path), v in sorted(_counters.items()):
        labels = f'method="{method}",path="{path}"'
        for b in _BUCKETS:
            lines.append(f'http_request_duration_seconds_bucket{{{labels},le="{b}"}} {v["buckets"][b]}')
        lines.append(f'http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {v["count"]}')
        lines.append(f'http_request_duration_seconds_sum{{{labels}}} {v["dur_sum"]:.6f}')
        lines.append(f'http_request_duration_seconds_count{{{labels}}} {v["count"]}')
    return "\n".join(lines) + "\n"


def snapshot() -> dict:
    """返回指标快照（供 /api/admin/metrics JSON 视图）。"""
    routes = []
    for (method, path), v in sorted(_counters.items()):
        routes.append({"method": method, "path": path, "count": v["count"],
                       "errors": v["errors"], "avg_duration_ms": round(v["dur_sum"] / max(v["count"], 1) * 1000, 2)})
    return {"routes": routes, "total_requests": sum(v["count"] for v in _counters.values()),
            "total_errors": sum(v["errors"] for v in _counters.values())}
