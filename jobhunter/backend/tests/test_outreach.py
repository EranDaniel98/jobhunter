import pytest
from httpx import AsyncClient

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_list_outreach_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/outreach", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_draft_message_invalid_contact(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"{API}/outreach/draft",
        headers=auth_headers,
        json={"contact_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_message_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get(
        f"{API}/outreach/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_outreach_full_flow(client: AsyncClient, auth_headers: dict):
    """Test: add company → get contacts → draft → edit → verify draft updated."""
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

    # Draft outreach
    resp = await client.post(
        f"{API}/outreach/draft",
        headers=auth_headers,
        json={"contact_id": contact_id},
    )
    assert resp.status_code == 201
    draft = resp.json()
    assert draft["status"] == "draft"
    assert draft["channel"] == "email"
    assert draft["body"]  # Should have content

    message_id = draft["id"]

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
