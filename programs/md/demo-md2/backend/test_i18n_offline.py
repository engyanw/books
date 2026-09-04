# -*- coding: utf-8 -*-
"""P2-G：多语言 i18n + 离线移动端同步。

验证：
- /api/i18n/{locale} 返回 zh/en 文案表，未知 locale 回退 zh
- /api/i18n 列出可用语言
- /api/sync/bundle 全量拉取文档 + 游标；since 增量只取后续变更
- 软删文档在 bundle 中标记 deleted
- PWA manifest + service worker 可访问
"""
import os, tempfile, shutil
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="i18n_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402
import i18n  # noqa: E402


def reg(c, u):
    c.post("/api/auth/register", json={"username": u, "password": "pw123456"})
    return c.post("/api/auth/login", json={"username": u, "password": "pw123456"}).json()["token"]


# 1) i18n 模块
assert "zh" in i18n.locales() and "en" in i18n.locales()
assert i18n.translate("zh", "doc.save") == "保存"
assert i18n.translate("en", "doc.save") == "Save"
# 未知 locale 回退默认 zh
assert i18n.translate("klingon", "doc.save") == "保存"

with TestClient(main.app) as c:
    tok = reg(c, "alice")
    ha = {"Authorization": f"Bearer {tok}"}

    # 2) i18n 端点
    r = c.get("/api/i18n/zh")
    assert r.status_code == 200
    s = r.json()
    assert s["strings"]["doc.save"] == "保存" and "en" in s["locales"]
    r = c.get("/api/i18n")
    assert "zh" in r.json()["locales"]

    # 3) sync bundle：建两篇文档，全量拉取
    c.post("/api/docs", json={"title": "doc-a", "content": "# A"}, headers=ha)
    did_b = c.post("/api/docs", json={"title": "doc-b", "content": "# B"}, headers=ha).json()["doc_id"]
    r = c.get("/api/sync/bundle", headers=ha)
    assert r.status_code == 200
    bundle = r.json()
    titles = [x["title"] for x in bundle["items"]]
    assert "doc-a" in titles and "doc-b" in titles
    cursor = bundle["cursor"]
    assert cursor

    # 4) 增量：since=cursor 时无新变更（空或仅自身）
    r = c.get("/api/sync/bundle", params={"since": cursor}, headers=ha)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 0, r.json()

    # 5) 新增一篇 → 增量应含它
    c.post("/api/docs", json={"title": "doc-c", "content": "# C"}, headers=ha)
    r = c.get("/api/sync/bundle", params={"since": cursor}, headers=ha)
    titles = [x["title"] for x in r.json()["items"]]
    assert "doc-c" in titles and "doc-a" not in titles, titles

    # 6) 软删 doc-b → bundle 标 deleted
    c.delete(f"/api/docs/{did_b}", headers=ha)
    r = c.get("/api/sync/bundle", params={"since": cursor}, headers=ha)
    db_item = next((x for x in r.json()["items"] if x["doc_id"] == did_b), None)
    assert db_item is not None and db_item["deleted"] is True, r.json()

# 7) PWA manifest + service worker
with TestClient(main.app) as c:
    r = c.get("/manifest.webmanifest")
    assert r.status_code == 200 and "mde-shell" not in r.text  # JSON 内容
    assert r.json()["short_name"] == "MDE"
    r = c.get("/sw.js")
    assert r.status_code == 200 and "service" in r.text.lower()
    assert "fetch" in r.text

shutil.rmtree(TMP, ignore_errors=True)
print("ALL PASSED")
