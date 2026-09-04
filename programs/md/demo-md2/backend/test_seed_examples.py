# -*- coding: utf-8 -*-
"""验证：新用户注册后云端自动生成 examples 文件夹 + 示例文档（基础5篇+场景模板）。"""
import os, shutil, tempfile
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="seed_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

import main  # noqa: E402
from seed_examples import EXAMPLES  # noqa: E402
EXPECTED = len(EXAMPLES)

with TestClient(main.app) as client:
    r = client.post("/api/auth/register", json={"username": "newbie", "password": "p@ssw0rd"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    docs = client.get("/api/docs", headers=h).json()["items"]
    titles = [d["title"] for d in docs]
    print("云端节点:", titles)

    folder = [d for d in docs if d["kind"] == "folder" and d["title"] == "examples"]
    assert folder, "未生成 examples 文件夹"
    # examples 文件夹应位于根目录（path 为空）
    assert folder[0]["path"] == "", f"examples 应在根目录，实际 path={folder[0]['path']!r}"

    files = [d for d in docs if d["kind"] == "file"]
    file_titles = [d["title"] for d in files]
    print("示例文件:", file_titles)
    assert len(files) == EXPECTED, f"应有 {EXPECTED} 篇示例，实际 {len(files)}"
    # 所有示例文件应位于 examples 文件夹下（path == "examples"）
    assert all(d["path"] == "examples" for d in files), "示例文件 path 应为 'examples'"

    # 打开一篇检查内容存在
    fid = files[0]["doc_id"]
    got = client.get(f"/api/docs/{fid}", headers=h).json()
    assert got["content"].strip().startswith("#"), "示例内容应以标题开头"
    print("首篇示例片段:", got["content"].splitlines()[0])

    # 幂等性：再注册第二个新用户同样获得 5 篇，且彼此独立
    r2 = client.post("/api/auth/register", json={"username": "newbie2", "password": "p@ssw0rd"})
    t2 = r2.json()["token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    docs2 = client.get("/api/docs", headers=h2).json()["items"]
    assert len([d for d in docs2 if d["kind"] == "file"]) == EXPECTED
    # newbie2 看不到 newbie 的文档（doc_id 互不相同）
    ids1 = {d["doc_id"] for d in docs}
    ids2 = {d["doc_id"] for d in docs2}
    assert ids1.isdisjoint(ids2), "两个用户示例 doc_id 不应重叠"
    print("两用户隔离 OK，doc_id 无重叠")

shutil.rmtree(TMP, ignore_errors=True)
print("ALL PASSED")
