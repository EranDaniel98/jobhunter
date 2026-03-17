import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.outreach import OutreachMessage

API = settings.API_V1_PREFIX


@pytest_asyncio.fixture
async def approval_data(db_session: AsyncSession, auth_headers: dict, client: AsyncClient):
    """Create test data: candidate (from auth), company, contact, draft message."""
    # Extract candidate_id from auth token
    from app.utils.security import decode_token
    token = auth_headers["Authorization"].replace("Bearer ", "")
    payload = decode_token(token)
    candidate_id = uuid.UUID(payload["sub"])

    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name="ApprovalCo",
        domain="approvalco.com",
        status="approved",
        research_status="completed",
    )
    db_session.add(company)

    contact = Contact(
        id=uuid.uuid4(),
        company_id=company.id,
        candidate_id=candidate_id,
        full_name="Approval Contact",
        email="test@approvalco.com",
    )
    db_session.add(contact)

    message = OutreachMessage(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        contact_id=contact.id,
        channel="email",
        message_type="initial",
        subject="Test approval subject",
        body="Test approval body",
        status="draft",
    )
    db_session.add(message)
    await db_session.flush()

    return {
        "candidate_id": candidate_id,
        "company": company,
        "contact": contact,
        "message": message,
    }


@pytest.mark.asyncio
async def test_list_approvals_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/approvals", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["actions"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_count_pending_zero(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/approvals/count", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_approve_nonexistent(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"{API}/approvals/{fake_id}/approve", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_nonexistent(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"{API}/approvals/{fake_id}/reject", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_creates_pending_action(client: AsyncClient, auth_headers: dict, approval_data):
    """Sending without auto_approve creates a PendingAction instead of sending."""
    message_id = str(approval_data["message"].id)

    resp = await client.post(
        f"{API}/outreach/{message_id}/send",
        headers=auth_headers,
        params={"auto_approve": "false"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert data["action_id"]

    # Verify pending count increased
    resp = await client.get(f"{API}/approvals/count", headers=auth_headers)
    assert resp.json()["count"] >= 1


@pytest.mark.asyncio
async def test_send_auto_approve_sends_immediately(client: AsyncClient, auth_headers: dict, approval_data):
    """Sending with auto_approve=true sends immediately."""
    message_id = str(approval_data["message"].id)

    resp = await client.post(
        f"{API}/outreach/{message_id}/send",
        headers=auth_headers,
        params={"auto_approve": "true"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"


@pytest.mark.asyncio
async def test_approve_action_flow(client: AsyncClient, auth_headers: dict, approval_data):
    """Create pending action via send, then approve it."""
    message_id = str(approval_data["message"].id)

    # Create pending action
    resp = await client.post(
        f"{API}/outreach/{message_id}/send",
        headers=auth_headers,
        params={"auto_approve": "false"},
    )
    assert resp.status_code == 200
    action_id = resp.json()["action_id"]

    # Verify it appears in the list
    resp = await client.get(f"{API}/approvals", headers=auth_headers, params={"status": "pending"})
    assert resp.status_code == 200
    actions = resp.json()["actions"]
    assert any(a["id"] == action_id for a in actions)

    # Get single action
    resp = await client.get(f"{API}/approvals/{action_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == action_id
    assert resp.json()["message_subject"] == "Test approval subject"

    # Approve it
    resp = await client.post(f"{API}/approvals/{action_id}/approve", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_action_flow(client: AsyncClient, auth_headers: dict, approval_data):
    """Create pending action, then reject it."""
    message_id = str(approval_data["message"].id)

    resp = await client.post(
        f"{API}/outreach/{message_id}/send",
        headers=auth_headers,
        params={"auto_approve": "false"},
    )
    assert resp.status_code == 200
    action_id = resp.json()["action_id"]

    resp = await client.post(f"{API}/approvals/{action_id}/reject", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
