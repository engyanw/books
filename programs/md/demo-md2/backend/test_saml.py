# -*- coding: utf-8 -*-
"""SAML 2.0 SP 流程：login→IdP→ACS→本地 token。dev 模式（不验签）+ mock IdP 断言。"""
import os, tempfile, base64, zlib, re
from urllib.parse import urlparse, parse_qs, urlencode
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="saml_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["SAML_SP_ENTITY_ID"] = "http://app.test/saml/metadata"
os.environ["SAML_ACS_URL"] = "http://app.test/api/auth/saml/acs"
os.environ["SAML_IDP_SSO_URL"] = "http://idp.test/sso"
os.environ["SAML_IDP_ENTITY_ID"] = "http://idp.test"
os.environ["SAML_VERIFY_SIGNATURE"] = "false"   # dev 模式：接受未签名断言
os.environ["OIDC_FRONTEND_URL"] = "/done"

import main  # noqa: E402


def build_response(nameid="saml-sub-001", username="saml_bob"):
    """构造一个最小可解析的 SAMLResponse（未签名）。"""
    rid = "id_" + "0" * 32
    now = "2026-08-14T10:00:00Z"
    xml = (
        f'<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
        f'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
        f'ID="{rid}" Version="2.0" IssueInstant="{now}" Destination="http://app.test/api/auth/saml/acs">'
        f'<saml:Issuer>http://idp.test</saml:Issuer>'
        f'<samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>'
        f'<saml:Assertion Version="2.0" ID="assert1" IssueInstant="{now}">'
        f'<saml:Issuer>http://idp.test</saml:Issuer>'
        f'<saml:Subject><saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified">{nameid}</saml:NameID></saml:Subject>'
        f'<saml:AttributeStatement>'
        f'<saml:Attribute Name="username"><saml:AttributeValue>{username}</saml:AttributeValue></saml:Attribute>'
        f'</saml:AttributeStatement>'
        f'</saml:Assertion>'
        f'</samlp:Response>'
    )
    return base64.b64encode(xml.encode("utf-8")).decode()


with TestClient(main.app) as c:
    # 1) metadata
    r = c.get("/api/auth/saml/metadata")
    assert r.status_code == 200 and "EntityDescriptor" in r.text and "AssertionConsumerService" in r.text

    # 2) login：302 到 IdP，带 SAMLRequest + RelayState
    r = c.get("/api/auth/saml/login", follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    loc = r.headers["location"]
    assert "idp.test/sso" in loc
    relay = parse_qs(urlparse(loc).query)["RelayState"][0]
    assert "SAMLRequest" in parse_qs(urlparse(loc).query)

    # 3) ACS：POST mock SAMLResponse + RelayState
    resp_b64 = build_response()
    r = c.post("/api/auth/saml/acs", data={"SAMLResponse": resp_b64, "RelayState": relay}, follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    loc2 = r.headers["location"]
    assert loc2.startswith("/done?"), loc2
    q = parse_qs(urlparse(loc2).query)
    token = q["token"][0]; uname = q["username"][0]
    assert uname == "saml_bob", uname

    # 4) token 可用
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["username"] == "saml_bob", me

    # 5) 同 NameID 复用用户（不新建）
    r2 = c.get("/api/auth/saml/login", follow_redirects=False)
    relay2 = parse_qs(urlparse(r2.headers["location"]).query)["RelayState"][0]
    r2 = c.post("/api/auth/saml/acs", data={"SAMLResponse": resp_b64, "RelayState": relay2}, follow_redirects=False)
    assert r2.status_code in (302, 307)
    import sqlite3
    conn = sqlite3.connect(os.path.join(TMP, "registry.db"))
    n = conn.execute("SELECT COUNT(*) FROM users WHERE saml_sub='saml-sub-001'").fetchone()[0]
    conn.close()
    assert n == 1, f"应复用用户，实际 {n}"

    # 6) RelayState 重放被拒
    assert c.post("/api/auth/saml/acs", data={"SAMLResponse": resp_b64, "RelayState": relay}, follow_redirects=False).status_code == 400

    # 7) 未配置 → 503（清空配置测试需重启，这里只验已配置路径已通）

print("ALL PASSED")
