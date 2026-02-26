import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

API = settings.API_V1_PREFIX


async def _draft_via_service(db_session: AsyncSession, candidate_id, contact_id):
    """Create a draft message directly via service (bypassing async graph)."""
    from app.services.outreach_service import draft_message
    return await draft_message(db_session, candidate_id, contact_id)


@pytest.mark.asyncio
async def test_list_outreach_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/outreach", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_draft_message_returns_202(client: AsyncClient, auth_headers: dict):
    """POST /draft now returns 202 with status=drafting and a thread_id."""
    resp = await client.post(
        f"{API}/outreach/draft",
        headers=auth_headers,
        json={"contact_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "drafting"
    assert "thread_id" in data


@pytest.mark.asyncio
async def test_get_message_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get(
        f"{API}/outreach/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_outreach_draft_and_edit(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Test: create draft via service → edit via API → verify updated."""
    # Add company
    resp = await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "stripe.com"},
    )
    assert resp.status_code == 201
    company_id = resp.json()["id"]

    # Get contacts
    resp = await client.get(
        f"{API}/companies/{company_id}/contacts",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    contacts = resp.json()
    assert len(contacts) > 0
    contact_id = contacts[0]["id"]

    # Get candidate_id from auth
    me_resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    candidate_id = uuid.UUID(me_resp.json()["id"])

    # Create draft directly via service (sync, not async graph)
    msg = await _draft_via_service(db_session, candidate_id, uuid.UUID(contact_id))
    message_id = str(msg.id)

    # Edit the draft
    resp = await client.patch(
        f"{API}/outreach/{message_id}",
        headers=auth_headers,
        json={"body": "Custom edited message body."},
    )
    assert resp.status_code == 200
    assert resp.json()["body"] == "Custom edited message body."

    # Get the message
    resp = await client.get(f"{API}/outreach/{message_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["body"] == "Custom edited message body."


@pytest.mark.asyncio
async def test_delete_draft_message(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Test: create draft via service → delete via API → verify gone."""
    resp = await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "deleteme.com"},
    )
    assert resp.status_code == 201
    company_id = resp.json()["id"]

    resp = await client.get(
        f"{API}/companies/{company_id}/contacts", headers=auth_headers
    )
    contacts = resp.json()
    assert len(contacts) > 0
    contact_id = contacts[0]["id"]

    me_resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    candidate_id = uuid.UUID(me_resp.json()["id"])

    msg = await _draft_via_service(db_session, candidate_id, uuid.UUID(contact_id))
    message_id = str(msg.id)

    # Delete the draft
    resp = await client.delete(
        f"{API}/outreach/{message_id}", headers=auth_headers
    )
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get(
        f"{API}/outreach/{message_id}", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_sent_message_fails(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Test: cannot delete a sent (non-draft) message."""
    resp = await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "github.com"},
    )
    assert resp.status_code == 201
    company_id = resp.json()["id"]

    resp = await client.get(
        f"{API}/companies/{company_id}/contacts", headers=auth_headers
    )
    contacts = resp.json()
    assert len(contacts) > 0
    contact_id = contacts[0]["id"]

    me_resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    candidate_id = uuid.UUID(me_resp.json()["id"])

    msg = await _draft_via_service(db_session, candidate_id, uuid.UUID(contact_id))
    message_id = str(msg.id)

    # Send the message (auto_approve via legacy path — no graph thread)
    resp = await client.post(
        f"{API}/outreach/{message_id}/send?auto_approve=true", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"

    # Attempt to delete sent message — should fail
    resp = await client.delete(
        f"{API}/outreach/{message_id}", headers=auth_headers
    )
    assert resp.status_code == 400
    assert "draft" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_nonexistent_message(client: AsyncClient, auth_headers: dict):
    """Test: deleting a message that doesn't exist returns 404."""
    resp = await client.delete(
        f"{API}/outreach/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404
