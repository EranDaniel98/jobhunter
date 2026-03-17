"""Tests for Redis helper functions with graceful degradation."""

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.redis_client import (
    get_redis,
    redis_safe_get,
    redis_safe_setex,
)


@pytest.mark.asyncio
async def test_redis_safe_get_returns_value():
    """redis_safe_get returns the value when Redis is healthy."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "cached_value"

    with patch("app.infrastructure.redis_client.redis_client", mock_redis):
        result = await redis_safe_get("my_key")

    assert result == "cached_value"
    mock_redis.get.assert_awaited_once_with("my_key")


@pytest.mark.asyncio
async def test_redis_safe_get_returns_none_on_connection_error():
    """redis_safe_get returns None when Redis is unreachable."""
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = ConnectionError("Connection refused")

    with patch("app.infrastructure.redis_client.redis_client", mock_redis):
        result = await redis_safe_get("my_key")

    assert result is None


@pytest.mark.asyncio
async def test_redis_safe_get_returns_none_when_not_initialized():
    """redis_safe_get returns None when Redis client is None (RuntimeError from get_redis)."""
    with patch("app.infrastructure.redis_client.redis_client", None):
        result = await redis_safe_get("my_key")

    assert result is None


@pytest.mark.asyncio
async def test_redis_safe_setex_returns_true_on_success():
    """redis_safe_setex returns True when the write succeeds."""
    mock_redis = AsyncMock()
    mock_redis.setex.return_value = True

    with patch("app.infrastructure.redis_client.redis_client", mock_redis):
        result = await redis_safe_setex("my_key", 3600, "my_value")

    assert result is True
    mock_redis.setex.assert_awaited_once_with("my_key", 3600, "my_value")


@pytest.mark.asyncio
async def test_redis_safe_setex_returns_false_on_connection_error():
    """redis_safe_setex returns False when Redis is unreachable."""
    mock_redis = AsyncMock()
    mock_redis.setex.side_effect = ConnectionError("Connection refused")

    with patch("app.infrastructure.redis_client.redis_client", mock_redis):
        result = await redis_safe_setex("my_key", 3600, "my_value")

    assert result is False


def test_get_redis_raises_when_not_initialized():
    """get_redis raises RuntimeError when called before init_redis."""
    with patch("app.infrastructure.redis_client.redis_client", None):
        with pytest.raises(RuntimeError, match="Redis not initialized"):
            get_redis()
