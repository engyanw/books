# -*- coding: utf-8 -*-
"""备份恢复演练：写数据 → 备份 → 清空 → 恢复 → 校验数据一致。"""
import os, tempfile, subprocess, sys, sqlite3
from fastapi.testclient import TestClient

TMP = tempfile.mkdtemp(prefix="bk_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"

BACKUP_OUT = tempfile.mkdtemp(prefix="bkout_")

import main  # noqa: E402

with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "restoreuser", "password": "pw123456"})
    tok = c.post("/api/auth/login", json={"username": "restoreuser", "password": "pw123456"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 写若干文档
    created = []
    for i in range(5):
        r = c.post("/api/docs", json={"title": f"doc{i}", "content": f"# 备份恢复 {i}\n"}, headers=h)
        created.append(r.json()["doc_id"])
    conn = sqlite3.connect(os.environ["REGISTRY_DB_PATH"])
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()

# 1) 备份
r = subprocess.run([sys.executable, "scripts/backup.py", "--data", TMP, "--out", BACKUP_OUT],
                   cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True)
assert r.returncode == 0, r.stderr
archives = [f for f in os.listdir(BACKUP_OUT) if f.endswith(".tar.gz")]
assert len(archives) == 1, archives
archive = os.path.join(BACKUP_OUT, archives[0])

# 2) 清空数据目录（模拟灾难）
import shutil
shutil.rmtree(TMP)
assert not os.path.exists(os.path.join(TMP, "registry.db"))

# 3) 恢复
r = subprocess.run([sys.executable, "scripts/backup.py", "--restore", archive, "--data", TMP, "--force"],
                   cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True)
assert r.returncode == 0, r.stderr + r.stdout
assert os.path.exists(os.path.join(TMP, "registry.db")), "恢复后 registry.db 应存在"

# 4) 校验数据一致：用户数一致 + 文档仍在
conn2 = sqlite3.connect(os.path.join(TMP, "registry.db"))
assert conn2.execute("SELECT COUNT(*) FROM users").fetchone()[0] == user_count, "用户数应一致"
# 恢复后用一个新进程的应用校验文档可读（避免复用已关闭的 main 模块状态）
conn2.close()

# 重新导入 main（指向恢复后的目录）验证文档可读
import importlib
r2 = subprocess.run([sys.executable, "-c", """
import os, sys
os.environ["DOC_DATA_DIR"] = %r
os.environ["REGISTRY_DB_PATH"] = os.path.join(%r, "registry.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
sys.path.insert(0, %r)
import main
from fastapi.testclient import TestClient
with TestClient(main.app) as c:
    tok = c.post("/api/auth/login", json={"username": "restoreuser", "password": "pw123456"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    docs = c.get("/api/docs", headers=h).json()["items"]
    titles = {d["title"] for d in docs}
    for i in range(5):
        assert f"doc{i}" in titles, f"doc{i} 丢失: {titles}"
print("RESTORE OK")
""" % (TMP, TMP, os.path.dirname(os.path.abspath(__file__)))],
    capture_output=True, text=True)
assert r2.returncode == 0, r2.stderr + r2.stdout
assert "RESTORE OK" in r2.stdout, r2.stdout

shutil.rmtree(TMP, ignore_errors=True)
shutil.rmtree(BACKUP_OUT, ignore_errors=True)
print("ALL PASSED")
