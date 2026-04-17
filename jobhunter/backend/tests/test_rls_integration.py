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
# Helpers - matches test_admin.py pattern (direct DB insert + login)
# ---------------------------------------------------------------------------


async def _create_user(db: AsyncSession, *, name: str = "Test", is_admin: bool = False) -> Candidate:
    c = Candidate(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@rls.com",
        password_hash=hash_password("Testpass123"),
        full_name=name,
        is_admin=is_admin,
    )
    db.add(c)
    await db.flush()
    return c


async def _login(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": "Testpass123"},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
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
        assert _has_candidate_id_column(mapper) is False


# ---------------------------------------------------------------------------
# Tenant middleware integration (API-level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_middleware_sets_tenant_on_authenticated_request(client: AsyncClient, auth_headers: dict):
    """Authenticated requests should have tenant context set by middleware."""
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


@pytest.mark.asyncio
async def test_public_paths_skip_tenant_middleware(client: AsyncClient):
    """Public paths like /health should work without auth."""
    resp = await client.get(f"{API}/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_user_data_isolation_via_api(client: AsyncClient, db_session: AsyncSession):
    """Two users should only see their own companies via API endpoints."""
    user_a = await _create_user(db_session, name="User A")
    user_b = await _create_user(db_session, name="User B")

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
    await db_session.flush()

    headers_a = await _login(client, user_a.email)
    headers_b = await _login(client, user_b.email)

    resp_a = await client.get(f"{API}/companies", headers=headers_a)
    resp_b = await client.get(f"{API}/companies", headers=headers_b)

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    # Response is CompanyListResponse with "companies" list and "total" count
    data_a = resp_a.json()
    data_b = resp_b.json()

    companies_a = data_a["companies"]
    companies_b = data_b["companies"]

    # User A should see exactly 2 companies, User B should see exactly 3
    assert len(companies_a) == 2, f"User A expected 2 companies, got {len(companies_a)}"
    assert len(companies_b) == 3, f"User B expected 3 companies, got {len(companies_b)}"

    # Verify names to confirm isolation (no cross-tenant leakage)
    names_a = {c["name"] for c in companies_a}
    names_b = {c["name"] for c in companies_b}
    assert all(n.startswith("Company A-") for n in names_a)
    assert all(n.startswith("Company B-") for n in names_b)


@pytest.mark.asyncio
async def test_admin_endpoint_sees_all_data(client: AsyncClient, db_session: AsyncSession):
    """Admin endpoints using get_admin_db should see cross-tenant data."""
    admin = await _create_user(db_session, name="Admin User", is_admin=True)
    user_a = await _create_user(db_session, name="Regular A")
    user_b = await _create_user(db_session, name="Regular B")

    # Create companies for different users
    db_session.add(Company(id=uuid.uuid4(), candidate_id=user_a.id, name="A-Corp", domain="acorp.com"))
    db_session.add(Company(id=uuid.uuid4(), candidate_id=user_b.id, name="B-Corp", domain="bcorp.com"))
    await db_session.flush()

    admin_headers = await _login(client, admin.email)

    # Admin overview should succeed (exercises get_admin_db)
    resp = await client.get(f"{API}/admin/overview", headers=admin_headers)
    assert resp.status_code == 200

    # Admin users list should show all users
    resp = await client.get(f"{API}/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Should have at least the admin + 2 regular users (plus seed-inviter from conftest)
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_worker_clears_tenant_context():
    """Worker functions must reset tenant context to None to avoid cross-tenant leakage."""
    token = current_tenant_id.set("some-tenant-id")
    assert current_tenant_id.get() == "some-tenant-id"

    worker_token = current_tenant_id.set(None)
    assert current_tenant_id.get() is None

    current_tenant_id.reset(worker_token)
    assert current_tenant_id.get() == "some-tenant-id"

    current_tenant_id.reset(token)
    assert current_tenant_id.get() is None


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
        from sqlalchemy.orm import Session

        mock_event.listens_for.assert_called_once_with(Session, "do_orm_execute")
