#!/usr/bin/env python3
"""数据目录备份：打包 DOC_DATA_DIR（registry.db + users/ + teams/ + configs/）为带时间戳的 .tar.gz。

提供：
    create_backup(data_dir, out_dir, keep) -> Path   创建备份并轮转旧备份、写清单
    restore_backup(archive, data_dir, force) -> None 从归档恢复
    list_backups(out_dir) -> list[dict]              列出可恢复点（按时间倒序）

清单 manifest.json 记录每份备份的时间戳/大小/文件数/sha256，支持"恢复到某个时间点"
（PITR 基础：选择最近的可用恢复点；真正的 WAL 连续归档需外部工具 wal-g/pgBackRest）。

CLI：
    python scripts/backup.py [--data D] [--out O] [--keep 14]
    python scripts/backup.py --restore ARCHIVE [--data D] [--force]
    python scripts/backup.py --list           列出可恢复点
    python scripts/backup.py --drill          自动恢复演练（恢复到临时目录并校验完整性）
"""
import argparse, hashlib, json, os, sys, tarfile, time, tempfile, shutil
from pathlib import Path

MANIFEST = "manifest.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_count(data_dir: Path) -> int:
    n = 0
    for _ in data_dir.rglob("*"):
        if _.is_file():
            n += 1
    return n


def _load_manifest(out_dir: Path) -> list:
    mf = out_dir / MANIFEST
    if not mf.exists():
        return []
    try:
        return json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_manifest(out_dir: Path, entries: list):
    (out_dir / MANIFEST).write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def create_backup(data_dir, out_dir, keep: int = 14) -> Path:
    """创建一份 tar.gz 备份，更新清单，按 keep 轮转旧备份。返回归档路径。"""
    data_dir = Path(data_dir).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not data_dir.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_dir}")

    ts = time.strftime("%Y%m%d-%H%M%S")
    archive = out_dir / f"md-backup-{ts}.tar.gz"
    # 同秒内多次备份：文件名冲突则追加序号，避免覆盖
    if archive.exists():
        i = 1
        while (out_dir / f"md-backup-{ts}-{i}.tar.gz").exists():
            i += 1
        archive = out_dir / f"md-backup-{ts}-{i}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(str(data_dir), arcname=data_dir.name)

    entry = {
        "timestamp": ts,
        "archive": archive.name,
        "size_bytes": archive.stat().st_size,
        "sha256": _sha256(archive),
        "file_count": _file_count(data_dir),
        "created_at_epoch": int(time.time()),
    }
    entries = _load_manifest(out_dir)
    entries.append(entry)
    # 轮转：保留近 keep 份
    if keep and keep > 0 and len(entries) > keep:
        entries.sort(key=lambda e: e["created_at_epoch"])
        for old in entries[:-keep]:
            p = out_dir / old["archive"]
            if p.exists():
                p.unlink()
        entries = entries[-keep:]
    entries.sort(key=lambda e: e["created_at_epoch"], reverse=True)
    _save_manifest(out_dir, entries)
    return archive


def list_backups(out_dir) -> list:
    """列出可恢复点（按时间倒序），并剔除清单中已丢失归档的条目。"""
    out_dir = Path(out_dir).resolve()
    entries = _load_manifest(out_dir)
    valid = [e for e in entries if (out_dir / e["archive"]).exists()]
    if len(valid) != len(entries):
        _save_manifest(out_dir, valid)
    valid.sort(key=lambda e: e["created_at_epoch"], reverse=True)
    return valid


def restore_backup(archive, data_dir, force: bool = False) -> Path:
    """从归档恢复到 data_dir（force 时把原目录备份为 .bak 再覆盖）。"""
    archive = Path(archive).resolve()
    data_dir = Path(data_dir).resolve()
    if not archive.exists():
        raise FileNotFoundError(f"备份文件不存在: {archive}")
    if data_dir.exists() and any(data_dir.iterdir()) and not force:
        raise RuntimeError(f"目标目录非空: {data_dir}（force=True 覆盖）")
    data_dir.mkdir(parents=True, exist_ok=True)
    if force and data_dir.exists() and any(data_dir.iterdir()):
        bak = data_dir.with_name(data_dir.name + ".bak")
        if bak.exists():
            shutil.rmtree(bak)
        data_dir.rename(bak)
        data_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tmp_extract = data_dir.parent / f".restore_tmp_{os.getpid()}"
        tmp_extract.mkdir(parents=True, exist_ok=True)
        try:
            tar.extractall(tmp_extract)
            top = tmp_extract / data_dir.name
            if not top.exists():
                subs = [p for p in tmp_extract.iterdir() if p.is_dir()]
                top = subs[0] if subs else tmp_extract
            for item in top.iterdir():
                shutil.move(str(item), str(data_dir))
        finally:
            shutil.rmtree(tmp_extract, ignore_errors=True)
    return data_dir


def drill(out_dir, data_dir) -> dict:
    """自动恢复演练：取最新备份，恢复到临时目录，校验文件数/可读性，返回报告。
    P2-13：量化 RTO（实测恢复耗时秒）与 RPO（距最近备份秒）。"""
    points = list_backups(out_dir)
    if not points:
        raise RuntimeError("无可恢复备份点")
    latest = points[0]
    archive = Path(out_dir).resolve() / latest["archive"]
    # 校验 sha256
    actual = _sha256(archive)
    if actual != latest["sha256"]:
        return {"ok": False, "reason": f"sha256 不匹配 期望={latest['sha256']} 实际={actual}", "point": latest}
    tmp = Path(tempfile.mkdtemp(prefix="drill_"))
    t0 = time.time()
    try:
        restore_backup(archive, tmp, force=False)
        n = _file_count(tmp)
        ok = n > 0
        rto = round(time.time() - t0, 3)
        # RPO = 距最近备份创建时刻的秒数
        rpo = int(time.time() - latest.get("created_at_epoch", time.time()))
        return {"ok": ok, "reason": "" if ok else "恢复后无文件", "point": latest,
                "restored_files": n, "expected_files": latest["file_count"],
                "rto_seconds": rto, "rpo_seconds": max(0, rpo)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def find_restore_point(out_dir, target_epoch: int) -> dict:
    """PITR：给定目标时间戳（epoch 秒），返回不晚于该时刻的最近可恢复点。
    SQLite 维度：每个 tar.gz 备份是一份完整快照（含 -wal），恢复即回到该时刻。
    真正的连续 WAL 归档（点在两次备份之间任意时刻）需外部 wal-g/pgBackRest，这里返回最近基线。"""
    points = list_backups(out_dir)  # 已按时间倒序
    for p in points:
        if p.get("created_at_epoch", 0) <= target_epoch:
            return p
    return {}


def replicate_latest(out_dir, replica_dir) -> dict:
    """跨区复制：把本地最新备份归档+清单同步到 replica_dir（模拟异地归档投递）。
    幂等：相同文件名跳过覆盖；返回本地/副本最新时间戳与 lag（秒）。"""
    out_dir = Path(out_dir).resolve()
    replica_dir = Path(replica_dir).resolve()
    replica_dir.mkdir(parents=True, exist_ok=True)
    points = list_backups(out_dir)
    if not points:
        return {"ok": False, "reason": "无本地备份点可复制"}
    latest = points[0]
    src = out_dir / latest["archive"]
    dst = replica_dir / latest["archive"]
    if not dst.exists():
        shutil.copy2(str(src), str(dst))
    # 同步清单（副本侧可据此自检）
    (replica_dir / MANIFEST).write_text(json.dumps(points, ensure_ascii=False, indent=2), encoding="utf-8")
    local_epoch = latest.get("created_at_epoch", 0)
    return {"ok": True, "replicated": latest["archive"], "local_epoch": local_epoch,
            "replica_epoch": local_epoch, "lag_seconds": 0}


def replica_status(out_dir, replica_dir) -> dict:
    """跨区副本健康度：比较本地与副本最新备份时间戳，给出 lag（秒）与 RPO。"""
    out_dir = Path(out_dir).resolve()
    local = list_backups(out_dir)
    local_epoch = local[0].get("created_at_epoch", 0) if local else 0
    if not replica_dir:
        return {"enabled": False, "local_epoch": local_epoch, "reason": "REPLICA_DIR 未配置"}
    replica_dir = Path(replica_dir).resolve()
    rep = list_backups(replica_dir) if replica_dir.exists() else []
    replica_epoch = rep[0].get("created_at_epoch", 0) if rep else 0
    now = int(time.time())
    lag = max(0, local_epoch - replica_epoch) if local_epoch else 0
    rpo = max(0, now - local_epoch) if local_epoch else 0
    return {"enabled": True, "local_epoch": local_epoch, "replica_epoch": replica_epoch,
            "lag_seconds": lag, "rpo_seconds": rpo, "replica_count": len(rep),
            "local_count": len(local)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("DOC_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
    ap.add_argument("--out", default=os.environ.get("BACKUP_DIR", "/backups"))
    ap.add_argument("--keep", type=int, default=14, help="保留近 N 份旧备份（0=不限）")
    ap.add_argument("--restore", metavar="ARCHIVE", help="从指定 tar.gz 恢复到 --data 目录")
    ap.add_argument("--force", action="store_true", help="恢复时覆盖已存在的目标目录")
    ap.add_argument("--list", action="store_true", help="列出可恢复点")
    ap.add_argument("--drill", action="store_true", help="自动恢复演练并校验完整性")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    data_dir = Path(args.data).resolve()

    if args.list:
        for p in list_backups(out_dir):
            print(f"{p['timestamp']}  {p['archive']}  {p['size_bytes']}B  files={p['file_count']}  sha={p['sha256'][:12]}")
        return
    if args.drill:
        rep = drill(out_dir, data_dir)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        sys.exit(0 if rep.get("ok") else 1)
    if args.restore:
        try:
            restore_backup(args.restore, data_dir, force=args.force)
            print(f"恢复完成: {args.restore} -> {data_dir}")
        except Exception as e:
            print(f"恢复失败: {e}", file=sys.stderr); sys.exit(2)
        return

    # 默认：创建备份
    archive = create_backup(data_dir, out_dir, keep=args.keep)
    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"备份完成: {archive} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
