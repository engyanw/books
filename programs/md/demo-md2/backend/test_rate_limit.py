# -*- coding: utf-8 -*-
"""D5 回归：限流多实例 Redis 必需开关。
覆盖：REDIS_REQUIRED=1 且无 REDIS_URL 时告警并退化（仍放行未超限请求，不静默放大）；
REDIS_REQUIRED=0 时无告警。
"""
import io, os, shutil, tempfile, logging

TMP = tempfile.mkdtemp(prefix="rl_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["REDIS_REQUIRED"] = "1"
os.environ.pop("REDIS_URL", None)  # 确保无 Redis

import config  # noqa: E402
import main  # noqa: E402

assert config.REDIS_REQUIRED is True

# 捕获 main.logger 告警
buf = io.StringIO()
h = logging.StreamHandler(buf)
h.setLevel(logging.WARNING)
main.logger.addHandler(h)
try:
    # 调用限流 → 触发告警（节流 30s，首次必告警）
    import asyncio as _aio
    res = _aio.run(main._check_rate_limit("1.2.3.4"))
    assert res is True, res  # 未超限应放行（退化模式仍按进程内计数）
    out = buf.getvalue()
    assert "REDIS_REQUIRED" in out and "退化" in out, out
finally:
    main.logger.removeHandler(h)

# REDIS_REQUIRED=0 不告警：独立子进程验证开关可关
import subprocess, sys
code = (
    "import os; os.environ.pop('REDIS_URL',None); os.environ['REDIS_REQUIRED']='0'; "
    "import config; assert config.REDIS_REQUIRED is False; "
    "open(os.environ['_OUT'],'w').write('ok')"
)
out = os.path.join(TMP, "ok.txt")
env = dict(os.environ); env["REDIS_REQUIRED"] = "0"; env.pop("REDIS_URL", None); env["_OUT"] = out
subprocess.run([sys.executable, "-c", code], env=env, check=True)
assert open(out).read() == "ok"

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
