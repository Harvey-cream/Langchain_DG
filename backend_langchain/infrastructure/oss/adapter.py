from __future__ import annotations

from pathlib import Path

from agent_platform.storage import ObjectStoragePort
from app.services import oss_client


class OssObjectStorage(ObjectStoragePort):
    def exists(self, key: str) -> bool:
        return oss_client.object_exists(key)

    def download(self, key: str, destination: Path) -> None:
        oss_client.download_to_path(key, destination)

    def delete(self, key: str) -> None:
        oss_client.delete_object(key)

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        oss_client.put_object_bytes(key, data, content_type=content_type)

    def sign_upload(self, key: str, *, content_type: str, expires: int | None = None) -> str:
        return oss_client.sign_put_url(key, content_type=content_type, expires=expires)


__all__ = ["OssObjectStorage"]
