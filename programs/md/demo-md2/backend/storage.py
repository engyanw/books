# -*- coding: utf-8 -*-
"""对象存储抽象层：本地磁盘 / S3 / OSS 统一接口。

通过 STORAGE_BACKEND 配置切换：
  - local  (默认)：存 data/uploads/<uid>/<hash>.<ext>，StaticFiles 直接提供
  - s3           ：存 S3 兼容桶（AWS S3 / MinIO / Ceph / 阿里 OSS 兼容模式）
  - oss          ：阿里云 OSS（用 oss2 SDK）

依赖可选：仅当配置 s3/oss 时才需要 boto3/oss2，否则零依赖。

对外接口：
    store_bytes(user_id, fname, content, content_type) -> (url, storage_key)
    delete(user_id, fname) -> bool
    read_bytes(storage_key) -> bytes  (仅代理回源/迁移时用)
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger("storage")

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").strip().lower()

# 本地模式根目录（与 UPLOAD_DIR 一致，由 main.py 初始化）
LOCAL_ROOT = Path(os.environ.get("DOC_DATA_DIR", str(Path(__file__).parent / "data"))) / "uploads"

# S3 配置（AWS S3 / MinIO / Ceph 等兼容服务）
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "").strip()       # https://s3.amazonaws.com 或自建
S3_REGION = os.environ.get("S3_REGION", "us-east-1").strip()
S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "").strip()
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "").strip()
S3_PUBLIC_BASE = os.environ.get("S3_PUBLIC_BASE", "").strip()  # 对外访问基址（CDN/反代）

# OSS 配置
OSS_ENDPOINT = os.environ.get("OSS_ENDPOINT", "").strip()
OSS_BUCKET = os.environ.get("OSS_BUCKET", "").strip()         # OSS bucket 名
OSS_ACCESS_KEY = os.environ.get("OSS_ACCESS_KEY", "").strip()
OSS_SECRET_KEY = os.environ.get("OSS_SECRET_KEY", "").strip()
OSS_PUBLIC_BASE = os.environ.get("OSS_PUBLIC_BASE", "").strip()


def _local_store(user_id: str, fname: str, content: bytes, content_type: str = ""):
    d = LOCAL_ROOT / user_id
    d.mkdir(parents=True, exist_ok=True)
    fpath = d / fname
    fpath.write_bytes(content)
    url = f"/uploads/{user_id}/{fname}"
    return url, f"{user_id}/{fname}"


def _local_delete(user_id: str, fname: str) -> bool:
    fpath = LOCAL_ROOT / user_id / fname
    if fpath.exists():
        try:
            fpath.unlink()
            return True
        except Exception:
            return False
    return False


def _local_read(storage_key: str) -> bytes:
    return (LOCAL_ROOT / storage_key).read_bytes()


def _s3_client():
    import boto3  # 延迟导入，仅 s3 模式需要
    kw = {"service_name": "s3", "region_name": S3_REGION,
          "aws_access_key_id": S3_ACCESS_KEY, "aws_secret_access_key": S3_SECRET_KEY}
    if S3_ENDPOINT:
        kw["endpoint_url"] = S3_ENDPOINT
    return boto3.client(**kw)


def _s3_store(user_id: str, fname: str, content: bytes, content_type: str = ""):
    key = f"{user_id}/{fname}"
    c = _s3_client()
    c.put_object(Bucket=S3_BUCKET, Key=key, Body=content, ContentType=content_type or "application/octet-stream")
    base = S3_PUBLIC_BASE or (S3_ENDPOINT.rstrip("/") if S3_ENDPOINT else f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com")
    url = f"{base.rstrip('/')}/{key}"
    return url, key


def _s3_delete(user_id: str, fname: str) -> bool:
    try:
        _s3_client().delete_object(Bucket=S3_BUCKET, Key=f"{user_id}/{fname}")
        return True
    except Exception as e:
        logger.warning("S3 删除失败: %s", e)
        return False


def _s3_read(storage_key: str) -> bytes:
    c = _s3_client()
    obj = c.get_object(Bucket=S3_BUCKET, Key=storage_key)
    return obj["Body"].read()


def _oss_store(user_id: str, fname: str, content: bytes, content_type: str = ""):
    import oss2  # 延迟导入
    auth = oss2.Auth(OSS_ACCESS_KEY, OSS_SECRET_KEY)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)
    key = f"{user_id}/{fname}"
    headers = {"Content-Type": content_type or "application/octet-stream"}
    bucket.put_object(key, content, headers=headers)
    base = OSS_PUBLIC_BASE or f"https://{OSS_BUCKET}.{OSS_ENDPOINT.strip('/')}"
    url = f"{base.rstrip('/')}/{key}"
    return url, key


def _oss_delete(user_id: str, fname: str) -> bool:
    try:
        import oss2
        auth = oss2.Auth(OSS_ACCESS_KEY, OSS_SECRET_KEY)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)
        bucket.delete_object(f"{user_id}/{fname}")
        return True
    except Exception as e:
        logger.warning("OSS 删除失败: %s", e)
        return False


def _oss_read(storage_key: str) -> bytes:
    import oss2
    auth = oss2.Auth(OSS_ACCESS_KEY, OSS_SECRET_KEY)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)
    return bucket.get_object(storage_key).read()


# 分发表
if STORAGE_BACKEND == "s3":
    _store_fn = _s3_store
    _delete_fn = _s3_delete
    _read_fn = _s3_read
    logger.info("对象存储：S3 兼容（bucket=%s）", S3_BUCKET)
elif STORAGE_BACKEND == "oss":
    _store_fn = _oss_store
    _delete_fn = _oss_delete
    _read_fn = _oss_read
    logger.info("对象存储：阿里云 OSS（bucket=%s）", OSS_BUCKET)
else:
    _store_fn = _local_store
    _delete_fn = _local_delete
    _read_fn = _local_read
    STORAGE_BACKEND = "local"
    logger.info("对象存储：本地磁盘（%s）", LOCAL_ROOT)


def store_bytes(user_id: str, fname: str, content: bytes, content_type: str = ""):
    """存储文件字节，返回 (对外可访问 URL, 内部 storage_key)。"""
    return _store_fn(user_id, fname, content, content_type)


def delete_file(user_id: str, fname: str) -> bool:
    """删除文件。"""
    return _delete_fn(user_id, fname)


def read_bytes(storage_key: str) -> bytes:
    """按 storage_key 读取字节（迁移/回源用）。"""
    return _read_fn(storage_key)
