import pytest
from unittest.mock import patch
from app.infrastructure.database import _get_engine_config


def test_direct_mode_when_no_pgbouncer_url():
    """Without PGBOUNCER_URL, uses DATABASE_URL with normal pool settings."""
    with patch("app.infrastructure.database.settings") as mock_settings:
        mock_settings.PGBOUNCER_URL = ""
        mock_settings.DATABASE_URL = "postgresql+asyncpg://localhost:5432/db"
        mock_settings.DB_POOL_SIZE = 10
        mock_settings.DB_MAX_OVERFLOW = 20
        config = _get_engine_config()
        assert config["pool_size"] == 10
        assert config["max_overflow"] == 20
        assert config["mode"] == "direct"


def test_pgbouncer_mode_reduces_pool():
    """With PGBOUNCER_URL set, reduces pool size."""
    with patch("app.infrastructure.database.settings") as mock_settings:
        mock_settings.PGBOUNCER_URL = "postgresql+asyncpg://localhost:6432/db"
        config = _get_engine_config()
        assert config["pool_size"] == 5
        assert config["max_overflow"] == 5
        assert config["mode"] == "pgbouncer"


@pytest.mark.asyncio
async def test_health_reports_connection_mode(authenticated_client):
    """Health endpoint reports connection mode and db_reachable."""
    resp = await authenticated_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    checks = data.get("checks", data)  # health endpoint wraps in "checks" key
    assert "connection_mode" in checks
    assert checks["connection_mode"] in ("direct", "pgbouncer")
    assert "db_reachable" in checks
    assert checks["db_reachable"] is True
