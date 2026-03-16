"""Unit tests for app/infrastructure/hunter_client.py."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.infrastructure.hunter_client import (
    CIRCUIT_BREAKER_KEY,
    HUNTER_BASE_URL,
    HunterClient,
)


def _make_response(status_code: int, data: dict | None = None) -> httpx.Response:
    body = {"data": data or {}}
    return httpx.Response(
        status_code,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", f"{HUNTER_BASE_URL}/domain-search"),
    )


def _make_redis_stub(*, cb_open: bool = False, failure_count: int = 0) -> AsyncMock:
    """Return a Redis stub configured for the given circuit-breaker state."""
    redis = AsyncMock()
    redis.get.return_value = "1" if cb_open else None
    redis.incr.return_value = failure_count + 1
    redis.expire.return_value = True
    redis.setex.return_value = True
    redis.delete.return_value = True
    return redis


class TestHunterClientDomainSearch:
    @pytest.mark.asyncio
    async def test_domain_search_success(self):
        """domain_search returns parsed data on success."""
        expected = {"domain": "example.com", "emails": []}
        mock_resp = _make_response(200, expected)
        mock_redis = _make_redis_stub()

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(return_value=mock_resp)),
        ):
            result = await client.domain_search("example.com")

        assert result == expected

    @pytest.mark.asyncio
    async def test_email_finder_success(self):
        """email_finder returns parsed data on success."""
        expected = {"email": "john@example.com", "score": 95}
        mock_resp = _make_response(200, expected)
        mock_redis = _make_redis_stub()

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(return_value=mock_resp)),
        ):
            result = await client.email_finder("example.com", "John", "Doe")

        assert result == expected

    @pytest.mark.asyncio
    async def test_email_verifier_success(self):
        """email_verifier returns parsed data on success."""
        expected = {"email": "john@example.com", "status": "valid"}
        mock_resp = _make_response(200, expected)
        mock_redis = _make_redis_stub()

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(return_value=mock_resp)),
        ):
            result = await client.email_verifier("john@example.com")

        assert result == expected


class TestHunterCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_raises(self):
        """RuntimeError is raised when circuit breaker key exists in Redis."""
        mock_redis = _make_redis_stub(cb_open=True)

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            pytest.raises(RuntimeError, match="circuit breaker"),
        ):
            await client.domain_search("example.com")

    @pytest.mark.asyncio
    async def test_request_failure_records_failure(self):
        """HTTP error increments failure counter in Redis."""
        resp = _make_response(500)
        error = httpx.HTTPStatusError("server error", request=resp.request, response=resp)
        mock_redis = _make_redis_stub(failure_count=1)

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(side_effect=error)),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await client.domain_search("example.com")

        mock_redis.incr.assert_awaited()

    @pytest.mark.asyncio
    async def test_request_success_clears_failures(self):
        """Successful request deletes the failure counter from Redis."""
        expected = {"domain": "example.com"}
        mock_resp = _make_response(200, expected)
        mock_redis = _make_redis_stub()

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(return_value=mock_resp)),
        ):
            await client.domain_search("example.com")

        mock_redis.delete.assert_awaited_with(f"{CIRCUIT_BREAKER_KEY}:failures")

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_5_failures(self):
        """After 5 failures the circuit breaker key is set in Redis."""
        resp = _make_response(500)
        error = httpx.HTTPStatusError("server error", request=resp.request, response=resp)
        # incr returns 5 (the threshold)
        mock_redis = _make_redis_stub()
        mock_redis.incr.return_value = 5

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(side_effect=error)),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await client.domain_search("example.com")

        mock_redis.setex.assert_awaited_with(f"{CIRCUIT_BREAKER_KEY}:open", 60, "1")

    @pytest.mark.asyncio
    async def test_request_failure_on_connect_error_records_failure(self):
        """ConnectError also increments failure counter."""
        mock_redis = _make_redis_stub()

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(side_effect=httpx.ConnectError("refused"))),
            pytest.raises(httpx.ConnectError),
        ):
            await client.domain_search("example.com")

        mock_redis.incr.assert_awaited()


class TestHunterRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_sleeps_when_exceeded(self):
        """When rate counter exceeds limit, asyncio.sleep is called."""
        expected = {"domain": "example.com"}
        mock_resp = _make_response(200, expected)
        # incr returns 16 — above the default limit of 15
        mock_redis = _make_redis_stub()
        mock_redis.incr.return_value = 16

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(return_value=mock_resp)),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            await client.domain_search("example.com")

        mock_sleep.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_rate_limit_no_sleep_within_limit(self):
        """When rate counter is within limit, asyncio.sleep is NOT called."""
        expected = {"domain": "example.com"}
        mock_resp = _make_response(200, expected)
        mock_redis = _make_redis_stub()
        mock_redis.incr.return_value = 5  # well within limit

        client = HunterClient()
        with (
            patch("app.infrastructure.hunter_client.get_redis", return_value=mock_redis),
            patch.object(client._client, "get", AsyncMock(return_value=mock_resp)),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            await client.domain_search("example.com")

        mock_sleep.assert_not_awaited()
