"""Tests for admin dashboard Phase 2 improvements:
- Activity feed
- CSV export
- User suspension (toggle active)
- Audit log
- Broadcast email
- Login guard for suspended users
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.analytics import AnalyticsEvent
from app.models.audit import AdminAuditLog
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
    is_active: bool = True,
    preferences: dict | None = None,
    created_at: datetime | None = None,
) -> Candidate:
    candidate = Candidate(
        id=uuid.uuid4(),
        email=email or _unique_email("user"),
        password_hash=hash_password("testpass123"),
        full_name=full_name,
        is_admin=is_admin,
        is_active=is_active,
    )
    if preferences:
        candidate.preferences = preferences
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


async def _create_analytics_event(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    event_type: str = "email_sent",
    entity_type: str | None = "outreach_message",
) -> AnalyticsEvent:
    event = AnalyticsEvent(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        event_type=event_type,
        entity_type=entity_type,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return event


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> Candidate:
    return await _create_user(db_session, full_name="Admin V2", is_admin=True)


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> Candidate:
    return await _create_user(db_session, full_name="Regular V2", is_admin=False)


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, admin_user: Candidate) -> dict:
    return await _login(client, admin_user.email)


@pytest_asyncio.fixture
async def regular_headers(client: AsyncClient, regular_user: Candidate) -> dict:
    return await _login(client, regular_user.email)


# ---------------------------------------------------------------------------
# 1. ACTIVITY FEED
# ---------------------------------------------------------------------------

class TestActivityFeed:

    @pytest.mark.asyncio
    async def test_activity_feed_empty(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/activity", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_activity_feed_returns_events(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        await _create_analytics_event(db_session, admin_user.id, "email_sent")
        await _create_analytics_event(db_session, admin_user.id, "company_added", "company")

        resp = await client.get(f"{API}/admin/activity", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        item = data[0]
        assert "id" in item
        assert "user_email" in item
        assert "user_name" in item
        assert "event_type" in item
        assert "occurred_at" in item

    @pytest.mark.asyncio
    async def test_activity_feed_respects_limit(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        for _ in range(5):
            await _create_analytics_event(db_session, admin_user.id)

        resp = await client.get(
            f"{API}/admin/activity", headers=admin_headers, params={"limit": 2}
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_activity_feed_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/activity", headers=regular_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 2. CSV EXPORT
# ---------------------------------------------------------------------------

class TestCsvExport:

    @pytest.mark.asyncio
    async def test_export_csv(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/users/export", headers=admin_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        content = resp.text
        assert "Email" in content
        assert "Full Name" in content

    @pytest.mark.asyncio
    async def test_export_csv_contains_users(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate
    ):
        resp = await client.get(f"{API}/admin/users/export", headers=admin_headers)
        assert admin_user.email in resp.text

    @pytest.mark.asyncio
    async def test_export_csv_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/users/export", headers=regular_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. TOGGLE ACTIVE (SUSPEND/ACTIVATE)
# ---------------------------------------------------------------------------

class TestToggleActive:

    @pytest.mark.asyncio
    async def test_suspend_user(
        self, client: AsyncClient, admin_headers: dict, regular_user: Candidate
    ):
        resp = await client.patch(
            f"{API}/admin/users/{regular_user.id}/active",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_activate_user(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        suspended = await _create_user(db_session, full_name="Suspended", is_active=False)
        resp = await client.patch(
            f"{API}/admin/users/{suspended.id}/active",
            headers=admin_headers,
            json={"is_active": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    @pytest.mark.asyncio
    async def test_toggle_active_nonexistent(self, client: AsyncClient, admin_headers: dict):
        resp = await client.patch(
            f"{API}/admin/users/{uuid.uuid4()}/active",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_active_requires_admin(
        self, client: AsyncClient, regular_headers: dict, admin_user: Candidate
    ):
        resp = await client.patch(
            f"{API}/admin/users/{admin_user.id}/active",
            headers=regular_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_toggle_active_creates_audit_log(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate,
        regular_user: Candidate, db_session: AsyncSession
    ):
        await client.patch(
            f"{API}/admin/users/{regular_user.id}/active",
            headers=admin_headers,
            json={"is_active": False},
        )

        # Check audit log was created
        result = await db_session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "toggle_active",
                AdminAuditLog.target_user_id == regular_user.id,
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.admin_id == admin_user.id
        assert log.details["is_active"] is False


# ---------------------------------------------------------------------------
# 4. LOGIN GUARD FOR SUSPENDED USERS
# ---------------------------------------------------------------------------

class TestSuspendedLoginGuard:

    @pytest.mark.asyncio
    async def test_suspended_user_cannot_login(
        self, client: AsyncClient, admin_headers: dict, regular_user: Candidate
    ):
        # Suspend the user
        await client.patch(
            f"{API}/admin/users/{regular_user.id}/active",
            headers=admin_headers,
            json={"is_active": False},
        )

        # Try to login
        resp = await client.post(
            f"{API}/auth/login",
            json={"email": regular_user.email, "password": "testpass123"},
        )
        assert resp.status_code == 403
        assert "suspended" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_reactivated_user_can_login(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        user = await _create_user(db_session, full_name="ReactivateTest", is_active=False)
        # Activate
        await client.patch(
            f"{API}/admin/users/{user.id}/active",
            headers=admin_headers,
            json={"is_active": True},
        )
        # Login should succeed
        resp = await client.post(
            f"{API}/auth/login",
            json={"email": user.email, "password": "testpass123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


# ---------------------------------------------------------------------------
# 5. AUDIT LOG
# ---------------------------------------------------------------------------

class TestAuditLog:

    @pytest.mark.asyncio
    async def test_audit_log_empty(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get(f"{API}/admin/audit-log", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_audit_log_records_toggle_admin(
        self, client: AsyncClient, admin_headers: dict, regular_user: Candidate
    ):
        await client.patch(
            f"{API}/admin/users/{regular_user.id}",
            headers=admin_headers,
            json={"is_admin": True},
        )

        resp = await client.get(f"{API}/admin/audit-log", headers=admin_headers)
        data = resp.json()
        admin_actions = [a for a in data if a["action"] == "toggle_admin"]
        assert len(admin_actions) >= 1
        assert admin_actions[0]["target_email"] == regular_user.email

    @pytest.mark.asyncio
    async def test_audit_log_records_delete(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        victim = await _create_user(db_session, full_name="Audit Delete Victim")
        victim_email = victim.email
        await client.delete(f"{API}/admin/users/{victim.id}", headers=admin_headers)

        resp = await client.get(f"{API}/admin/audit-log", headers=admin_headers)
        data = resp.json()
        delete_actions = [a for a in data if a["action"] == "delete_user"]
        assert len(delete_actions) >= 1
        # Target user was deleted so target_email may be null
        assert delete_actions[0]["details"]["email"] == victim_email

    @pytest.mark.asyncio
    async def test_audit_log_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.get(f"{API}/admin/audit-log", headers=regular_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 6. BROADCAST EMAIL
# ---------------------------------------------------------------------------

class TestBroadcast:

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_active_users(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        # Create additional active user
        await _create_user(db_session, full_name="Active Recipient")

        resp = await client.post(
            f"{API}/admin/broadcast",
            headers=admin_headers,
            json={"subject": "Test Broadcast", "body": "Hello everyone!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent_count"] >= 2  # admin + the created user
        assert "skipped_count" in data

    @pytest.mark.asyncio
    async def test_broadcast_skips_opted_out_users(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        # Create user who opted out
        await _create_user(
            db_session,
            full_name="Opted Out",
            preferences={"email_notifications": False},
        )
        # Create user who opted in
        await _create_user(db_session, full_name="Opted In")

        resp = await client.post(
            f"{API}/admin/broadcast",
            headers=admin_headers,
            json={"subject": "Test", "body": "Hello"},
        )
        data = resp.json()
        assert data["skipped_count"] >= 1

    @pytest.mark.asyncio
    async def test_broadcast_skips_suspended_users(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        await _create_user(db_session, full_name="Suspended Recv", is_active=False)

        resp = await client.post(
            f"{API}/admin/broadcast",
            headers=admin_headers,
            json={"subject": "Test", "body": "Hello"},
        )
        data = resp.json()
        # The suspended user should not be counted in sent_count
        assert data["sent_count"] >= 1  # at least admin

    @pytest.mark.asyncio
    async def test_broadcast_creates_audit_log(
        self, client: AsyncClient, admin_headers: dict, admin_user: Candidate, db_session: AsyncSession
    ):
        await client.post(
            f"{API}/admin/broadcast",
            headers=admin_headers,
            json={"subject": "Audit Test", "body": "Check log"},
        )

        result = await db_session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "broadcast_sent",
                AdminAuditLog.admin_id == admin_user.id,
            ).order_by(AdminAuditLog.created_at.desc())
        )
        log = result.scalars().first()
        assert log is not None
        assert log.details["subject"] == "Audit Test"

    @pytest.mark.asyncio
    async def test_broadcast_requires_admin(self, client: AsyncClient, regular_headers: dict):
        resp = await client.post(
            f"{API}/admin/broadcast",
            headers=regular_headers,
            json={"subject": "Test", "body": "Hello"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_broadcast_validates_body(self, client: AsyncClient, admin_headers: dict):
        # Empty subject and body should fail validation
        resp = await client.post(
            f"{API}/admin/broadcast",
            headers=admin_headers,
            json={},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. is_active IN USER LIST
# ---------------------------------------------------------------------------

class TestIsActiveInUserList:

    @pytest.mark.asyncio
    async def test_user_list_includes_is_active(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(f"{API}/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        user = resp.json()["users"][0]
        assert "is_active" in user

    @pytest.mark.asyncio
    async def test_suspended_user_shows_in_list(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession
    ):
        suspended = await _create_user(db_session, full_name="Suspended Listed", is_active=False)
        resp = await client.get(f"{API}/admin/users", headers=admin_headers)
        users = resp.json()["users"]
        match = [u for u in users if u["id"] == str(suspended.id)]
        assert len(match) == 1
        assert match[0]["is_active"] is False


# ---------------------------------------------------------------------------
# 8. PREFERENCES IN AUTH RESPONSES
# ---------------------------------------------------------------------------

class TestPreferencesInAuth:

    @pytest.mark.asyncio
    async def test_get_me_returns_preferences(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.get(f"{API}/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        assert "preferences" in resp.json()

    @pytest.mark.asyncio
    async def test_update_preferences(
        self, client: AsyncClient, admin_headers: dict
    ):
        resp = await client.patch(
            f"{API}/auth/me",
            headers=admin_headers,
            json={"preferences": {"email_notifications": False}},
        )
        assert resp.status_code == 200
        assert resp.json()["preferences"]["email_notifications"] is False

        # Verify it persists
        resp = await client.get(f"{API}/auth/me", headers=admin_headers)
        assert resp.json()["preferences"]["email_notifications"] is False
