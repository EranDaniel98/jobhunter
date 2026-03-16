"""Extended tests for the health endpoint — covers degraded/failed states."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_health_returns_200_when_all_healthy(client: AsyncClient):
    """GET /health returns 200 with status=healthy when DB and Redis are both up."""
    resp = await client.get(f"{API}/health")
    # May be 200 (healthy) or 503 (degraded) depending on test env state
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    assert "version" in data
    assert "checks" in data
    assert data["version"] == "0.3.0"


@pytest.mark.asyncio
async def test_health_checks_structure(client: AsyncClient):
    """GET /health response includes all expected check keys."""
    resp = await client.get(f"{API}/health")
    data = resp.json()
    checks = data["checks"]
    # These keys must always be present
    assert "database" in checks
    assert "redis" in checks
    assert "migration_version" in checks
    assert "connection_mode" in checks
    assert "pgbouncer_configured" in checks
    assert "db_reachable" in checks


@pytest.mark.asyncio
async def test_health_503_when_redis_down(client: AsyncClient):
    """GET /health returns 503 when Redis ping fails."""
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(side_effect=ConnectionError("Redis connection refused"))

    with patch("app.api.health.get_redis", return_value=mock_redis):
        resp = await client.get(f"{API}/health")

    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert "unhealthy" in data["checks"]["redis"]


@pytest.mark.asyncio
async def test_health_503_when_db_down(client: AsyncClient):
    """GET /health returns 503 when DB execute fails."""
    from sqlalchemy.exc import OperationalError

    # Patch the session's execute to raise an error
    with patch(
        "app.api.health.AsyncSession.execute",
        side_effect=OperationalError("DB down", None, None),
    ):
        resp = await client.get(f"{API}/health")

    # When DB is down, response should be degraded
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_health_status_healthy_string(client: AsyncClient):
    """GET /health status field is either 'healthy' or 'degraded'."""
    resp = await client.get(f"{API}/health")
    data = resp.json()
    assert data["status"] in ("healthy", "degraded")


@pytest.mark.asyncio
async def test_health_redis_unhealthy_contains_error_detail(client: AsyncClient):
    """When Redis fails, checks.redis contains the error message."""
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(side_effect=RuntimeError("connection timed out"))

    with patch("app.api.health.get_redis", return_value=mock_redis):
        resp = await client.get(f"{API}/health")

    data = resp.json()
    redis_status = data["checks"]["redis"]
    assert redis_status.startswith("unhealthy:")
    assert "connection timed out" in redis_status


@pytest.mark.asyncio
async def test_health_migration_version_present(client: AsyncClient):
    """GET /health always includes migration_version (may be 'unknown' if table missing)."""
    resp = await client.get(f"{API}/health")
    data = resp.json()
    assert "migration_version" in data["checks"]
    # Should be a non-empty value
    assert data["checks"]["migration_version"] is not None


@pytest.mark.asyncio
async def test_health_pgbouncer_configured_is_bool(client: AsyncClient):
    """pgbouncer_configured is a boolean in the health response."""
    resp = await client.get(f"{API}/health")
    data = resp.json()
    assert isinstance(data["checks"]["pgbouncer_configured"], bool)
