# -*- coding: utf-8 -*-
"""A2 回归：/ready 就绪探针。
正常 → 200 ready；DB 不可达 → 503 not_ready。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="ready_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    # 正常：DB 可达，Redis 未配置（视为非必需）→ 200 ready
    r = c.get("/ready")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ready", body
    assert body["checks"]["db"] is True, body
    # Redis 未配置 → None（非必需）
    assert body["checks"]["redis"] is None, body

    # /ready 不进入 RED 指标采集（skip 集），仅校验不报错即可
    assert c.get("/metrics").status_code == 200

    # 模拟 DB 故障：monkeypatch 使 registry 取连接抛错
    import aiosqlite
    _orig_get = main._get_registry_db

    async def _broken_get():
        raise RuntimeError("DB unreachable")

    main._get_registry_db = _broken_get
    try:
        r2 = c.get("/ready")
    finally:
        main._get_registry_db = _orig_get
    assert r2.status_code == 503, r2.text
    body2 = r2.json()
    assert body2["status"] == "not_ready", body2
    assert body2["checks"]["db"] is False, body2

    # 恢复后再次就绪
    assert c.get("/ready").status_code == 200

    # /health 仍存活（进程级，不校验依赖）
    assert c.get("/health").status_code == 200

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
