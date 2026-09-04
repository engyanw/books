# -*- coding: utf-8 -*-
"""P2-c 自动分级回归：密钥扫描命中 → 建议提升 confidential；apply=true 落库；
公开分享中文档拒绝自动提升（DLP）。
"""
import os, tempfile

TMP = tempfile.mkdtemp(prefix="autocls_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402

SECRET_CONTENT = "运维笔记\nOPENAI_API_KEY=sk-abc123def456ghi789jkl012mno345\naws key AKIAIOSFODNN7EXAMPLE\n"
CLEAN_CONTENT = "架构设计文档，无密钥。\n# 标题\n正文内容。\n"


def _make_user(c, name):
    c.post("/api/auth/register", json={"username": name, "password": "p@ssw0rd"})
    return c.post("/api/auth/login", json={"username": name, "password": "p@ssw0rd"}).json()["token"]


with TestClient(main.app) as c:
    t = _make_user(c, "cls_user")
    h = {"Authorization": f"Bearer {t}"}

    # 干净文档：无命中 → 建议维持 internal
    d1 = c.post("/api/docs", headers=h, json={"title": "clean", "content": CLEAN_CONTENT}).json()["doc_id"]
    r = c.post(f"/api/docs/{d1}/scan-secrets", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["count"] == 0
    assert j["current_classification"] == "internal"
    assert j["suggested_classification"] == "internal"

    # 含密钥文档：命中 → 建议 confidential
    d2 = c.post("/api/docs", headers=h, json={"title": "secrets", "content": SECRET_CONTENT}).json()["doc_id"]
    r = c.post(f"/api/docs/{d2}/scan-secrets", headers=h)
    j = r.json()
    assert j["count"] >= 2, j
    assert j["suggested_classification"] == "confidential"
    assert j["current_classification"] == "internal"  # 尚未应用

    # auto-classify 默认不应用：apply=false
    r = c.post(f"/api/docs/{d2}/auto-classify", headers=h)
    j = r.json()
    assert j["suggested_classification"] == "confidential"
    assert j["applied"] is False
    assert j["current_classification"] == "internal"

    # apply=true → 提升为 confidential
    r = c.post(f"/api/docs/{d2}/auto-classify?apply=true", headers=h)
    j = r.json()
    assert j["applied"] is True, j
    assert j["current_classification"] == "confidential", j
    # 再次扫描 → 已 confidential，建议亦 confidential
    r = c.post(f"/api/docs/{d2}/scan-secrets", headers=h)
    assert r.json()["current_classification"] == "confidential"

    # DLP：公开分享的含密钥文档 → apply=true 拒绝提升
    d3 = c.post("/api/docs", headers=h, json={"title": "shared-secret", "content": SECRET_CONTENT}).json()["doc_id"]
    # 开启公开分享（默认只读）
    sc = c.post(f"/api/docs/{d3}/share", headers=h, json={})
    assert sc.status_code == 200, sc.text
    assert sc.json().get("share_code"), sc.text  # 分享已开启
    r = c.post(f"/api/docs/{d3}/auto-classify?apply=true", headers=h)
    j = r.json()
    assert j["applied"] is False, j
    assert j["reason"] is not None  # 给出拒绝原因
    assert j["current_classification"] == "internal"  # 未提升

print("ALL PASSED")
