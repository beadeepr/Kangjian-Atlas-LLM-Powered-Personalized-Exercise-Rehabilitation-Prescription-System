from __future__ import annotations

import io
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def storage_backend() -> str:
    return os.getenv("OBJECT_STORAGE_BACKEND", "local").strip().lower() or "local"


def local_storage_root() -> Path:
    configured = os.getenv("LOCAL_STORAGE_DIR", "").strip()
    return Path(configured) if configured else BACKEND_DIR / "uploads"


def minio_bucket() -> str:
    return os.getenv("MINIO_BUCKET", "kangjian-atlas")


def _minio_client():
    from minio import Minio

    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def _ensure_minio_bucket(client, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def save_object(content: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
    object_name = object_name.replace("\\", "/").lstrip("/")
    if storage_backend() == "minio":
        client = _minio_client()
        bucket = minio_bucket()
        _ensure_minio_bucket(client, bucket)
        client.put_object(
            bucket,
            object_name,
            io.BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
        return f"minio://{bucket}/{object_name}"

    target = local_storage_root() / object_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    try:
        return str(target.relative_to(BACKEND_DIR))
    except ValueError:
        return str(target)


def check_object_storage() -> dict:
    backend = storage_backend()
    if backend == "minio":
        try:
            client = _minio_client()
            bucket = minio_bucket()
            _ensure_minio_bucket(client, bucket)
            return {
                "backend": "minio",
                "status": "ok",
                "bucket": bucket,
                "endpoint_configured": bool(os.getenv("MINIO_ENDPOINT")),
            }
        except Exception as exc:
            return {"backend": "minio", "status": "error", "detail": str(exc)}
    root = local_storage_root()
    return {"backend": "local", "status": "ok", "root": str(root)}
