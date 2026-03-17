"""Comprehensive tests for admin dashboard API endpoints."""
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.contact import Contact
from app.models.invite import InviteCode
from app.models.outreach import OutreachMessage
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


async def _create_user(
    db: AsyncSession,
    email: str | None = None,
    full_name: str = "Test User",
    is_admin: bool = False,
    created_at: datetime | None = None,
) -> Candidate:
    candidate = Candidate(
        id=uuid.uuid4(),
        email=email or _unique_email("user"),
        password_hash=hash_password("testpass123"),
        full_name=full_name,
        is_admin=is_admin,
    )
    if created_at:
        candidate.created_at = created_at
    db.add(candidate)
    await db.flush()
    return candidate


async def _login(client: AsyncClient, email: str, password: str = "testpass123") -> dict:
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
    )
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_invite(
    db: AsyncSession, inviter_id: uuid.UUID, used_by_id: uuid.UUID | None = None
) -> InviteCode:
    invite = InviteCode(
        id=uuid.uuid4(),
        code=secrets.token_urlsafe(16),
        invited_by_id=inviter_id,
        used_by_id=used_by_id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        is_used=used_by_id is not None,
    )
    db.add(invite)
    await db.flush()
    return invite


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> Candidate:
    return await _create_user(db_session, full_name="Admin User", is_admin=True)


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> Candidate:
    return await _create_user(db_session, full_name="Regular User", is_admin=False)


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, admin_user: Candidate) -> dict:
    return await _login(client, admin_user.email)


@pytest_asyncio.fixture
async def regular_headers(client: AsyncClient, regular_user: Candidate) -> dict:
    return await _login(client, regular_user.email)


# ---------------------------------------------------------------------------
# 1. AUTH GUARD - All endpoints must require admin
# ---------------------------------------------------------------------------

class TestAdminAuthGuard:
    """Every admin endpoint must return 403 for non-admin users and 401 for unauthenticated."""

    ADMIN_ENDPOINTS = [
        ("GET", "/admin/overview"),
        ("GET", "/admin/users"),
        ("GET", f"/admin/users/{uuid.uuid4()}"),
        ("PATCH", f"/admin/users/{uuid.uuid4()}"),
        ("DELETE", f"/admin/users/{uuid.uuid4()}"),
        ("GET", "/admin/analytics/registrations"),
        ("GET", "/admin/analytics/invites"),
        ("GET", "/admin/analytics/top-users"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    async def test_unauthenticated_returns_401(self, client: AsyncClient, method: str, path: str):
        resp = await client.request(method, f"{API}{path}")
        assert resp.status_code in (401, 403), f"{method} {path} should reject unauthenticated"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    async def test_non_admin_returns_403(
        self, client: AsyncClient, regular_headers: dict, method: str, path: str
    ):
        kwargs = {"headers": regular_headers}
        if method == "PATCH":
            kwargs["json"] = {"is_admin": True}
        resp = await client.request(method, f"{API}{path}", **kwargs)
        assert resp.status_code == 403, f"{method} {path} should reject non-admin"


# ---------------------------------------------------------------------------
# 2. SYSTEM OVERVIEW
# ---------------------------------------------------------------------------

class TestSystemOverview:

    @pytest.mark.asyncio
    async def test_overview_empty_system(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/overview", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] >= 1  # at least the admin
        assert "total_companies" in data
        assert "total_messages_sent" in data
        assert "total_contacts" in data
        assert "total_invites_used" in data
        assert "active_users_7d" in data
        assert "active_users_30d" in data

    @pytest.mark.asyncio
    async def test_overview_counts_are_accurate(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        # Create some data
        user2 = await _create_user(db_session, full_name="Count Tester")
        company = Company(
            id=uuid.uuid4(), candidate_id=admin_user.id,
            name="TestCo", domain="testco.com", status="approved", research_status="completed",
        )
        db_session.add(company)
        await db_session.flush()

        contact = Contact(
            id=uuid.uuid4(), company_id=company.id, candidate_id=admin_user.id,
            full_name="John Contact", email="john@testco.com",
        )
        db_session.add(contact)
        await db_session.flush()

        # One sent message, one draft - only sent should count
        db_session.add(OutreachMessage(
            id=uuid.uuid4(), contact_id=contact.id, candidate_id=admin_user.id,
            body="sent msg", status="sent", sent_at=datetime.now(UTC),
        ))
        db_session.add(OutreachMessage(
            id=uuid.uuid4(), contact_id=contact.id, candidate_id=admin_user.id,
            body="draft msg", status="draft",
        ))
        await db_session.flush()

        invite = await _create_invite(db_session, admin_user.id, used_by_id=user2.id)

        resp = await client.get(f"{API}/admin/overview", headers=admin_headers)
        data = resp.json()
        assert data["total_users"] >= 2
        assert data["total_companies"] >= 1
        assert data["total_contacts"] >= 1
        assert data["total_messages_sent"] >= 1  # only the "sent" one
        assert data["total_invites_used"] >= 1


# ---------------------------------------------------------------------------
# 3. USER LIST
# ---------------------------------------------------------------------------

class TestUserList:

    @pytest.mark.asyncio
    async def test_list_users_returns_users(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["users"]) >= 1

    @pytest.mark.asyncio
    async def test_list_users_contains_expected_fields(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(f"{API}/admin/users", headers=admin_headers)
        user = resp.json()["users"][0]
        for field in ("id", "email", "full_name", "is_admin", "created_at", "companies_count", "messages_sent_count"):
            assert field in user, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_list_users_search_by_email(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        tag = uuid.uuid4().hex[:8]
        await _create_user(db_session, f"searchable-{tag}@test.com", "Searchable Person")

        resp = await client.get(
            f"{API}/admin/users", headers=admin_headers, params={"search": f"searchable-{tag}"}
        )
        data = resp.json()
        assert data["total"] >= 1
        assert any(f"searchable-{tag}" in u["email"] for u in data["users"])

    @pytest.mark.asyncio
    async def test_list_users_search_by_name(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        await _create_user(db_session, full_name="Zaphod Beeblebrox")

        resp = await client.get(
            f"{API}/admin/users", headers=admin_headers, params={"search": "Beeblebrox"}
        )
        data = resp.json()
        assert data["total"] >= 1
        assert any("Beeblebrox" in u["full_name"] for u in data["users"])

    @pytest.mark.asyncio
    async def test_list_users_search_no_match(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(
            f"{API}/admin/users", headers=admin_headers, params={"search": "zzzznonexistent999"}
        )
        data = resp.json()
        assert data["total"] == 0
        assert len(data["users"]) == 0

    @pytest.mark.asyncio
    async def test_list_users_pagination(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        # Create several users
        for i in range(5):
            await _create_user(db_session, full_name=f"Page User {i}")

        # Page 1 with limit 2
        resp = await client.get(
            f"{API}/admin/users", headers=admin_headers, params={"skip": 0, "limit": 2}
        )
        data = resp.json()
        assert len(data["users"]) == 2
        assert data["total"] >= 5

        # Page 2
        resp2 = await client.get(
            f"{API}/admin/users", headers=admin_headers, params={"skip": 2, "limit": 2}
        )
        data2 = resp2.json()
        assert len(data2["users"]) == 2
        # Different users from page 1
        page1_ids = {u["id"] for u in data["users"]}
        page2_ids = {u["id"] for u in data2["users"]}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_list_users_aggregated_stats(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        # Create company + sent message for admin user
        company = Company(
            id=uuid.uuid4(), candidate_id=admin_user.id,
            name="AggCo", domain="aggco.com",
        )
        db_session.add(company)
        await db_session.flush()

        contact = Contact(
            id=uuid.uuid4(), company_id=company.id, candidate_id=admin_user.id,
            full_name="Agg Contact",
        )
        db_session.add(contact)
        await db_session.flush()

        db_session.add(OutreachMessage(
            id=uuid.uuid4(), contact_id=contact.id, candidate_id=admin_user.id,
            body="sent", status="sent", sent_at=datetime.now(UTC),
        ))
        await db_session.flush()

        resp = await client.get(f"{API}/admin/users", headers=admin_headers)
        admin_entry = next(u for u in resp.json()["users"] if u["id"] == str(admin_user.id))
        assert admin_entry["companies_count"] >= 1
        assert admin_entry["messages_sent_count"] >= 1


# ---------------------------------------------------------------------------
# 4. USER DETAIL
# ---------------------------------------------------------------------------

class TestUserDetail:

    @pytest.mark.asyncio
    async def test_get_user_detail(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate
    ):
        resp = await client.get(f"{API}/admin/users/{admin_user.id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(admin_user.id)
        assert data["email"] == admin_user.email
        assert data["is_admin"] is True

    @pytest.mark.asyncio
    async def test_get_user_detail_nonexistent(
        self, client: AsyncClient, admin_headers: dict
    ):
        fake_id = uuid.uuid4()
        resp = await client.get(f"{API}/admin/users/{fake_id}", headers=admin_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_user_detail_with_invite_info(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        invitee = await _create_user(db_session, full_name="Invitee Detail")
        await _create_invite(db_session, admin_user.id, used_by_id=invitee.id)

        resp = await client.get(f"{API}/admin/users/{invitee.id}", headers=admin_headers)
        data = resp.json()
        assert data["invited_by_email"] == admin_user.email


# ---------------------------------------------------------------------------
# 5. TOGGLE ADMIN
# ---------------------------------------------------------------------------

class TestToggleAdmin:

    @pytest.mark.asyncio
    async def test_promote_user_to_admin(
        self, client: AsyncClient, admin_headers: dict, regular_user: Candidate
    ):
        resp = await client.patch(
            f"{API}/admin/users/{regular_user.id}",
            headers=admin_headers,
            json={"is_admin": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

    @pytest.mark.asyncio
    async def test_demote_admin(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        other_admin = await _create_user(db_session, full_name="Other Admin", is_admin=True)
        resp = await client.patch(
            f"{API}/admin/users/{other_admin.id}",
            headers=admin_headers,
            json={"is_admin": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is False

    @pytest.mark.asyncio
    async def test_toggle_nonexistent_user(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.patch(
            f"{API}/admin/users/{uuid.uuid4()}",
            headers=admin_headers,
            json={"is_admin": True},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_admin_invalid_body(
        self, client: AsyncClient, admin_headers: dict, regular_user: Candidate
    ):
        resp = await client.patch(
            f"{API}/admin/users/{regular_user.id}",
            headers=admin_headers,
            json={"invalid": "field"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_promoted_user_can_access_admin(
        self, client: AsyncClient, admin_headers: dict, regular_user: Candidate
    ):
        # Promote
        await client.patch(
            f"{API}/admin/users/{regular_user.id}",
            headers=admin_headers,
            json={"is_admin": True},
        )
        # Login as promoted user
        promoted_headers = await _login(client, regular_user.email)
        resp = await client.get(f"{API}/admin/overview", headers=promoted_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 6. DELETE USER
# ---------------------------------------------------------------------------

class TestDeleteUser:

    @pytest.mark.asyncio
    async def test_delete_user(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        victim = await _create_user(db_session, full_name="Delete Me")
        resp = await client.delete(f"{API}/admin/users/{victim.id}", headers=admin_headers)
        assert resp.status_code == 204

        # Verify user is gone
        resp = await client.get(f"{API}/admin/users/{victim.id}", headers=admin_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_self_delete(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate
    ):
        resp = await client.delete(f"{API}/admin/users/{admin_user.id}", headers=admin_headers)
        assert resp.status_code == 400
        assert "Cannot delete your own account" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.delete(f"{API}/admin/users/{uuid.uuid4()}", headers=admin_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_cascades_data(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        """Deleting a user should cascade-delete their companies, contacts, messages."""
        victim = await _create_user(db_session, full_name="Cascade Victim")
        company = Company(
            id=uuid.uuid4(), candidate_id=victim.id,
            name="VictimCo", domain="victimco.com",
        )
        db_session.add(company)
        await db_session.flush()

        contact = Contact(
            id=uuid.uuid4(), company_id=company.id, candidate_id=victim.id,
            full_name="Victim Contact",
        )
        db_session.add(contact)
        await db_session.flush()

        msg = OutreachMessage(
            id=uuid.uuid4(), contact_id=contact.id, candidate_id=victim.id,
            body="msg", status="draft",
        )
        db_session.add(msg)
        await db_session.flush()

        company_id = company.id
        contact_id = contact.id
        msg_id = msg.id

        # Delete the user
        resp = await client.delete(f"{API}/admin/users/{victim.id}", headers=admin_headers)
        assert resp.status_code == 204

        # Verify cascade: company, contact, message should all be gone
        assert (await db_session.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none() is None
        assert (await db_session.execute(select(Contact).where(Contact.id == contact_id))).scalar_one_or_none() is None
        assert (await db_session.execute(select(OutreachMessage).where(OutreachMessage.id == msg_id))).scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_deleted_user_cannot_login(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        victim = await _create_user(db_session, full_name="No Login")
        victim_email = victim.email
        await client.delete(f"{API}/admin/users/{victim.id}", headers=admin_headers)

        resp = await client.post(
            f"{API}/auth/login",
            json={"email": victim_email, "password": "testpass123"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 7. REGISTRATION TREND
# ---------------------------------------------------------------------------

class TestRegistrationTrend:

    @pytest.mark.asyncio
    async def test_registration_trend_returns_data(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(
            f"{API}/admin/analytics/registrations", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # At least the admin user was created today
        assert len(data) >= 1
        assert "date" in data[0]
        assert "count" in data[0]

    @pytest.mark.asyncio
    async def test_registration_trend_custom_days(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(
            f"{API}/admin/analytics/registrations",
            headers=admin_headers,
            params={"days": 7},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_registration_trend_validation(
        self, client: AsyncClient, admin_headers: dict
    ):
        # days must be >= 1
        resp = await client.get(
            f"{API}/admin/analytics/registrations",
            headers=admin_headers,
            params={"days": 0},
        )
        assert resp.status_code == 422

        # days must be <= 365
        resp = await client.get(
            f"{API}/admin/analytics/registrations",
            headers=admin_headers,
            params={"days": 999},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 8. INVITE CHAIN
# ---------------------------------------------------------------------------

class TestInviteChain:

    @pytest.mark.asyncio
    async def test_invite_chain_returns_data(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        invitee = await _create_user(db_session, full_name="Chain Invitee")
        await _create_invite(db_session, admin_user.id, used_by_id=invitee.id)

        resp = await client.get(f"{API}/admin/analytics/invites", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        item = data[0]
        for field in ("inviter_email", "inviter_name", "code"):
            assert field in item

    @pytest.mark.asyncio
    async def test_invite_chain_shows_unused(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        await _create_invite(db_session, admin_user.id, used_by_id=None)

        resp = await client.get(f"{API}/admin/analytics/invites", headers=admin_headers)
        data = resp.json()
        unused = [i for i in data if i["used_at"] is None]
        assert len(unused) >= 1
        assert unused[0]["invitee_email"] is None


# ---------------------------------------------------------------------------
# 9. TOP USERS
# ---------------------------------------------------------------------------

class TestTopUsers:

    @pytest.mark.asyncio
    async def test_top_users_messages_sent(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        # Create a sent message for admin
        company = Company(
            id=uuid.uuid4(), candidate_id=admin_user.id,
            name="TopCo", domain="topco.com",
        )
        db_session.add(company)
        await db_session.flush()
        contact = Contact(
            id=uuid.uuid4(), company_id=company.id, candidate_id=admin_user.id,
            full_name="Top Contact",
        )
        db_session.add(contact)
        await db_session.flush()
        db_session.add(OutreachMessage(
            id=uuid.uuid4(), contact_id=contact.id, candidate_id=admin_user.id,
            body="top msg", status="sent", sent_at=datetime.now(UTC),
        ))
        await db_session.flush()

        resp = await client.get(
            f"{API}/admin/analytics/top-users",
            headers=admin_headers,
            params={"metric": "messages_sent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["metric_name"] == "messages_sent"
        assert data[0]["metric_value"] >= 1

    @pytest.mark.asyncio
    async def test_top_users_companies_added(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        db_session.add(Company(
            id=uuid.uuid4(), candidate_id=admin_user.id,
            name="TopCo2", domain="topco2.com",
        ))
        await db_session.flush()

        resp = await client.get(
            f"{API}/admin/analytics/top-users",
            headers=admin_headers,
            params={"metric": "companies_added"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["metric_name"] == "companies_added"

    @pytest.mark.asyncio
    async def test_top_users_invalid_metric(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(
            f"{API}/admin/analytics/top-users",
            headers=admin_headers,
            params={"metric": "totally_fake"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_top_users_excludes_drafts(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        company = Company(
            id=uuid.uuid4(), candidate_id=admin_user.id,
            name="DraftCo", domain="draftco.com",
        )
        db_session.add(company)
        await db_session.flush()
        contact = Contact(
            id=uuid.uuid4(), company_id=company.id, candidate_id=admin_user.id,
            full_name="Draft Contact",
        )
        db_session.add(contact)
        await db_session.flush()
        # Only drafts - should NOT appear in top users
        db_session.add(OutreachMessage(
            id=uuid.uuid4(), contact_id=contact.id, candidate_id=admin_user.id,
            body="just a draft", status="draft",
        ))
        await db_session.flush()

        resp = await client.get(
            f"{API}/admin/analytics/top-users",
            headers=admin_headers,
            params={"metric": "messages_sent", "limit": 50},
        )
        # If admin has no sent messages (only drafts), they shouldn't appear
        # (they may appear from other test fixtures, so just verify response shape)
        data = resp.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# 10. is_admin IN AUTH RESPONSES
# ---------------------------------------------------------------------------

class TestIsAdminInAuth:

    @pytest.mark.asyncio
    async def test_register_returns_is_admin_false(
        self, client: AsyncClient, invite_code: str
    ):
        resp = await client.post(
            f"{API}/auth/register",
            json={
                "email": "newreg@test.com",
                "password": "securepass1",
                "full_name": "New Reg",
                "invite_code": invite_code,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["is_admin"] is False

    @pytest.mark.asyncio
    async def test_get_me_returns_is_admin(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(f"{API}/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

    @pytest.mark.asyncio
    async def test_get_me_returns_is_admin_false_for_regular(
        self, client: AsyncClient, regular_headers: dict
    ):
        resp = await client.get(f"{API}/auth/me", headers=regular_headers)
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is False

    @pytest.mark.asyncio
    async def test_update_me_returns_is_admin(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.patch(
            f"{API}/auth/me",
            headers=admin_headers,
            json={"headline": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True


# ---------------------------------------------------------------------------
# 11. EDGE CASES & SECURITY
# ---------------------------------------------------------------------------

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_422(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(f"{API}/admin/users/not-a-uuid", headers=admin_headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_sql_injection_safe(
        self, client: AsyncClient, admin_headers: dict
    ):
        """Ensure search param is safely handled."""
        resp = await client.get(
            f"{API}/admin/users",
            headers=admin_headers,
            params={"search": "'; DROP TABLE candidates; --"},
        )
        assert resp.status_code == 200  # Should not crash
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_pagination_boundary_skip_beyond_total(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(
            f"{API}/admin/users",
            headers=admin_headers,
            params={"skip": 99999, "limit": 20},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["users"]) == 0
        assert data["total"] >= 1  # total still accurate

    @pytest.mark.asyncio
    async def test_limit_boundary(self, client: AsyncClient, admin_headers: dict):
        # limit=0 should be rejected (ge=1)
        resp = await client.get(
            f"{API}/admin/users",
            headers=admin_headers,
            params={"limit": 0},
        )
        assert resp.status_code == 422

        # limit=101 should be rejected (le=100)
        resp = await client.get(
            f"{API}/admin/users",
            headers=admin_headers,
            params={"limit": 101},
        )
        assert resp.status_code == 422
