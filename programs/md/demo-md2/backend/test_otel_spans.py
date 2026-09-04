# -*- coding: utf-8 -*-
"""#6 OTel 热路径埋点 回归。

验证关键路径已埋 span()（无 OTel SDK 时为 no-op，不抛、不影响行为）：
  auth.require_user、db.transaction、db.registry_transaction、db.team_transaction、
  ai.forward、collab.yjs_update、search.global。
"""
import os, shutil, tempfile, asyncio
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="otel_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"

import main  # noqa: E402
import observability  # noqa: E402


def test_span_noop():
    """span() 在无 OTel SDK 时返回 no-op 上下文，不抛、属性透传。"""
    # 默认未设 OTEL_EXPORTER_OTLP_ENDPOINT → tracer 为 None → no-op
    observability._tracer = None
    observability._tracing_checked = True  # 强制不探测 SDK
    with observability.span("test.span", attr="v", n=1) as s:
        assert s is not None
    # 也可作为普通上下文嵌套使用
    with observability.span("a"), observability.span("b"):
        pass
    # 观测计数仍工作
    observability.observe_request("GET", "/api/docs", 200, 0.012)
    snap = observability.snapshot()
    assert snap["total_requests"] >= 1, snap
    print("span no-op OK")


test_span_noop()

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "u", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "u", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # auth.require_user → db.transaction → 创建文档（事务 span 嵌套）
    did = c.post("/api/docs", headers=h, json={"title": "t", "content": "# body"}).json()["doc_id"]
    # db.registry_transaction：/api/docs 列表 / 团队查询都会过 registry 事务
    assert c.get("/api/docs", headers=h).status_code == 200

    # search.global：搜索走 global_search（含 span）
    assert c.get(f"/api/search?q=body&limit=20", headers=h).status_code == 200

    # ai.forward span：直接调 _ai_forward（不可达上游），验证 span 包裹的转发返回错误体而不抛
    os.environ["AI_PROXY_TIMEOUT"] = "2"
    res = asyncio.run(main._ai_forward(
        "http://127.0.0.1:9/none", "k", "m",
        [{"role": "user", "content": "hi"}], log_user="u"))
    assert res["ok"] is False, res  # 不可达上游 → ok=False（非崩溃）

    # collab.yjs_update span：ws 增量分支（仅断言 span 存在且函数可导入，不强制建连——WS 在 TestClient 下另测）
    # 这里只验证 span 已在源码埋点（通过 import 不可达路径无异常即可）
    import inspect
    src = inspect.getsource(main)
    assert 'span("collab.yjs_update"' in src, "collab ws span 未埋点"
    assert 'span("auth.require_user"' in src, "auth span 未埋点"
    assert 'span("ai.forward"' in src, "ai span 未埋点"
    assert 'span("db.transaction"' in src, "db.transaction span 未埋点"
    assert 'span("db.registry_transaction"' in src, "registry_transaction span 未埋点"
    assert 'span("db.team_transaction"' in src, "team_transaction span 未埋点"
    assert 'span("search.global"' in src, "search.global span 未埋点"

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
