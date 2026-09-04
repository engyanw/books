# -*- coding: utf-8 -*-
"""#3 Release 冻结不可变性 回归。

冻结后引用文档的 PUT/DELETE → 409；解冻后恢复；打包下载 zip 含快照内容。
"""
import os, shutil, tempfile, io, zipfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="frozen_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 两篇文档
    d1 = c.post("/api/docs", headers=h, json={"title": "doc one", "content": "# v1"}).json()["doc_id"]
    d2 = c.post("/api/docs", headers=h, json={"title": "doc two", "content": "# two"}).json()["doc_id"]

    # 创建 release（快照 d1 当前版本）
    r = c.post("/api/releases", headers=h, json={"name": "R1", "version": "1.0", "doc_ids": [d1]}).json()
    rid = r["release_id"]
    assert r["doc_count"] == 1, r

    # 未冻结时：可修改 d1
    assert c.put(f"/api/docs/{d1}", headers=h, json={"content": "# v2 modified"}).status_code == 200

    # 冻结
    assert c.post(f"/api/releases/{rid}/freeze", headers=h).json()["frozen"] is True

    # 冻结后：PUT d1 → 409（不可变）
    r = c.put(f"/api/docs/{d1}", headers=h, json={"content": "# frozen change"})
    assert r.status_code == 409, r.text
    assert "冻结" in r.json()["detail"], r.text

    # 冻结后：DELETE d1 → 409
    r = c.delete(f"/api/docs/{d1}", headers=h)
    assert r.status_code == 409, r.text

    # d2 未被引用：冻结不影响 → 可删/可改
    assert c.put(f"/api/docs/{d2}", headers=h, json={"content": "# d2 ok"}).status_code == 200
    assert c.delete(f"/api/docs/{d2}", headers=h).status_code == 200

    # 解冻（非创建者 → 403；创建者 → 200）
    c2_user = "other"
    c.post("/api/auth/register", json={"username": c2_user, "password": "p@ssw0rd"})
    t2 = c.post("/api/auth/login", json={"username": c2_user, "password": "p@ssw0rd"}).json()["token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert c.post(f"/api/releases/{rid}/unfreeze", headers=h2).status_code == 403
    # 未冻结状态再次解冻 → 先恢复冻结后测：此处仍冻结，由创建者解冻
    assert c.post(f"/api/releases/{rid}/unfreeze", headers=h).json()["frozen"] is False

    # 解冻后：PUT d1 恢复 → 200
    assert c.put(f"/api/docs/{d1}", headers=h, json={"content": "# after unfreeze"}).status_code == 200

    # 打包下载：GET /api/releases/{rid}/download → zip 含快照内容
    # 重新冻结以测试下载
    c.post(f"/api/releases/{rid}/freeze", headers=h)
    r = c.get(f"/api/releases/{rid}/download", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip", r.headers
    assert "attachment" in r.headers["content-disposition"], r.headers
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "INDEX.md" in names, names
    # 至少有一个 .md 文档文件
    md_files = [n for n in names if n.endswith(".md") and n != "INDEX.md"]
    assert len(md_files) == 1, names
    # 快照内容是 release 创建时刻（"# v1"），不受后续写入/解冻影响（manifest 不可变）
    body = z.read(md_files[0]).decode("utf-8")
    assert body == "# v1", body
    # INDEX 含 release 元信息
    idx = z.read("INDEX.md").decode("utf-8")
    assert "R1" in idx and "v1.0" in idx, idx

    # 下载不存在的 release → 404
    assert c.get("/api/releases/rel-nope/download", headers=h).status_code == 404

    # 重复解冻（未冻结）→ 409
    c.post(f"/api/releases/{rid}/unfreeze", headers=h)
    assert c.post(f"/api/releases/{rid}/unfreeze", headers=h).status_code == 409

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
