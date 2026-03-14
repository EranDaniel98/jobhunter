"""Tenant isolation middleware - extracts candidate_id from JWT and sets request state.

When ENABLE_RLS=True, also installs a SQLAlchemy event listener that automatically
filters all SELECT queries on models with a `candidate_id` column.
"""

import contextvars
import uuid as _uuid

import jwt
import structlog
from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

logger = structlog.get_logger()

# Context variable holding the current tenant's candidate_id (as string UUID)
current_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_tenant_id", default=None)

# Paths that don't require tenant context
PUBLIC_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
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
                    current_tenant_id.set(candidate_id)
                    # Bind to structlog context for all downstream logs
                    structlog.contextvars.bind_contextvars(tenant_id=candidate_id)
            except Exception:
                pass  # Auth dependency will handle invalid tokens

        response = await call_next(request)

        # Clear structlog context and tenant after request
        current_tenant_id.set(None)
        structlog.contextvars.unbind_contextvars("tenant_id")

        return response


def _has_candidate_id_column(mapper) -> bool:
    """Check if the mapped class has a candidate_id column."""
    try:
        return "candidate_id" in {col.key for col in mapper.columns}
    except Exception:
        return False


def install_rls_listener(engine) -> None:
    """Install the SQLAlchemy ORM execute event listener for automatic tenant filtering.

    Only active when settings.ENABLE_RLS is True. Admin sessions can bypass
    RLS by passing execution_options(_bypass_rls=True).
    """
    if not settings.ENABLE_RLS:
        logger.info("rls_disabled", reason="ENABLE_RLS=False")
        return

    @event.listens_for(engine.sync_engine, "do_orm_execute")
    def _apply_rls_filter(orm_execute_state: ORMExecuteState):
        # Skip if RLS bypass is set (admin sessions)
        if orm_execute_state.execution_options.get("_bypass_rls", False):
            return

        # Only filter SELECT queries
        if not orm_execute_state.is_select:
            return

        tenant_id = current_tenant_id.get()
        if tenant_id is None:
            return  # No tenant context (startup, background tasks, etc.)

        # Apply filter to each entity in the query that has candidate_id
        for mapper_entity in orm_execute_state.all_mappers:
            if _has_candidate_id_column(mapper_entity):
                candidate_id_col = mapper_entity.columns["candidate_id"]
                orm_execute_state.statement = orm_execute_state.statement.where(
                    candidate_id_col == _uuid.UUID(tenant_id)
                )

    logger.info("rls_enabled", message="SQLAlchemy RLS event listener installed")
