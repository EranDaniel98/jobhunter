"""Tests for TenantMiddleware — extracts candidate_id from JWT into request.state."""

from unittest.mock import patch

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.middleware.tenant import TenantMiddleware

# ---------------------------------------------------------------------------
# Minimal test app with TenantMiddleware
# ---------------------------------------------------------------------------

TEST_JWT_SECRET = "test-secret-for-tenant-middleware"
TEST_JWT_ALGORITHM = "HS256"


def _create_test_app() -> FastAPI:
    """Build a tiny FastAPI app that echoes tenant_id from request.state."""
    test_app = FastAPI()
    test_app.add_middleware(TenantMiddleware)

    @test_app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @test_app.get("/api/v1/admin/users")
    async def admin_users():
        return {"users": []}

    @test_app.get("/api/v1/protected")
    async def protected(request: Request):
        return {"tenant_id": getattr(request.state, "tenant_id", None)}

    return test_app


def _make_token(sub: str, secret: str = TEST_JWT_SECRET) -> str:
    return jwt.encode({"sub": sub}, secret, algorithm=TEST_JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticated_request_sets_tenant_id():
    """Valid JWT sets tenant_id on request.state."""
    app = _create_test_app()
    token = _make_token("candidate-123")

    with patch("app.middleware.tenant.settings") as mock_settings:
        mock_settings.JWT_SECRET = TEST_JWT_SECRET
        mock_settings.JWT_ALGORITHM = TEST_JWT_ALGORITHM

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/protected", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "candidate-123"


@pytest.mark.asyncio
async def test_unauthenticated_request_has_none_tenant():
    """Request without Authorization header has tenant_id=None."""
    app = _create_test_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/protected")

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] is None


@pytest.mark.asyncio
async def test_public_path_bypasses_tenant_extraction():
    """Health endpoint skips tenant extraction entirely."""
    app = _create_test_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_admin_path_bypasses_tenant_extraction():
    """Admin endpoints skip tenant extraction."""
    app = _create_test_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/admin/users")

    assert resp.status_code == 200
    assert resp.json() == {"users": []}


@pytest.mark.asyncio
async def test_invalid_jwt_doesnt_crash():
    """Malformed JWT is handled gracefully — tenant_id stays None."""
    app = _create_test_app()

    with patch("app.middleware.tenant.settings") as mock_settings:
        mock_settings.JWT_SECRET = TEST_JWT_SECRET
        mock_settings.JWT_ALGORITHM = TEST_JWT_ALGORITHM

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/protected",
                headers={"Authorization": "Bearer invalid.jwt.token"},
            )

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] is None


@pytest.mark.asyncio
async def test_structlog_context_bound_and_unbound():
    """Structlog contextvars are bound during request and unbound after."""
    app = _create_test_app()
    token = _make_token("candidate-456")

    with (
        patch("app.middleware.tenant.settings") as mock_settings,
        patch("app.middleware.tenant.structlog") as mock_structlog,
    ):
        mock_settings.JWT_SECRET = TEST_JWT_SECRET
        mock_settings.JWT_ALGORITHM = TEST_JWT_ALGORITHM

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.get("/api/v1/protected", headers={"Authorization": f"Bearer {token}"})

        mock_structlog.contextvars.bind_contextvars.assert_called_with(tenant_id="candidate-456")
        mock_structlog.contextvars.unbind_contextvars.assert_called_with("tenant_id")
