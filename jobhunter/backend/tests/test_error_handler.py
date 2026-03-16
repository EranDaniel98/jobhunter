"""Tests for ErrorHandlerMiddleware - catches unhandled exceptions, returns 500 JSON."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.error_handler import ErrorHandlerMiddleware


def _create_test_app() -> FastAPI:
    """Build a tiny FastAPI app with ErrorHandlerMiddleware."""
    test_app = FastAPI()
    test_app.add_middleware(ErrorHandlerMiddleware)

    @test_app.get("/ok")
    async def ok():
        return {"status": "ok"}

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("something went very wrong")

    @test_app.get("/value-error")
    async def value_error():
        raise ValueError("bad input")

    return test_app


@pytest.fixture
async def error_client():
    app = _create_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_normal_request_passes_through(error_client: AsyncClient):
    """Non-failing route returns normally."""
    resp = await error_client.get("/ok")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500(error_client: AsyncClient):
    """Unhandled exception is caught and returns 500 with error body."""
    resp = await error_client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "internal_server_error"
    assert body["detail"] == "An unexpected error occurred."
    assert "request_id" in body


@pytest.mark.asyncio
async def test_value_error_also_returns_500(error_client: AsyncClient):
    """Any exception subclass is caught and returns 500."""
    resp = await error_client.get("/value-error")
    assert resp.status_code == 500
    assert resp.json()["error"] == "internal_server_error"


@pytest.mark.asyncio
async def test_error_is_logged(error_client: AsyncClient):
    """The middleware logs the unhandled exception via structlog."""
    with patch("app.middleware.error_handler.logger") as mock_logger:
        resp = await error_client.get("/boom")
    assert resp.status_code == 500
    mock_logger.error.assert_called_once()
    call_kwargs = mock_logger.error.call_args
    assert call_kwargs[0][0] == "unhandled_exception"


@pytest.mark.asyncio
async def test_sentry_capture_called_when_sentry_available():
    """sentry_sdk.capture_exception is called when sentry_sdk is importable."""
    app = _create_test_app()
    mock_sentry = MagicMock()

    import sys

    sys.modules["sentry_sdk"] = mock_sentry

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/boom")
        assert resp.status_code == 500
        mock_sentry.capture_exception.assert_called_once()
    finally:
        # Restore original sentry_sdk state
        sys.modules.pop("sentry_sdk", None)


@pytest.mark.asyncio
async def test_sentry_failure_does_not_mask_500():
    """Even if sentry_sdk.capture_exception raises, we still get a 500."""
    app = _create_test_app()
    mock_sentry = MagicMock()
    mock_sentry.capture_exception.side_effect = Exception("sentry down")

    import sys

    sys.modules["sentry_sdk"] = mock_sentry

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/boom")
        assert resp.status_code == 500
        assert resp.json()["error"] == "internal_server_error"
    finally:
        sys.modules.pop("sentry_sdk", None)


@pytest.mark.asyncio
async def test_request_id_in_response_when_set():
    """If a request_id is in structlog contextvars it appears in the error body."""
    app = _create_test_app()

    with patch("app.middleware.error_handler.structlog") as mock_structlog:
        mock_structlog.contextvars.get_contextvars.return_value = {"request_id": "test-req-id-123"}
        mock_structlog.get_logger.return_value = MagicMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/boom")

    assert resp.status_code == 500
    assert resp.json()["request_id"] == "test-req-id-123"
