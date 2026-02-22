import asyncio
import os
from functools import lru_cache

import structlog

from app.config import settings

logger = structlog.get_logger()


class LocalStorage:
    """Stores files on the local filesystem under UPLOAD_DIR."""

    async def upload(self, key: str, data: bytes, content_type: str = "") -> str:
        path = os.path.join(settings.UPLOAD_DIR, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._write, path, data)
        logger.info("local_storage_upload", key=key)
        return key

    async def download(self, key: str) -> bytes:
        path = os.path.join(settings.UPLOAD_DIR, key)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._read, path)

    async def delete(self, key: str) -> None:
        path = os.path.join(settings.UPLOAD_DIR, key)
        if os.path.exists(path):
            os.remove(path)
            logger.info("local_storage_delete", key=key)

    @staticmethod
    def _write(path: str, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    @staticmethod
    def _read(path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()


class R2Storage:
    """Stores files in Cloudflare R2 via S3-compatible API."""

    def __init__(self) -> None:
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        self._bucket = settings.R2_BUCKET_NAME

    async def upload(self, key: str, data: bytes, content_type: str = "") -> str:
        extra = {"ContentType": content_type} if content_type else {}
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.put_object(
                Bucket=self._bucket, Key=key, Body=data, **extra
            ),
        )
        logger.info("r2_storage_upload", key=key, bucket=self._bucket)
        return key

    async def download(self, key: str) -> bytes:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.get_object(Bucket=self._bucket, Key=key),
        )
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.delete_object(Bucket=self._bucket, Key=key),
        )
        logger.info("r2_storage_delete", key=key, bucket=self._bucket)


_storage_instance = None


def get_storage():
    """Return the storage singleton — R2 if configured, otherwise local."""
    global _storage_instance
    if _storage_instance is None:
        if settings.R2_ENDPOINT_URL and settings.R2_BUCKET_NAME:
            _storage_instance = R2Storage()
            logger.info("storage_backend", backend="r2")
        else:
            _storage_instance = LocalStorage()
            logger.info("storage_backend", backend="local")
    return _storage_instance
