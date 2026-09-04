# -*- coding: utf-8 -*-
"""P0-A3：定时备份 + PITR 清单 + 自动恢复演练。

验证：
- create_backup 写 tar.gz + manifest（含 sha256/文件数/时间戳）
- list_backups 按时间倒序列出可恢复点
- drill 自动恢复演练：校验 sha256、恢复到临时目录、文件数一致
- 多份备份按 keep 轮转
"""
import os, sys, tempfile, shutil, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
from backup import create_backup, list_backups, drill, restore_backup, _load_manifest

TMP = tempfile.mkdtemp(prefix="bkpitr_data_")
OUT = tempfile.mkdtemp(prefix="bkpitr_out_")

# 造数据目录
os.makedirs(os.path.join(TMP, "users", "u1"), exist_ok=True)
with open(os.path.join(TMP, "users", "u1", "docs.db"), "w") as f:
    f.write("dummy-db-content-1")
with open(os.path.join(TMP, "a.txt"), "w") as f:
    f.write("hello")

# 1) 创建备份
a1 = create_backup(TMP, OUT, keep=3)
assert a1.exists()
mf = _load_manifest(__import__("pathlib").Path(OUT))
assert len(mf) == 1
assert mf[0]["sha256"] and mf[0]["file_count"] >= 2, mf[0]

# 2) list_backups
points = list_backups(OUT)
assert len(points) == 1 and points[0]["archive"] == a1.name

# 3) drill 自动恢复演练（校验 sha256 + 恢复到临时目录 + 文件数）
rep = drill(OUT, TMP)
assert rep["ok"], rep
assert rep["restored_files"] == rep["expected_files"], rep

# 4) 再造两份 + 轮转（keep=2）
import time as _t
create_backup(TMP, OUT, keep=2); _t.sleep(1.1)
create_backup(TMP, OUT, keep=2); _t.sleep(0.1)
points = list_backups(OUT)
assert len(points) == 2, f"keep=2 应只保留 2 份，实际 {len(points)}: {points}"
archives = [p["archive"] for p in points]
assert all((__import__("pathlib").Path(OUT) / name).exists() for name in archives)

# 5) restore_backup 到全新目录（用当前仍存在的最新备份）
target = tempfile.mkdtemp(prefix="bkpitr_restore_")
shutil.rmtree(target)
latest_archive = __import__("pathlib").Path(OUT) / list_backups(OUT)[0]["archive"]
restore_backup(latest_archive, target, force=False)
assert os.path.exists(os.path.join(target, "a.txt"))

# 6) PITR：篡改清单中的 sha256 → drill 应失败（完整性护栏）
bad = list_backups(OUT)[0]
bad["sha256"] = "deadbeef" * 8
mf_path = __import__("pathlib").Path(OUT) / "manifest.json"
mf_path.write_text(json.dumps([bad]), encoding="utf-8")
rep2 = drill(OUT, TMP)
assert not rep2["ok"] and "sha256" in rep2["reason"], rep2

shutil.rmtree(TMP, ignore_errors=True)
shutil.rmtree(OUT, ignore_errors=True)
shutil.rmtree(target, ignore_errors=True)
print("ALL PASSED")
