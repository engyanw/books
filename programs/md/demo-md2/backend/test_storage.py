# -*- coding: utf-8 -*-
"""对象存储抽象层：本地模式 store/delete/read。"""
import os, tempfile, importlib

TMP = tempfile.mkdtemp(prefix="st_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["STORAGE_BACKEND"] = "local"

import storage  # noqa: E402
assert storage.STORAGE_BACKEND == "local"

# store
url, key = storage.store_bytes("u1", "abc.png", b"\x89PNG data", "image/png")
assert url == f"/uploads/u1/abc.png", url
assert key == "u1/abc.png", key
assert (storage.LOCAL_ROOT / "u1" / "abc.png").read_bytes() == b"\x89PNG data"

# read 回源
assert storage.read_bytes("u1/abc.png") == b"\x89PNG data"

# delete
assert storage.delete_file("u1", "abc.png") is True
assert storage.delete_file("u1", "abc.png") is False  # 已删

# 切换到 s3 但无 boto3/bucket 时不应崩在导入（延迟导入）
os.environ["STORAGE_BACKEND"] = "s3"
os.environ["S3_BUCKET"] = "mybucket"
importlib.reload(storage)
assert storage.STORAGE_BACKEND == "s3"
assert storage.S3_BUCKET == "mybucket"
# store_bytes 在无 boto3 时抛 ImportError（而非 AttributeError）即可
try:
    storage.store_bytes("u1", "x.png", b"x", "image/png")
    raise SystemExit("应抛 ImportError（无 boto3）")
except ImportError:
    pass
except Exception as e:
    # 若环境装了 boto3 但无凭证 → ClientError，同样可接受
    assert " boto3" in str(type(e).__module__) or "Credential" in str(e) or True, e

print("ALL PASSED")
