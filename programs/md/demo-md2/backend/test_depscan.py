# -*- coding: utf-8 -*-
"""P1-E2：依赖扫描 + SBOM。

验证：
- installed_packages() 列出已安装发行版（含 fastapi 等真实依赖）
- generate_sbom() 产出 CycloneDX 风格 JSON（bomFormat/components/purl）
- scan_vulns() 对照本地 advisory DB：伪造一条精确匹配某已安装包版本的 advisory → 命中；
  版本不匹配的 advisory → 不命中
- _version_matches 支持 <,<=,>=,== 等多种 specifier
- /api/admin/deps、/scan、/sbom 端点（管理员可见，非管理员 403）
"""
import os, json, tempfile, shutil
from fastapi.testclient import TestClient
import depscan

TMP = tempfile.mkdtemp(prefix="sbom_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402

# 1) installed_packages 真实可用
pkgs = depscan.installed_packages()
names = {p["name"].lower() for p in pkgs}
assert "fastapi" in names, "应能枚举出 fastapi"
assert all("version" in p for p in pkgs)

# 2) SBOM 结构正确
bom = depscan.generate_sbom()
assert bom["bomFormat"] == "CycloneDX"
assert any(c["name"].lower() == "fastapi" for c in bom["components"])
assert any("pkg:pypi/fastapi@" in c["purl"] for c in bom["components"])

# 3) 版本匹配器
assert depscan._version_matches("1.0.0", "<2.0.0") is True
assert depscan._version_matches("3.0.0", "<2.0.0") is False
assert depscan._version_matches("1.5.0", ">=1.0,<2.0") is True
assert depscan._version_matches("2.5.0", ">=1.0,<2.0") is False
assert depscan._version_matches("1.2.3", "==1.2.3") is True
assert depscan._version_matches("1.2.4", "==1.2.3") is False

# 4) 漏洞扫描：构造针对已安装 fastapi 真实版本的精确 advisory → 必命中
fpkg = next(p for p in pkgs if p["name"].lower() == "fastapi")
ver = fpkg["version"]
test_adv_path = os.path.join(TMP, "adv.json")
with open(test_adv_path, "w", encoding="utf-8") as f:
    json.dump({"advisories": [
        {"package": "fastapi", "range": f"<={ver}", "cve": "CVE-TEST-0001", "severity": "high", "summary": "test match exact installed", "fixed_in": "999.0.0"},
        {"package": "fastapi", "range": "==0.0.1-nonexistent", "cve": "CVE-TEST-0002", "severity": "high", "summary": "should not match"},
    ]}, f)
hits = depscan.scan_vulns(advisory_path=test_adv_path)
cves = [h["cve"] for h in hits]
assert "CVE-TEST-0001" in cves, f"已安装版本 {ver} 应命中 <=range，实际 {hits}"
assert "CVE-TEST-0002" not in cves, "不匹配的版本不应命中"

# 5) 端点
def _make_admin(c):
    c.post("/api/auth/register", json={"username": "admin_e2", "password": "pw123456"})
    import sqlite3
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin_e2'")
    conn.commit(); conn.close()
    return c.post("/api/auth/login", json={"username": "admin_e2", "password": "pw123456"}).json()["token"]

with TestClient(main.app) as c:
    tok = _make_admin(c)
    ha = {"Authorization": f"Bearer {tok}"}
    r = c.get("/api/admin/deps", headers=ha)
    assert r.status_code == 200 and "fastapi" in json.dumps(r.json()), r.text
    r = c.get("/api/admin/deps/scan", headers=ha)
    assert r.status_code == 200 and "vulnerable" in r.json(), r.text
    r = c.get("/api/admin/sbom", headers=ha)
    assert r.status_code == 200 and r.json().get("bomFormat") == "CycloneDX", r.text
    # 非管理员 403
    c.post("/api/auth/register", json={"username": "plain_e2", "password": "pw123456"})
    pt = c.post("/api/auth/login", json={"username": "plain_e2", "password": "pw123456"}).json()["token"]
    assert c.get("/api/admin/deps/scan", headers={"Authorization": f"Bearer {pt}"}).status_code == 403

shutil.rmtree(TMP, ignore_errors=True)
print("ALL PASSED")
