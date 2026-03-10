"""Tenant isolation middleware — extracts candidate_id from JWT and sets request state."""

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import jwt

from app.config import settings

logger = structlog.get_logger()

# Paths that don't require tenant context
PUBLIC_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/webhooks",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}

ADMIN_PREFIX = "/api/v1/admin"


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant (candidate_id) from JWT and attach to request state.

    This enables tenant-aware logging and prepares for multi-tenant isolation.
    Public endpoints and admin endpoints bypass tenant extraction.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.tenant_id = None

        # Skip public paths
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith(ADMIN_PREFIX) or path.startswith("/api/v1/waitlist"):
            return await call_next(request)

        # Try to extract tenant from Authorization header
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = jwt.decode(
                    token,
                    settings.JWT_SECRET,
                    algorithms=[settings.JWT_ALGORITHM],
                    options={"verify_exp": False},  # Don't fail here; auth dep handles expiry
                )
                candidate_id = payload.get("sub")
                if candidate_id:
                    request.state.tenant_id = candidate_id
                    # Bind to structlog context for all downstream logs
                    structlog.contextvars.bind_contextvars(tenant_id=candidate_id)
            except Exception:
                pass  # Auth dependency will handle invalid tokens

        response = await call_next(request)

        # Clear structlog context after request
        structlog.contextvars.unbind_contextvars("tenant_id")

        return response
