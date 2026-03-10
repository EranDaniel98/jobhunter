"""Tests for webhook endpoints: Resend webhook and unsubscribe."""
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.email_service import generate_unsubscribe_link, _sign_email

API = settings.API_V1_PREFIX


# ── Resend Webhook ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_webhook_valid_payload(client: AsyncClient, redis):
    """POST /webhooks/resend with valid payload returns 200."""
    payload = {
        "type": "email.delivered",
        "data": {
            "email_id": f"msg_{uuid.uuid4().hex[:12]}",
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "to": ["recipient@example.com"],
        },
    }
    resp = await client.post(
        f"{API}/webhooks/resend",
        content=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "svix-id": "test-id",
            "svix-timestamp": "1234567890",
            "svix-signature": "v1,test-signature",
        },
    )
    # ResendStub.verify_webhook just json-parses the payload, so this should succeed
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_resend_webhook_missing_email_id(client: AsyncClient, redis):
    """Webhook with missing email_id in data is accepted but no-ops."""
    payload = {
        "type": "email.delivered",
        "data": {},  # no email_id
    }
    resp = await client.post(
        f"{API}/webhooks/resend",
        content=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "svix-id": "test-id-2",
            "svix-timestamp": "1234567890",
            "svix-signature": "v1,test-signature",
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_resend_webhook_unknown_event_type(client: AsyncClient, redis):
    """Webhook with unknown event type is accepted gracefully."""
    payload = {
        "type": "email.unknown_future_event",
        "data": {
            "email_id": f"msg_{uuid.uuid4().hex[:12]}",
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        },
    }
    resp = await client.post(
        f"{API}/webhooks/resend",
        content=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "svix-id": "test-id-3",
            "svix-timestamp": "1234567890",
            "svix-signature": "v1,test-sig",
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_resend_webhook_duplicate_event_skipped(client: AsyncClient, redis):
    """Sending the same webhook event twice: second is deduplicated."""
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    payload = {
        "type": "email.delivered",
        "data": {
            "email_id": f"msg_{uuid.uuid4().hex[:12]}",
            "event_id": event_id,
        },
    }
    body = json.dumps(payload)
    headers = {
        "Content-Type": "application/json",
        "svix-id": "test-dup",
        "svix-timestamp": "1234567890",
        "svix-signature": "v1,test",
    }

    # First call
    resp1 = await client.post(f"{API}/webhooks/resend", content=body, headers=headers)
    assert resp1.status_code == 200

    # Second call with same event_id
    resp2 = await client.post(f"{API}/webhooks/resend", content=body, headers=headers)
    assert resp2.status_code == 200  # accepted but skipped internally


# ── Unsubscribe ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unsubscribe_valid_token(client: AsyncClient):
    """GET /unsubscribe/{token} with valid signed token returns success."""
    email = "unsub@example.com"
    token = _sign_email(email)

    resp = await client.get(f"{API}/unsubscribe/{token}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unsubscribed"


@pytest.mark.asyncio
async def test_unsubscribe_invalid_token(client: AsyncClient):
    """GET /unsubscribe/{token} with invalid token returns 400."""
    resp = await client.get(f"{API}/unsubscribe/invalid-token-here")
    assert resp.status_code == 400
    assert "Invalid" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unsubscribe_idempotent(client: AsyncClient):
    """Unsubscribing twice with the same token succeeds both times (idempotent)."""
    email = "double-unsub@example.com"
    token = _sign_email(email)

    resp1 = await client.get(f"{API}/unsubscribe/{token}")
    assert resp1.status_code == 200

    resp2 = await client.get(f"{API}/unsubscribe/{token}")
    assert resp2.status_code == 200
