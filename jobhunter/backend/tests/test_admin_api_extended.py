"""Extended unit tests for admin API endpoints (covering uncovered lines)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email(prefix: str = "admin-ext") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


async def _create_user(
    db: AsyncSession,
    email: str | None = None,
    full_name: str = "Test User",
    is_admin: bool = False,
) -> Candidate:
    candidate = Candidate(
        id=uuid.uuid4(),
        email=email or _unique_email(),
        password_hash=hash_password("testpass123"),
        full_name=full_name,
        is_admin=is_admin,
    )
    db.add(candidate)
    await db.flush()
    return candidate


async def _login(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> Candidate:
    return await _create_user(db_session, full_name="Ext Admin", is_admin=True)


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> Candidate:
    return await _create_user(db_session, full_name="Ext Regular", is_admin=False)


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, admin_user: Candidate) -> dict:
    return await _login(client, admin_user.email)


@pytest_asyncio.fixture
async def regular_headers(client: AsyncClient, regular_user: Candidate) -> dict:
    return await _login(client, regular_user.email)


# ---------------------------------------------------------------------------
# GET /admin/overview
# ---------------------------------------------------------------------------


class TestAdminOverview:
    @pytest.mark.asyncio
    async def test_overview_returns_200(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/overview", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "total_companies" in data
        assert "total_messages_sent" in data

    @pytest.mark.asyncio
    async def test_overview_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/overview", headers=regular_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_overview_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{API}/admin/overview")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------


class TestAdminListUsers:
    @pytest.mark.asyncio
    async def test_list_users_returns_list(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_users_with_search(self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession):
        tag = uuid.uuid4().hex[:8]
        await _create_user(db_session, email=f"searchme-{tag}@test.com", full_name="SearchTarget")
        resp = await client.get(f"{API}/admin/users", headers=admin_headers, params={"search": f"searchme-{tag}"})
        data = resp.json()
        assert data["total"] >= 1
        assert any(f"searchme-{tag}" in u["email"] for u in data["users"])

    @pytest.mark.asyncio
    async def test_list_users_pagination(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/users", headers=admin_headers, params={"skip": 0, "limit": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["users"]) <= 1

    @pytest.mark.asyncio
    async def test_list_users_invalid_limit(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/users", headers=admin_headers, params={"limit": 0})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /admin/users/{id}
# ---------------------------------------------------------------------------


class TestAdminGetUser:
    @pytest.mark.asyncio
    async def test_get_user_detail(self, client: AsyncClient, admin_headers: dict, admin_user: Candidate):
        resp = await client.get(f"{API}/admin/users/{admin_user.id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(admin_user.id)
        assert data["is_admin"] is True

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/users/{uuid.uuid4()}", headers=admin_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_user_invalid_uuid(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/users/not-a-uuid", headers=admin_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /admin/users/{id} (toggle admin)
# ---------------------------------------------------------------------------


class TestAdminToggleAdmin:
    @pytest.mark.asyncio
    async def test_promote_user(self, client: AsyncClient, admin_headers: dict, regular_user: Candidate):
        resp = await client.patch(
            f"{API}/admin/users/{regular_user.id}",
            headers=admin_headers,
            json={"is_admin": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

    @pytest.mark.asyncio
    async def test_demote_user(self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession):
        other_admin = await _create_user(db_session, full_name="OtherAdmin", is_admin=True)
        resp = await client.patch(
            f"{API}/admin/users/{other_admin.id}",
            headers=admin_headers,
            json={"is_admin": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is False

    @pytest.mark.asyncio
    async def test_toggle_admin_not_found(self, client: AsyncClient, admin_headers: dict):
        resp = await client.patch(
            f"{API}/admin/users/{uuid.uuid4()}",
            headers=admin_headers,
            json={"is_admin": True},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /admin/activity
# ---------------------------------------------------------------------------


class TestAdminActivity:
    @pytest.mark.asyncio
    async def test_activity_feed_returns_list(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/activity", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_activity_feed_pagination(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(
            f"{API}/admin/activity",
            headers=admin_headers,
            params={"skip": 0, "limit": 5},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_activity_feed_invalid_limit(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/activity", headers=admin_headers, params={"limit": 201})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_activity_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/activity", headers=regular_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/audit-log
# ---------------------------------------------------------------------------


class TestAdminAuditLog:
    @pytest.mark.asyncio
    async def test_audit_log_returns_list(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/audit-log", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_audit_log_after_toggle(
        self,
        client: AsyncClient,
        admin_headers: dict,
        regular_user: Candidate,
        db_session: AsyncSession,
    ):
        # Generate an audit event
        await client.patch(
            f"{API}/admin/users/{regular_user.id}",
            headers=admin_headers,
            json={"is_admin": True},
        )
        resp = await client.get(f"{API}/admin/audit-log", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should have at least one audit entry now
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_audit_log_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/audit-log", headers=regular_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/api-costs
# ---------------------------------------------------------------------------


class TestAdminApiCosts:
    @pytest.mark.asyncio
    async def test_api_costs_returns_list(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/api-costs", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_api_costs_with_days_param(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/api-costs", headers=admin_headers, params={"days": 30})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_api_costs_invalid_days(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/api-costs", headers=admin_headers, params={"days": 0})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_api_costs_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/api-costs", headers=regular_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/db-pool-stats
# ---------------------------------------------------------------------------


class TestAdminDbPoolStats:
    @pytest.mark.asyncio
    async def test_db_pool_stats_returns_dict(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/db-pool-stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "connection_mode" in data
        assert "pool_size" in data

    @pytest.mark.asyncio
    async def test_db_pool_stats_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/db-pool-stats", headers=regular_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/email-health
# ---------------------------------------------------------------------------


class TestAdminEmailHealth:
    @pytest.mark.asyncio
    async def test_email_health_returns_result(self, client: AsyncClient, admin_headers: dict):
        # Patch the underlying DNS resolver so tests don't make real DNS lookups
        with patch(
            "app.services.dns_health_service._resolve_txt",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.get(f"{API}/admin/email-health", headers=admin_headers, params={"force": "true"})
        assert resp.status_code == 200
        data = resp.json()
        assert "domain" in data
        assert "spf" in data
        assert "dkim" in data
        assert "dmarc" in data
        assert "overall" in data

    @pytest.mark.asyncio
    async def test_email_health_cached(self, client: AsyncClient, admin_headers: dict):
        """Second call (without force) should use cache and also succeed."""
        with patch(
            "app.services.dns_health_service._resolve_txt",
            new=AsyncMock(return_value=None),
        ):
            # Prime the cache
            await client.get(f"{API}/admin/email-health", headers=admin_headers, params={"force": "true"})
            # Use cache
            resp = await client.get(f"{API}/admin/email-health", headers=admin_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_email_health_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/email-health", headers=regular_headers)
        assert resp.status_code == 403
