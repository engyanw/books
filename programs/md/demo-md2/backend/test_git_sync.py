# -*- coding: utf-8 -*-
"""E1 回归：Git 双向同步（docs-as-code）。
覆盖：bind/get/unbind；pull 从本地仓库读文件回写文档；push 文档→仓库 commit；
admin sync 触发 auto_publish；token 加密落库明文不回传。
使用本地 git 仓库（无需网络/GitPython），直接调 git 二进制。
"""
import os, shutil, tempfile, subprocess
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="git_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
# 关闭自动备份等后台副作用
os.environ["BACKUP_INTERVAL_HOURS"] = "0"

import main  # noqa: E402

# 准备一个本地 git 仓库（bare），含一个 README.md
REPO = os.path.join(TMP, "origin.git")
subprocess.run(["git", "init", "--bare", "--quiet", "-b", "main", REPO], check=True)
# 用一个临时工作仓库写入初始提交再 push
seed = tempfile.mkdtemp(prefix="seed_")
subprocess.run(["git", "init", "--quiet", "-b", "main", seed], check=True)
subprocess.run(["git", "-C", seed, "config", "user.email", "t@t"], check=True)
subprocess.run(["git", "-C", seed, "config", "user.name", "t"], check=True)
open(os.path.join(seed, "doc.md"), "w").write("from repo line1\n")
subprocess.run(["git", "-C", seed, "add", "."], check=True)
subprocess.run(["git", "-C", seed, "commit", "--quiet", "-m", "init"], check=True)
subprocess.run(["git", "-C", seed, "remote", "add", "origin", REPO], check=True)
subprocess.run(["git", "-C", seed, "push", "--quiet", "origin", "main"], check=True)
shutil.rmtree(seed, ignore_errors=True)

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    # 管理员
    import sqlite3 as _s
    _db = _s.connect(os.path.join(TMP, "registry.db"))
    _db.execute("UPDATE users SET is_admin=1 WHERE username=?", ("owner",))
    _db.commit(); _db.close()

    doc = c.post("/api/docs", headers=h, json={"title": "doc", "content": "local draft"}).json()
    did = doc["doc_id"]

    # 未绑定 → bound=False
    assert c.get(f"/api/docs/{did}/git", headers=h).json()["bound"] is False

    # 绑定（本地路径仓库，无 token）
    b = c.post(f"/api/docs/{did}/git", headers=h,
               json={"repo_url": REPO, "branch": "main", "file_path": "doc.md", "auto_publish": True}).json()
    assert b["id"].startswith("git-")
    # token_hint 不泄露明文（未设 token → 空）
    assert b["token_hint"] == ""

    # 查询绑定
    g = c.get(f"/api/docs/{did}/git", headers=h).json()
    assert g["bound"] is True and g["repo_url"] == REPO and g["file_path"] == "doc.md"
    assert g["auto_publish"] is True

    # pull → 文档内容应被仓库文件覆盖
    p = c.post(f"/api/docs/{did}/git/pull", headers=h).json()
    assert p["ok"] is True, p
    content = c.get(f"/api/docs/{did}", headers=h).json()["content"]
    assert content == "from repo line1\n", content

    # 修改文档并 push → 仓库应收到新 commit
    c.put(f"/api/docs/{did}", headers=h, json={"content": "edited from app\n", "title": "doc"})
    pu = c.post(f"/api/docs/{did}/git/push", headers=h).json()
    assert pu["ok"] is True, pu
    assert pu["commit"], pu
    # 克隆一份验证仓库内容
    verify = tempfile.mkdtemp(prefix="verify_")
    subprocess.run(["git", "clone", "--quiet", REPO, verify], check=True)
    got = open(os.path.join(verify, "doc.md")).read()
    assert got == "edited from app\n", got
    shutil.rmtree(verify, ignore_errors=True)

    # admin sync 触发 auto_publish
    s = c.post("/api/admin/git/sync", headers=h).json()
    assert s["synced"] == 1, s
    assert s["items"][0]["ok"] is True

    # unbind
    assert c.delete(f"/api/docs/{did}/git", headers=h).status_code == 200
    assert c.get(f"/api/docs/{did}/git", headers=h).json()["bound"] is False

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
