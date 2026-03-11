"""Tests for storage backends (R2Storage and LocalStorage)."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.infrastructure.storage import R2Storage, LocalStorage, get_storage


# ---------------------------------------------------------------------------
# R2Storage tests (mocked boto3)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_boto3():
    """Patch boto3.client and return the mock S3 client."""
    with patch.dict(os.environ, {}, clear=False), \
         patch("app.infrastructure.storage.settings") as mock_settings, \
         patch("boto3.client") as mock_client_factory:
        mock_settings.R2_ENDPOINT_URL = "https://fake.r2.endpoint"
        mock_settings.R2_ACCESS_KEY_ID = "fake_key"
        mock_settings.R2_SECRET_ACCESS_KEY = "fake_secret"
        mock_settings.R2_BUCKET_NAME = "test-bucket"
        mock_s3 = MagicMock()
        mock_client_factory.return_value = mock_s3
        yield mock_s3, mock_settings


@pytest.mark.asyncio
async def test_r2_upload(mock_boto3):
    """R2Storage.upload calls put_object with correct bucket and key."""
    mock_s3, _ = mock_boto3
    storage = R2Storage()

    result = await storage.upload("resumes/abc.pdf", b"pdf-bytes", "application/pdf")

    assert result == "resumes/abc.pdf"
    mock_s3.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="resumes/abc.pdf",
        Body=b"pdf-bytes",
        ContentType="application/pdf",
    )


@pytest.mark.asyncio
async def test_r2_download(mock_boto3):
    """R2Storage.download reads the Body from the S3 response."""
    mock_s3, _ = mock_boto3
    body_mock = MagicMock()
    body_mock.read.return_value = b"file-content"
    mock_s3.get_object.return_value = {"Body": body_mock}

    storage = R2Storage()
    data = await storage.download("resumes/abc.pdf")

    assert data == b"file-content"
    mock_s3.get_object.assert_called_once_with(Bucket="test-bucket", Key="resumes/abc.pdf")


@pytest.mark.asyncio
async def test_r2_delete(mock_boto3):
    """R2Storage.delete calls delete_object."""
    mock_s3, _ = mock_boto3
    storage = R2Storage()

    await storage.delete("resumes/abc.pdf")

    mock_s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key="resumes/abc.pdf")


@pytest.mark.asyncio
async def test_r2_upload_without_content_type(mock_boto3):
    """R2Storage.upload omits ContentType when not provided."""
    mock_s3, _ = mock_boto3
    storage = R2Storage()

    await storage.upload("data/file.bin", b"binary-data")

    mock_s3.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="data/file.bin",
        Body=b"binary-data",
    )


# ---------------------------------------------------------------------------
# LocalStorage tests (temp directory)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_upload_and_download(tmp_path):
    """LocalStorage round-trips data through the filesystem."""
    with patch("app.infrastructure.storage.settings") as mock_settings:
        mock_settings.UPLOAD_DIR = str(tmp_path)
        storage = LocalStorage()

        key = "test/hello.txt"
        await storage.upload(key, b"hello world")
        data = await storage.download(key)

    assert data == b"hello world"
    assert os.path.exists(os.path.join(str(tmp_path), key))


@pytest.mark.asyncio
async def test_local_delete(tmp_path):
    """LocalStorage.delete removes the file from disk."""
    with patch("app.infrastructure.storage.settings") as mock_settings:
        mock_settings.UPLOAD_DIR = str(tmp_path)
        storage = LocalStorage()

        key = "test/deleteme.txt"
        await storage.upload(key, b"temporary")
        await storage.delete(key)

    assert not os.path.exists(os.path.join(str(tmp_path), key))


def test_get_storage_returns_r2_when_configured():
    """get_storage returns R2Storage when R2 env vars are set."""
    import app.infrastructure.storage as storage_mod
    original = storage_mod._storage_instance
    storage_mod._storage_instance = None

    try:
        with patch("app.infrastructure.storage.settings") as mock_settings, \
             patch("boto3.client"):
            mock_settings.R2_ENDPOINT_URL = "https://fake.r2.endpoint"
            mock_settings.R2_BUCKET_NAME = "bucket"
            mock_settings.R2_ACCESS_KEY_ID = "key"
            mock_settings.R2_SECRET_ACCESS_KEY = "secret"

            result = get_storage()
            assert isinstance(result, R2Storage)
    finally:
        storage_mod._storage_instance = original


def test_get_storage_returns_local_when_not_configured():
    """get_storage returns LocalStorage when R2 env vars are empty."""
    import app.infrastructure.storage as storage_mod
    original = storage_mod._storage_instance
    storage_mod._storage_instance = None

    try:
        with patch("app.infrastructure.storage.settings") as mock_settings:
            mock_settings.R2_ENDPOINT_URL = ""
            mock_settings.R2_BUCKET_NAME = ""

            result = get_storage()
            assert isinstance(result, LocalStorage)
    finally:
        storage_mod._storage_instance = original
