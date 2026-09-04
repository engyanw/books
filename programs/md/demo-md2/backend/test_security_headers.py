# -*- coding: utf-8 -*-
"""安全响应头中间件：CSP/HSTS/X-Frame-Options 等默认下发。"""
import os, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="sec_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["SECURITY_HEADERS_ENABLED"] = "true"

import main  # noqa: E402

with TestClient(main.app) as c:
    # /health 是纯 JSON 端点，便于断言响应头
    r = c.get("/health")
    assert r.status_code == 200, r.text
    assert r.headers.get("x-content-type-options") == "nosniff", "缺 X-Content-Type-Options"
    assert r.headers.get("x-frame-options") == "SAMEORIGIN", "缺 X-Frame-Options"
    assert "strict-origin-when-cross-origin" in r.headers.get("referrer-policy", ""), "缺 Referrer-Policy"
    csp = r.headers.get("content-security-policy", "")
    assert "default-src" in csp and "object-src 'none'" in csp, f"CSP 不完整: {csp}"
    assert "geolocation=()" in r.headers.get("permissions-policy", ""), "缺 Permissions-Policy"
    # HSTS 仅 https 下下发；TestClient 走 http，故不应出现
    assert "strict-transport-security" not in {k.lower() for k in r.headers}, "http 下不应下发 HSTS"

    # 禁用开关生效
    main.SECURITY_HEADERS_ENABLED = False
    r2 = c.get("/health")
    assert "content-security-policy" not in {k.lower() for k in r2.headers}, "禁用后不应再下发 CSP"
    main.SECURITY_HEADERS_ENABLED = True

print("ALL PASSED")
