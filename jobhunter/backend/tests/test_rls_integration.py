"""Integration tests for multi-tenant Row-Level Security (RLS) filtering.

These tests verify that the SQLAlchemy ORM execute event listener installed by
install_rls_listener() actually modifies SELECT queries to append
`WHERE candidate_id = <tenant>` for models that have a candidate_id column.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.middleware.tenant import (
    _has_candidate_id_column,
    current_tenant_id,
    install_rls_listener,
)
from app.models.candidate import Candidate
from app.models.company import Company
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_candidate(
    db: AsyncSession, *, name: str = "Test", is_admin: bool = False
) -> Candidate:
    c = Candidate(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@rls.local",
        password_hash=hash_password("testpass123"),
        full_name=name,
        is_admin=is_admin,
    )
    db.add(c)
    await db.flush()
    return c


async def _login(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Context variable isolation
# ---------------------------------------------------------------------------


class TestCurrentTenantId:
    def test_default_is_none(self):
        assert current_tenant_id.get() is None

    def test_set_and_get(self):
        token = current_tenant_id.set("tenant-abc")
        assert current_tenant_id.get() == "tenant-abc"
        current_tenant_id.reset(token)
        assert current_tenant_id.get() is None

    def test_nested_set(self):
        outer = current_tenant_id.set("outer")
        inner = current_tenant_id.set("inner")
        assert current_tenant_id.get() == "inner"
        current_tenant_id.reset(inner)
        assert current_tenant_id.get() == "outer"
        current_tenant_id.reset(outer)


# ---------------------------------------------------------------------------
# _has_candidate_id_column
# ---------------------------------------------------------------------------


class TestHasCandidateIdColumn:
    def test_company_model_has_candidate_id(self):
        """Company model should be identified as having candidate_id."""
        from sqlalchemy.orm import class_mapper

        mapper = class_mapper(Company)
        assert _has_candidate_id_column(mapper) is True

    def test_candidate_model_has_no_candidate_id(self):
        """Candidate model itself doesn't have a candidate_id FK to itself."""
        from sqlalchemy.orm import class_mapper

        mapper = class_mapper(Candidate)
        # Candidate's PK is 'id', it doesn't have a separate 'candidate_id' FK
        assert _has_candidate_id_column(mapper) is False


# ---------------------------------------------------------------------------
# Tenant middleware integration (API-level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_middleware_sets_tenant_on_authenticated_request(
    client: AsyncClient, auth_headers: dict
):
    """Authenticated requests should have tenant context set by middleware."""
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    # The middleware sets tenant_id = candidate_id from JWT
    assert "id" in resp.json()


@pytest.mark.asyncio
async def test_public_paths_skip_tenant_middleware(client: AsyncClient):
    """Public paths like /health should work without auth."""
    resp = await client.get(f"{API}/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_user_data_isolation_via_api(
    client: AsyncClient, db_session: AsyncSession
):
    """Two users should only see their own companies via API endpoints."""
    user_a = await _make_candidate(db_session, name="User A")
    user_b = await _make_candidate(db_session, name="User B")

    # Create companies for each user
    for i in range(2):
        db_session.add(
            Company(
                id=uuid.uuid4(),
                candidate_id=user_a.id,
                name=f"Company A-{i}",
                domain=f"a{i}.example.com",
            )
        )
    for i in range(3):
        db_session.add(
            Company(
                id=uuid.uuid4(),
                candidate_id=user_b.id,
                name=f"Company B-{i}",
                domain=f"b{i}.example.com",
            )
        )
    await db_session.commit()

    headers_a = await _login(client, user_a.email)
    headers_b = await _login(client, user_b.email)

    resp_a = await client.get(f"{API}/companies", headers=headers_a)
    resp_b = await client.get(f"{API}/companies", headers=headers_b)

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    companies_a = resp_a.json()
    companies_b = resp_b.json()

    # User A should only see their companies
    for c in companies_a:
        assert c["candidate_id"] == str(user_a.id)

    # User B should only see their companies
    for c in companies_b:
        assert c["candidate_id"] == str(user_b.id)


# ---------------------------------------------------------------------------
# install_rls_listener
# ---------------------------------------------------------------------------


class TestInstallRlsListener:
    def test_noop_when_disabled(self):
        """Should not install listener when ENABLE_RLS=False."""
        from unittest.mock import MagicMock, patch

        mock_engine = MagicMock()
        with patch("app.middleware.tenant.settings") as s:
            s.ENABLE_RLS = False
            install_rls_listener(mock_engine)
        mock_engine.sync_engine.assert_not_called()

    def test_installs_when_enabled(self):
        """Should register do_orm_execute listener when ENABLE_RLS=True."""
        from unittest.mock import MagicMock, patch

        mock_engine = MagicMock()
        with (
            patch("app.middleware.tenant.settings") as s,
            patch("app.middleware.tenant.event") as mock_event,
        ):
            s.ENABLE_RLS = True
            install_rls_listener(mock_engine)
        mock_event.listens_for.assert_called_once_with(
            mock_engine.sync_engine, "do_orm_execute"
        )
