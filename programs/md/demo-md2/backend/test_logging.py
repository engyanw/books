# -*- coding: utf-8 -*-
"""D3 回归：结构化 JSON 日志（LOG_JSON=1 时切 JSON formatter）。
覆盖：日志行可解析为 JSON；含 ts/level/logger/message；extra 字段透传；默认格式不受影响。
"""
import io, os, shutil, tempfile, json, logging

TMP = tempfile.mkdtemp(prefix="logjson_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["LOG_JSON"] = "1"  # 关键：导入前开启 JSON 日志

import config  # noqa: E402
import main  # noqa: E402

# 验证开关生效
assert config.LOG_JSON is True

# 挂一个捕获 handler（用 JSON formatter）到 root logger
buf = io.StringIO()
h = logging.StreamHandler(buf)
h.setFormatter(config._JsonFormatter())
h.setLevel(logging.INFO)
root = logging.getLogger()
root.addHandler(h)

try:
    main.logger.info("结构化测试", extra={"request_id": "rid-001", "user": "alice"})
    # 触发一条带异常的日志
    try:
        1 / 0
    except ZeroDivisionError:
        main.logger.exception("计算失败")

    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    assert lines, "无日志输出"
    first = json.loads(lines[0])
    assert first["message"] == "结构化测试", first
    assert first["level"] == "INFO", first
    assert first["logger"] == "sandbox-proxy", first
    assert first["request_id"] == "rid-001", first
    assert first["user"] == "alice", first
    assert first["ts"].endswith("Z"), first

    # 异常日志行含 exc 字段
    exc_line = json.loads(lines[1])
    assert exc_line["message"] == "计算失败"
    assert "exc" in exc_line and "ZeroDivisionError" in exc_line["exc"], exc_line
finally:
    root.removeHandler(h)

# 默认（非 JSON）格式不受影响：用一个独立进程验证
import subprocess, sys
code = (
    "import os; os.environ.pop('LOG_JSON', None); "
    "import config; "
    "import logging, io; "
    "b=io.StringIO(); h=logging.StreamHandler(b); "
    "logging.getLogger().addHandler(h); logging.getLogger().setLevel(logging.INFO); "
    "logging.getLogger('x').info('plain %s','msg'); "
    "open(os.environ['_OUT'],'w').write(b.getvalue())"
)
out = os.path.join(TMP, "plain.log")
env = dict(os.environ)
env.pop("LOG_JSON", None)
env["_OUT"] = out
subprocess.run([sys.executable, "-c", code], env=env, check=True)
plain = open(out).read()
assert "plain msg" in plain and plain.lstrip().startswith(("20", "[", "p")), repr(plain)
# 非 JSON 模式输出不应是合法 JSON 行
assert not plain.strip().startswith("{"), repr(plain)

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
