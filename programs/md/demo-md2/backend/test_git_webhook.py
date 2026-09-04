# -*- coding: utf-8 -*-
"""#2 Git push-to-publish webhook 回归。

GitHub 风格 push webhook：HMAC-SHA256 签名校验 → 拉取远端最新内容回写文档 →
auto_publish 时置 status=published 并审计。不走 _require_user（以 webhook 密钥为准入）。
"""
import os, shutil, tempfile, subprocess, hmac, hashlib, json
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="gitwh_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["BACKUP_INTERVAL_HOURS"] = "0"

import main  # noqa: E402

# 本地 bare 仓库 + 初始 doc.md
REPO = os.path.join(TMP, "origin.git")
subprocess.run(["git", "init", "--bare", "--quiet", "-b", "main", REPO], check=True)
seed = tempfile.mkdtemp(prefix="seed_")
subprocess.run(["git", "init", "--quiet", "-b", "main", seed], check=True)
subprocess.run(["git", "-C", seed, "config", "user.email", "t@t"], check=True)
subprocess.run(["git", "-C", seed, "config", "user.name", "t"], check=True)
open(os.path.join(seed, "doc.md"), "w").write("# v1 from repo\n")
subprocess.run(["git", "-C", seed, "add", "."], check=True)
subprocess.run(["git", "-C", seed, "commit", "--quiet", "-m", "init"], check=True)
subprocess.run(["git", "-C", seed, "remote", "add", "origin", REPO], check=True)
subprocess.run(["git", "-C", seed, "push", "--quiet", "origin", "main"], check=True)
shutil.rmtree(seed, ignore_errors=True)

WH_SECRET = "test-webhook-secret-please-rotate"


def sign(body: bytes, secret: str = WH_SECRET) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    doc = c.post("/api/docs", headers=h, json={"title": "doc", "content": "local draft"}).json()
    did = doc["doc_id"]
    # 绑定：显式 webhook_secret + auto_publish
    b = c.post(f"/api/docs/{did}/git", headers=h, json={
        "repo_url": REPO, "branch": "main", "file_path": "doc.md",
        "auto_publish": True, "webhook_secret": WH_SECRET,
    }).json()
    assert b["webhook_secret"] == WH_SECRET, b
    assert c.get(f"/api/docs/{did}/git", headers=h).json()["webhook_bound"] is True

    # 1) 缺签名头 → 401
    body = b'{"ref":"refs/heads/main"}'
    assert c.post(f"/api/docs/{did}/git/webhook", content=body).status_code == 401

    # 2) 错误签名 → 401
    r = c.post(f"/api/docs/{did}/git/webhook", content=body,
               headers={"X-Hub-Signature-256": "sha256=deadbeef"})
    assert r.status_code == 401, r.text

    # 3) 正确签名 → 200，拉取成功，文档被远端内容覆盖，且 published=True（auto_publish + 原 draft）
    r = c.post(f"/api/docs/{did}/git/webhook", content=body,
               headers={"X-Hub-Signature-256": sign(body)})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["published"] is True, r.text
    content = c.get(f"/api/docs/{did}", headers=h).json()["content"]
    assert content == "# v1 from repo\n", content
    assert c.get(f"/api/docs/{did}", headers=h).json()["status"] == "published"

    # 4) 再次 push 一个新 commit，再触发 webhook：内容更新且 published 已是 published（不重复置位）
    seed2 = tempfile.mkdtemp(prefix="seed2_")
    subprocess.run(["git", "clone", "--quiet", REPO, seed2], check=True)
    subprocess.run(["git", "-C", seed2, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", seed2, "config", "user.name", "t"], check=True)
    open(os.path.join(seed2, "doc.md"), "w").write("# v2 updated\n")
    subprocess.run(["git", "-C", seed2, "add", "."], check=True)
    subprocess.run(["git", "-C", seed2, "commit", "--quiet", "-m", "v2"], check=True)
    subprocess.run(["git", "-C", seed2, "push", "--quiet", "origin", "main"], check=True)
    shutil.rmtree(seed2, ignore_errors=True)

    body2 = b'{"ref":"refs/heads/main"}'
    r = c.post(f"/api/docs/{did}/git/webhook", content=body2,
               headers={"X-Hub-Signature-256": sign(body2)})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    # 第二次 published=False（已经是 published）
    assert r.json()["published"] is False, r.text
    content2 = c.get(f"/api/docs/{did}", headers=h).json()["content"]
    assert content2 == "# v2 updated\n", content2

    # 5) 未绑定 → 404
    doc2 = c.post("/api/docs", headers=h, json={"title": "d2", "content": "x"}).json()
    assert c.post(f"/api/docs/{doc2['doc_id']}/git/webhook", content=body,
                  headers={"X-Hub-Signature-256": sign(body)}).status_code == 404

    # 6) 非法 doc_id → 404
    assert c.post("/api/docs/nope/git/webhook", content=body,
                  headers={"X-Hub-Signature-256": sign(body)}).status_code == 404

print("ALL PASSED")
shutil.rmtree(TMP, ignore_errors=True)
