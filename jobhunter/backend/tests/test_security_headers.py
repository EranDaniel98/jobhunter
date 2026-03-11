"""Tests for security headers middleware."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.security_headers import SecurityHeadersMiddleware


@pytest.fixture
def secured_app() -> FastAPI:
    """Create a minimal FastAPI app with the security headers middleware."""
    _app = FastAPI()
    _app.add_middleware(SecurityHeadersMiddleware)

    @_app.get("/ping")
    async def ping():
        return {"ok": True}

    @_app.post("/echo")
    async def echo():
        return {"method": "post"}

    return _app


@pytest.fixture
async def secured_client(secured_app: FastAPI):
    transport = ASGITransport(app=secured_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_hsts_header_present(secured_client: AsyncClient):
    """HSTS header must be set with a long max-age and includeSubDomains."""
    resp = await secured_client.get("/ping")
    assert resp.status_code == 200
    hsts = resp.headers.get("strict-transport-security")
    assert hsts is not None
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


@pytest.mark.asyncio
async def test_x_frame_options_deny(secured_client: AsyncClient):
    """X-Frame-Options must be DENY to prevent clickjacking."""
    resp = await secured_client.get("/ping")
    assert resp.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_x_content_type_options_nosniff(secured_client: AsyncClient):
    """X-Content-Type-Options must be nosniff to prevent MIME sniffing."""
    resp = await secured_client.get("/ping")
    assert resp.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.asyncio
async def test_x_xss_protection_disabled(secured_client: AsyncClient):
    """X-XSS-Protection should be '0' (modern best practice — CSP is preferred)."""
    resp = await secured_client.get("/ping")
    assert resp.headers.get("x-xss-protection") == "0"


@pytest.mark.asyncio
async def test_headers_present_on_post(secured_client: AsyncClient):
    """Security headers must appear on non-GET methods too."""
    resp = await secured_client.post("/echo")
    assert resp.status_code == 200
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("strict-transport-security") is not None
    assert resp.headers.get("x-xss-protection") == "0"
