"""Extended unit tests for the outreach API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.outreach import OutreachMessage

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_candidate_id(client: AsyncClient, headers: dict) -> uuid.UUID:
    me = await client.get(f"{API}/auth/me", headers=headers)
    return uuid.UUID(me.json()["id"])


async def _create_company_and_contact(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    domain: str | None = None,
) -> tuple[Company, Contact]:
    tag = uuid.uuid4().hex[:8]
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=f"OutreachCo-{tag}",
        domain=domain or f"outreach-{tag}.com",
    )
    db.add(company)
    await db.flush()

    contact = Contact(
        id=uuid.uuid4(),
        company_id=company.id,
        candidate_id=candidate_id,
        full_name="Test Contact",
        email=f"contact-{tag}@outreach.com",
    )
    db.add(contact)
    await db.flush()
    return company, contact


async def _create_draft_message(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: str = "Hello, I'd like to connect.",
    status: str = "draft",
) -> OutreachMessage:
    msg = OutreachMessage(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        contact_id=contact_id,
        channel="email",
        message_type="initial",
        subject="Test Subject",
        body=body,
        status=status,
    )
    db.add(msg)
    await db.flush()
    return msg


# ---------------------------------------------------------------------------
# POST /outreach/draft
# ---------------------------------------------------------------------------


class TestOutreachDraft:
    @pytest.mark.asyncio
    async def test_draft_returns_202(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            f"{API}/outreach/draft",
            headers=auth_headers,
            json={"contact_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "drafting"
        assert "thread_id" in data

    @pytest.mark.asyncio
    async def test_draft_with_language(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            f"{API}/outreach/draft",
            headers=auth_headers,
            json={"contact_id": str(uuid.uuid4()), "language": "es"},
        )
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_draft_requires_contact_id(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            f"{API}/outreach/draft",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_draft_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/outreach/draft",
            json={"contact_id": str(uuid.uuid4())},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /outreach (list messages)
# ---------------------------------------------------------------------------


class TestOutreachListMessages:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(f"{API}/outreach", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_shows_messages(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        await _create_draft_message(db_session, candidate_id, contact.id)

        resp = await client.get(f"{API}/outreach", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        await _create_draft_message(db_session, candidate_id, contact.id, status="draft")
        await _create_draft_message(db_session, candidate_id, contact.id, status="sent")

        resp = await client.get(f"{API}/outreach", headers=auth_headers, params={"status": "draft"})
        data = resp.json()
        assert all(m["status"] == "draft" for m in data)

    @pytest.mark.asyncio
    async def test_list_filter_by_channel(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        await _create_draft_message(db_session, candidate_id, contact.id)

        resp = await client.get(f"{API}/outreach", headers=auth_headers, params={"channel": "email"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(m["channel"] == "email" for m in data)

    @pytest.mark.asyncio
    async def test_list_isolation(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, invite_code: str
    ):
        """Messages from another user must not appear."""
        other_email = f"other-{uuid.uuid4().hex[:8]}@test.com"
        await client.post(
            f"{API}/auth/register",
            json={
                "email": other_email,
                "password": "Testpass123",
                "full_name": "Other",
                "invite_code": invite_code,
            },
        )
        other_resp = await client.post(
            f"{API}/auth/login",
            json={"email": other_email, "password": "Testpass123"},
        )
        other_id = uuid.UUID(
            (
                await client.get(
                    f"{API}/auth/me", headers={"Authorization": f"Bearer {other_resp.json()['access_token']}"}
                )
            ).json()["id"]
        )
        _, other_contact = await _create_company_and_contact(db_session, other_id)
        other_msg = await _create_draft_message(db_session, other_id, other_contact.id)

        resp = await client.get(f"{API}/outreach", headers=auth_headers)
        ids = [m["id"] for m in resp.json()]
        assert str(other_msg.id) not in ids

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{API}/outreach")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /outreach/{message_id}
# ---------------------------------------------------------------------------


class TestOutreachGetMessage:
    @pytest.mark.asyncio
    async def test_get_message_returns_data(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, body="Hello!")

        resp = await client.get(f"{API}/outreach/{msg.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(msg.id)
        assert data["body"] == "Hello!"

    @pytest.mark.asyncio
    async def test_get_message_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(f"{API}/outreach/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_message_isolation(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, invite_code: str
    ):
        """Cannot access another user's message."""
        other_email = f"iso-{uuid.uuid4().hex[:8]}@test.com"
        await client.post(
            f"{API}/auth/register",
            json={
                "email": other_email,
                "password": "Testpass123",
                "full_name": "Iso User",
                "invite_code": invite_code,
            },
        )
        other_resp = await client.post(
            f"{API}/auth/login",
            json={"email": other_email, "password": "Testpass123"},
        )
        other_headers = {"Authorization": f"Bearer {other_resp.json()['access_token']}"}
        other_id = uuid.UUID((await client.get(f"{API}/auth/me", headers=other_headers)).json()["id"])

        _, other_contact = await _create_company_and_contact(db_session, other_id)
        other_msg = await _create_draft_message(db_session, other_id, other_contact.id)

        resp = await client.get(f"{API}/outreach/{other_msg.id}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /outreach/{message_id}/send
# ---------------------------------------------------------------------------


class TestOutreachSendMessage:
    @pytest.mark.asyncio
    async def test_send_draft_creates_pending_action(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """Sending a draft (without auto_approve) creates a pending approval action."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        resp = await client.post(
            f"{API}/outreach/{msg.id}/send",
            headers=auth_headers,
            params={"auto_approve": "false"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_approval"
        assert "action_id" in data

    @pytest.mark.asyncio
    async def test_send_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(f"{API}/outreach/{uuid.uuid4()}/send", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_send_wrong_status_fails(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """Cannot send a message that is already sent."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, status="sent")

        resp = await client.post(f"{API}/outreach/{msg.id}/send", headers=auth_headers)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_requires_auth(self, client: AsyncClient):
        resp = await client.post(f"{API}/outreach/{uuid.uuid4()}/send")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /outreach/{message_id} (edit)
# ---------------------------------------------------------------------------


class TestOutreachEditMessage:
    @pytest.mark.asyncio
    async def test_edit_draft_body(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        resp = await client.patch(
            f"{API}/outreach/{msg.id}",
            headers=auth_headers,
            json={"body": "Updated body content."},
        )
        assert resp.status_code == 200
        assert resp.json()["body"] == "Updated body content."

    @pytest.mark.asyncio
    async def test_edit_non_draft_fails(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, status="sent")

        resp = await client.patch(
            f"{API}/outreach/{msg.id}",
            headers=auth_headers,
            json={"body": "Try to edit sent message."},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /outreach/{message_id}
# ---------------------------------------------------------------------------


class TestOutreachDeleteMessage:
    @pytest.mark.asyncio
    async def test_delete_draft(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        resp = await client.delete(f"{API}/outreach/{msg.id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get(f"{API}/outreach/{msg.id}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_non_draft_fails(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, status="sent")

        resp = await client.delete(f"{API}/outreach/{msg.id}", headers=auth_headers)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.delete(f"{API}/outreach/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /outreach/{message_id}/mark-replied
# ---------------------------------------------------------------------------


class TestOutreachMarkReplied:
    @pytest.mark.asyncio
    async def test_mark_replied(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, status="sent")

        resp = await client.patch(f"{API}/outreach/{msg.id}/mark-replied", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "replied"
        assert data["replied_at"] is not None
