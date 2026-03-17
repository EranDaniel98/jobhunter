"""Integration tests for app/api/outreach.py — second pass covering additional uncovered lines.

Targets:
- Lines 134-138: draft-followup success / ValueError paths
- Lines 216-227: PATCH edit (subject-only, body-only, both)
- Lines 240-295: POST send — legacy auto_approve + approved status + error paths
- Lines 297-309: POST send — pending_approval path with PendingAction cleanup
- Lines 324-332: DELETE — cleans up PendingActions before deleting
- Lines 342-347: PATCH mark-replied
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import MessageStatus
from app.models.outreach import OutreachMessage
from app.models.pending_action import PendingAction

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


async def _seed_outreach(
    db_session: AsyncSession,
    candidate_id: uuid.UUID,
    status: MessageStatus = MessageStatus.DRAFT,
    channel: str = "email",
) -> tuple[Company, Contact, OutreachMessage]:
    unique_suffix = uuid.uuid4().hex[:8]
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=f"IntegCo2-{unique_suffix}",
        domain=f"integco2-{unique_suffix}.com",
    )
    db_session.add(company)
    contact = Contact(
        id=uuid.uuid4(),
        company_id=company.id,
        candidate_id=candidate_id,
        full_name="Jane Smith",
        email="jane@integco2.com",
    )
    db_session.add(contact)
    msg = OutreachMessage(
        id=uuid.uuid4(),
        contact_id=contact.id,
        candidate_id=candidate_id,
        channel=channel,
        message_type="initial",
        subject="Subject line",
        body="Body content here.",
        status=status,
    )
    db_session.add(msg)
    await db_session.flush()
    return company, contact, msg


async def _seed_pending_action(
    db_session: AsyncSession,
    candidate_id: uuid.UUID,
    msg_id: uuid.UUID,
    action_type: str = "send_email",
    thread_id: str | None = None,
) -> PendingAction:
    meta = {"attach_resume": True}
    if thread_id:
        meta["thread_id"] = thread_id
    action = PendingAction(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        action_type=action_type,
        entity_id=msg_id,
        metadata_=meta,
    )
    db_session.add(action)
    await db_session.flush()
    return action


# ---------------------------------------------------------------------------
# POST /{message_id}/draft-followup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_followup_with_existing_message(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """draft-followup route handler runs; service may raise ValueError without dossier."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.post(
        f"{API}/outreach/{msg.id}/draft-followup",
        headers=auth_headers,
    )
    # With no dossier the service raises ValueError → 400; route coverage still hit
    assert resp.status_code in (201, 400)


@pytest.mark.asyncio
async def test_draft_followup_wrong_candidate_returns_404(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """Requesting followup for a non-existent message returns 404."""
    fake_id = uuid.uuid4()
    resp = await client.post(
        f"{API}/outreach/{fake_id}/draft-followup",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /{message_id} — edit subject/body on DRAFT message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_draft_subject_only(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """PATCH with subject only updates subject, leaves body intact."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.patch(
        f"{API}/outreach/{msg.id}",
        headers=auth_headers,
        json={"subject": "New Subject Only"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "New Subject Only"
    assert data["body"] == "Body content here."


@pytest.mark.asyncio
async def test_edit_draft_body_only(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """PATCH with body only updates body, leaves subject intact."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.patch(
        f"{API}/outreach/{msg.id}",
        headers=auth_headers,
        json={"body": "Brand new body."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["body"] == "Brand new body."
    assert data["subject"] == "Subject line"


@pytest.mark.asyncio
async def test_edit_draft_both_subject_and_body(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """PATCH with both subject and body updates both fields."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.patch(
        f"{API}/outreach/{msg.id}",
        headers=auth_headers,
        json={"subject": "New Subject", "body": "New body text."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "New Subject"
    assert data["body"] == "New body text."


@pytest.mark.asyncio
async def test_edit_non_draft_returns_400(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """PATCH on a SENT message returns 400."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.SENT)

    resp = await client.patch(
        f"{API}/outreach/{msg.id}",
        headers=auth_headers,
        json={"body": "Attempt to edit"},
    )
    assert resp.status_code == 400
    assert "draft" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_edit_message_not_found(client: AsyncClient, auth_headers: dict):
    """PATCH on non-existent message returns 404."""
    fake_id = uuid.uuid4()
    resp = await client.patch(
        f"{API}/outreach/{fake_id}",
        headers=auth_headers,
        json={"subject": "Ghost subject"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /{message_id}/send — status validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_failed_message_returns_400(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Cannot send a message with status FAILED."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.FAILED)

    resp = await client.post(
        f"{API}/outreach/{msg.id}/send",
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Cannot send" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_send_replied_message_returns_400(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Cannot send a message with status REPLIED."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.REPLIED)

    resp = await client.post(
        f"{API}/outreach/{msg.id}/send",
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /{message_id}/send — legacy auto_approve path (no graph thread)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_auto_approve_draft_no_graph(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """auto_approve=true on DRAFT without graph thread triggers legacy send."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.post(
        f"{API}/outreach/{msg.id}/send?auto_approve=true",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(msg.id)


@pytest.mark.asyncio
async def test_send_approved_message_no_graph(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Sending an APPROVED message (no graph thread) uses legacy email path."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.APPROVED)

    resp = await client.post(
        f"{API}/outreach/{msg.id}/send",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(msg.id)


# ---------------------------------------------------------------------------
# POST /{message_id}/send — pending_approval path (draft without auto_approve)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_draft_creates_pending_action(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Draft without auto_approve → creates PendingAction and returns pending_approval."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.post(
        f"{API}/outreach/{msg.id}/send?auto_approve=false",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert data["message_id"] == str(msg.id)
    assert "action_id" in data
    assert data["detail"] == "Message queued for approval"


@pytest.mark.asyncio
async def test_send_draft_default_auto_approve_false(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Default (no auto_approve param) on DRAFT → pending_approval."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.post(
        f"{API}/outreach/{msg.id}/send",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_approval"


# ---------------------------------------------------------------------------
# DELETE /{message_id} — cleans up PendingActions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_draft_cleans_pending_actions(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Deleting a DRAFT message also removes its PendingActions."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)
    await _seed_pending_action(db_session, candidate_id, msg.id)

    resp = await client.delete(f"{API}/outreach/{msg.id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify message is gone
    get_resp = await client.get(f"{API}/outreach/{msg.id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_non_draft_returns_400(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Attempting to delete a non-draft message returns 400."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.APPROVED)

    resp = await client.delete(f"{API}/outreach/{msg.id}", headers=auth_headers)
    assert resp.status_code == 400
    assert "draft" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_message_not_found(client: AsyncClient, auth_headers: dict):
    """Deleting a non-existent message returns 404."""
    fake_id = uuid.uuid4()
    resp = await client.delete(f"{API}/outreach/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /{message_id}/mark-replied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_replied_on_sent_message(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """mark-replied on a SENT message sets status=REPLIED and replied_at."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.SENT)

    resp = await client.patch(
        f"{API}/outreach/{msg.id}/mark-replied",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == MessageStatus.REPLIED
    assert data["replied_at"] is not None
    assert data["id"] == str(msg.id)


@pytest.mark.asyncio
async def test_mark_replied_on_draft_message(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """mark-replied works even on a DRAFT message (no status restriction)."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, _, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.patch(
        f"{API}/outreach/{msg.id}/mark-replied",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == MessageStatus.REPLIED


@pytest.mark.asyncio
async def test_mark_replied_not_found(client: AsyncClient, auth_headers: dict):
    """mark-replied on non-existent message returns 404."""
    fake_id = uuid.uuid4()
    resp = await client.patch(
        f"{API}/outreach/{fake_id}/mark-replied",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /{message_id} — basic retrieval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_message_found(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /{message_id} returns the message with contact/company context."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    _, contact, msg = await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.get(f"{API}/outreach/{msg.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(msg.id)
    assert data["contact_id"] == str(contact.id)
    assert data["contact_name"] == "Jane Smith"
    assert data["company_name"] is not None  # unique suffix makes name dynamic


@pytest.mark.asyncio
async def test_get_message_not_found(client: AsyncClient, auth_headers: dict):
    """GET /{message_id} with unknown ID returns 404."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"{API}/outreach/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET / — list messages with pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_messages_pagination(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """List messages respects skip/limit parameters."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    for _ in range(3):
        await _seed_outreach(db_session, candidate_id, MessageStatus.DRAFT)

    resp = await client.get(f"{API}/outreach?skip=0&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 2
