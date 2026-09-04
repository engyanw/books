# -*- coding: utf-8 -*-
"""B5 回归：应用层 IP 白/黑名单。
覆盖：黑名单拒绝、白名单放行/拒绝、健康探针豁免、CIDR 匹配。
"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="ipf_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 仅放行 10.0.0.0/8 与 127.0.0.1；拒绝 6.6.6.6
os.environ["IP_ALLOWLIST"] = "10.0.0.0/8,127.0.0.1"
os.environ["IP_BLOCKLIST"] = "6.6.6.6"

import main  # noqa: E402

# 单元：匹配逻辑
assert main._ip_in_list("10.1.2.3", ["10.0.0.0/8"]) is True
assert main._ip_in_list("11.1.2.3", ["10.0.0.0/8"]) is False
assert main._ip_in_list("6.6.6.6", ["6.6.6.6"]) is True
print("ip matching OK")

with TestClient(main.app) as c:
    # 默认 testserver 客户端 IP 为 testclient（非 IP）。这里通过 X-Forwarded-For 模拟。
    # 白名单内的 IP（10.x）→ 放行
    r = c.get("/health", headers={"X-Forwarded-For": "10.1.2.3"})
    assert r.status_code == 200, r.text

    # 健康探针豁免：即使 IP 不在白名单也放行
    r = c.get("/health", headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 200, "健康探针应豁免 IP 过滤"

    # 非白名单 IP 访问普通 API → 403
    r = c.get("/api/auth/me", headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 403, r.text

    # 黑名单 IP → 403（即便在白名单也不该被放行——这里 6.6.6.6 不在白名单）
    r = c.get("/api/auth/me", headers={"X-Forwarded-For": "6.6.6.6"})
    assert r.status_code == 403, r.text

    # 白名单 IP 但访问需鉴权的 API → 401（IP 通过，但未带 token）
    r = c.get("/api/auth/me", headers={"X-Forwarded-For": "10.1.2.3"})
    assert r.status_code == 401, r.text

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
