# -*- coding: utf-8 -*-
"""A3 回归：优雅关闭——后台任务在 shutdown 时被取消并 drain。
"""
import os, shutil, tempfile, asyncio
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="grace_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402
from main import app  # noqa: E402

# 启动前注入一个可观测的后台任务，验证 shutdown 会 cancel 它
_external_cancelled = {"v": False}


async def _observable_loop():
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        _external_cancelled["v"] = True
        raise


# 通过额外的 startup handler 把可观测任务挂到 lifespan loop 上
@app.on_event("startup")
async def _inject_observable():
    t = asyncio.create_task(_observable_loop())
    main._bg_tasks.append(t)


with TestClient(main.app) as c:
    # lifespan startup 已创建标准后台任务 + 注入的可观测任务
    assert c.get("/ready").status_code == 200
    assert len(main._bg_tasks) >= 2, f"后台任务数 {len(main._bg_tasks)}"

# TestClient 上下文退出 → 触发 shutdown（cancel + wait + 关池）
assert _external_cancelled["v"] is True, "注入的后台任务未被取消"
assert main._bg_tasks == [], "shutdown 后 _bg_tasks 未清空"

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
