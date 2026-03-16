"""Tests for app/main.py startup / lifespan logic.

We test the lifespan coroutine in isolation by patching all external I/O
(Redis, DB, checkpointer, event bus) so no real infrastructure is needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine_mock() -> MagicMock:
    """Return an engine mock where connect() works as an async context manager."""
    engine_mock = MagicMock()
    engine_mock.dispose = AsyncMock()

    # The lifespan does: async with engine.connect() as conn: conn.execute(...)
    conn_mock = MagicMock()
    result_mock = MagicMock()
    result_mock.first.return_value = ("018",)
    conn_mock.execute = AsyncMock(return_value=result_mock)

    # Build an async context manager that returns conn_mock
    async_cm = MagicMock()
    async_cm.__aenter__ = AsyncMock(return_value=conn_mock)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    engine_mock.connect.return_value = async_cm

    return engine_mock


def _patch_all_io():
    """Return a list of patches that disable all I/O in lifespan."""
    return [
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.engine"),
        patch("app.main.setup_logging"),
        # Patch checkpointer helpers via import inside lifespan
        patch("app.graphs.resume_pipeline.init_checkpointer", new_callable=AsyncMock),
        patch("app.graphs.resume_pipeline.close_checkpointer", new_callable=AsyncMock),
    ]


def _make_settings_mock(
    jwt_secret: str = "super-secret-jwt-key-that-is-not-default",
    unsubscribe_secret: str = "unsubscribe-secret",
    openai_api_key: str = "sk-test",
    hunter_api_key: str = "hunter-test",
    frontend_url: str = "http://localhost:3000",
    sentry_dsn: str = "",
    app_name: str = "TestApp",
    database_url: str = "postgresql+asyncpg://localhost/test",
) -> MagicMock:
    mock = MagicMock()
    mock.JWT_SECRET = jwt_secret
    mock.UNSUBSCRIBE_SECRET = unsubscribe_secret
    mock.OPENAI_API_KEY = openai_api_key
    mock.HUNTER_API_KEY = hunter_api_key
    mock.FRONTEND_URL = frontend_url
    mock.SENTRY_DSN = sentry_dsn
    mock.APP_NAME = app_name
    mock.DATABASE_URL = database_url
    return mock


# ---------------------------------------------------------------------------
# JWT_SECRET validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_rejects_default_jwt_secret():
    """Startup must raise SystemExit when JWT_SECRET is the default placeholder."""
    from app.main import _JWT_DEFAULT, lifespan

    mock_settings = _make_settings_mock(jwt_secret=_JWT_DEFAULT)
    mock_app = MagicMock()

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.setup_logging"),
        pytest.raises(SystemExit, match="FATAL"),
    ):
        async with lifespan(mock_app):
            pass  # Should never reach here


@pytest.mark.asyncio
async def test_startup_accepts_custom_jwt_secret():
    """Startup succeeds when JWT_SECRET differs from the default placeholder."""
    from app.main import lifespan

    mock_settings = _make_settings_mock()
    mock_app = MagicMock()

    engine_mock = _make_engine_mock()

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.engine", engine_mock),
        patch("app.main.logger"),
        patch("app.graphs.resume_pipeline.init_checkpointer", new_callable=AsyncMock),
        patch("app.graphs.resume_pipeline.close_checkpointer", new_callable=AsyncMock),
        patch("app.events.bus.get_event_bus") as mock_get_bus,
    ):
        mock_bus = MagicMock()
        mock_bus.subscribe = MagicMock()
        mock_bus.handler_count = 4
        mock_get_bus.return_value = mock_bus

        async with lifespan(mock_app):
            pass  # No exception means startup succeeded


# ---------------------------------------------------------------------------
# Missing optional env vars → warnings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_warns_when_unsubscribe_secret_empty():
    """Startup logs a warning when UNSUBSCRIBE_SECRET is empty."""
    from app.main import lifespan

    mock_settings = _make_settings_mock(unsubscribe_secret="")
    mock_app = MagicMock()
    engine_mock = _make_engine_mock()

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.engine", engine_mock),
        patch("app.main.logger") as mock_logger,
        patch("app.graphs.resume_pipeline.init_checkpointer", new_callable=AsyncMock),
        patch("app.graphs.resume_pipeline.close_checkpointer", new_callable=AsyncMock),
        patch("app.events.bus.get_event_bus") as mock_get_bus,
    ):
        mock_bus = MagicMock()
        mock_bus.handler_count = 4
        mock_get_bus.return_value = mock_bus

        async with lifespan(mock_app):
            pass

    warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
    assert any("UNSUBSCRIBE_SECRET" in w for w in warning_calls)


@pytest.mark.asyncio
async def test_startup_warns_when_openai_key_empty():
    """Startup logs a warning when OPENAI_API_KEY is empty."""
    from app.main import lifespan

    mock_settings = _make_settings_mock(openai_api_key="")
    mock_app = MagicMock()
    engine_mock = _make_engine_mock()

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.engine", engine_mock),
        patch("app.main.logger") as mock_logger,
        patch("app.graphs.resume_pipeline.init_checkpointer", new_callable=AsyncMock),
        patch("app.graphs.resume_pipeline.close_checkpointer", new_callable=AsyncMock),
        patch("app.events.bus.get_event_bus") as mock_get_bus,
    ):
        mock_bus = MagicMock()
        mock_bus.handler_count = 4
        mock_get_bus.return_value = mock_bus

        async with lifespan(mock_app):
            pass

    warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
    assert any("OPENAI_API_KEY" in w for w in warning_calls)


@pytest.mark.asyncio
async def test_startup_warns_when_hunter_key_empty():
    """Startup logs a warning when HUNTER_API_KEY is empty."""
    from app.main import lifespan

    mock_settings = _make_settings_mock(hunter_api_key="")
    mock_app = MagicMock()
    engine_mock = _make_engine_mock()

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.engine", engine_mock),
        patch("app.main.logger") as mock_logger,
        patch("app.graphs.resume_pipeline.init_checkpointer", new_callable=AsyncMock),
        patch("app.graphs.resume_pipeline.close_checkpointer", new_callable=AsyncMock),
        patch("app.events.bus.get_event_bus") as mock_get_bus,
    ):
        mock_bus = MagicMock()
        mock_bus.handler_count = 4
        mock_get_bus.return_value = mock_bus

        async with lifespan(mock_app):
            pass

    warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
    assert any("HUNTER_API_KEY" in w for w in warning_calls)


# ---------------------------------------------------------------------------
# Production FRONTEND_URL check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_errors_when_localhost_frontend_in_railway():
    """Startup logs an error when FRONTEND_URL is localhost on Railway."""
    from app.main import lifespan

    mock_settings = _make_settings_mock(frontend_url="http://localhost:3000")
    mock_app = MagicMock()
    engine_mock = _make_engine_mock()

    import os

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.engine", engine_mock),
        patch("app.main.logger") as mock_logger,
        patch("app.graphs.resume_pipeline.init_checkpointer", new_callable=AsyncMock),
        patch("app.graphs.resume_pipeline.close_checkpointer", new_callable=AsyncMock),
        patch("app.events.bus.get_event_bus") as mock_get_bus,
        patch.dict(os.environ, {"RAILWAY_ENVIRONMENT": "production"}),
    ):
        mock_bus = MagicMock()
        mock_bus.handler_count = 4
        mock_get_bus.return_value = mock_bus

        async with lifespan(mock_app):
            pass

    error_calls = [str(c) for c in mock_logger.error.call_args_list]
    assert any("FRONTEND_URL" in e for e in error_calls)


# ---------------------------------------------------------------------------
# Sentry initialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_initializes_sentry_when_dsn_set():
    """When SENTRY_DSN is set, sentry_sdk.init is called."""
    from app.main import lifespan

    mock_settings = _make_settings_mock(sentry_dsn="https://test@sentry.io/123")
    mock_settings.SENTRY_ENVIRONMENT = "production"
    mock_settings.SENTRY_TRACES_SAMPLE_RATE = 0.1
    mock_app = MagicMock()
    engine_mock = _make_engine_mock()

    mock_sentry = MagicMock()

    import sys

    sys.modules["sentry_sdk"] = mock_sentry

    try:
        with (
            patch("app.main.settings", mock_settings),
            patch("app.main.setup_logging"),
            patch("app.main.init_redis", new_callable=AsyncMock),
            patch("app.main.close_redis", new_callable=AsyncMock),
            patch("app.main.engine", engine_mock),
            patch("app.main.logger"),
            patch("app.graphs.resume_pipeline.init_checkpointer", new_callable=AsyncMock),
            patch("app.graphs.resume_pipeline.close_checkpointer", new_callable=AsyncMock),
            patch("app.events.bus.get_event_bus") as mock_get_bus,
        ):
            mock_bus = MagicMock()
            mock_bus.handler_count = 4
            mock_get_bus.return_value = mock_bus

            async with lifespan(mock_app):
                pass

        mock_sentry.init.assert_called_once()
        init_kwargs = mock_sentry.init.call_args.kwargs
        assert init_kwargs["dsn"] == "https://test@sentry.io/123"
        assert init_kwargs["send_default_pii"] is False
    finally:
        sys.modules.pop("sentry_sdk", None)


# ---------------------------------------------------------------------------
# Migration check failure is graceful
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_handles_migration_check_failure_gracefully():
    """If the migration version query fails, startup still proceeds (just logs a warning)."""
    from app.main import lifespan

    mock_settings = _make_settings_mock()
    mock_app = MagicMock()

    # engine.connect() raises — simulates DB unreachable for alembic check
    engine_mock = _make_engine_mock()
    # Use a plain MagicMock so the sync side_effect doesn't leave an unawaited coroutine
    connect_mock = MagicMock()
    connect_mock.side_effect = Exception("DB unreachable")
    engine_mock.connect = connect_mock

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.engine", engine_mock),
        patch("app.main.logger") as mock_logger,
        patch("app.graphs.resume_pipeline.init_checkpointer", new_callable=AsyncMock),
        patch("app.graphs.resume_pipeline.close_checkpointer", new_callable=AsyncMock),
        patch("app.events.bus.get_event_bus") as mock_get_bus,
    ):
        mock_bus = MagicMock()
        mock_bus.handler_count = 4
        mock_get_bus.return_value = mock_bus

        # Should not raise — failure is caught and logged
        async with lifespan(mock_app):
            pass

    warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
    assert any("migration_check_failed" in w for w in warning_calls)
