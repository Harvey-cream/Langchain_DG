"""阿里云 OSS：预签名上传、下载、删除（密钥来自 settings / .env）。"""
from __future__ import annotations

from pathlib import Path

from app.settings import oss_config


class OssNotConfiguredError(RuntimeError):
    pass


def _bucket():
    cfg = oss_config()
    key_id = cfg["access_key_id"]
    key_secret = cfg["access_key_secret"]
    bucket_name = cfg["bucket_name"]
    endpoint = cfg["endpoint"]
    if not key_id or not key_secret or not bucket_name or not endpoint:
        raise OssNotConfiguredError("OSS 未配置：请在 .env 填写 OSS_ACCESS_KEY_ID / SECRET 等")
    import oss2

    auth = oss2.Auth(key_id, key_secret)
    return oss2.Bucket(auth, endpoint, bucket_name), cfg


def build_object_key(*, user_id: int, document_id: int, filename: str) -> str:
    cfg = oss_config()
    safe = Path(filename).name.replace("\\", "_").replace("/", "_").strip() or "file"
    return f"{cfg['prefix']}/users/{user_id}/{document_id}/{safe}"


def sign_put_url(oss_key: str, *, content_type: str, expires: int | None = None) -> str:
    bucket, cfg = _bucket()
    ttl = expires if expires is not None else int(cfg["upload_url_expires"])
    headers = {"Content-Type": content_type or "application/octet-stream"}
    return bucket.sign_url("PUT", oss_key, ttl, headers=headers)


def object_exists(oss_key: str) -> bool:
    bucket, _ = _bucket()
    return bool(bucket.object_exists(oss_key))


def download_to_path(oss_key: str, local_path: Path) -> None:
    bucket, _ = _bucket()
    local_path.parent.mkdir(parents=True, exist_ok=True)
    bucket.get_object_to_file(oss_key, str(local_path))


def delete_object(oss_key: str) -> None:
    bucket, _ = _bucket()
    bucket.delete_object(oss_key)


def put_object_bytes(oss_key: str, data: bytes, *, content_type: str) -> None:
    bucket, _ = _bucket()
    bucket.put_object(
        oss_key,
        data,
        headers={"Content-Type": content_type or "application/octet-stream"},
    )


def ensure_browser_cors(*, origins: list[str] | None = None) -> None:
    """为浏览器直传配置桶 CORS（预签名 PUT 需要）。"""
    import oss2
    from oss2.models import BucketCors, CorsRule

    bucket, _ = _bucket()
    allow_origins = origins or ["*"]
    rule = CorsRule(
        allowed_origins=allow_origins,
        allowed_methods=["GET", "PUT", "POST", "HEAD", "DELETE"],
        allowed_headers=["*"],
        expose_headers=["ETag", "x-oss-request-id"],
        max_age_seconds=600,
    )
    bucket.put_bucket_cors(BucketCors([rule]))
