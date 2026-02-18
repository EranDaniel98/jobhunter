import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.email_service import generate_unsubscribe_link, verify_unsubscribe_token

API = settings.API_V1_PREFIX


def test_unsubscribe_token_round_trip():
    email = "test@example.com"
    link = generate_unsubscribe_link(email)
    # Extract token from URL
    token = link.split("/unsubscribe/")[-1]
    assert verify_unsubscribe_token(token) == email


def test_unsubscribe_token_invalid():
    assert verify_unsubscribe_token("invalid-token") is None
    assert verify_unsubscribe_token("bad:signature:email") is None


@pytest.mark.asyncio
async def test_unsubscribe_endpoint(client: AsyncClient):
    email = "unsub@example.com"
    link = generate_unsubscribe_link(email)
    token = link.split("/unsubscribe/")[-1]

    resp = await client.get(f"{API}/unsubscribe/{token}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unsubscribed"


@pytest.mark.asyncio
async def test_unsubscribe_invalid_token(client: AsyncClient):
    resp = await client.get(f"{API}/unsubscribe/invalidtoken")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_no_signature(client: AsyncClient):
    resp = await client.post(
        f"{API}/webhooks/resend",
        json={"type": "email.delivered", "data": {"email_id": "test123"}},
    )
    # Mock client should accept any signature
    assert resp.status_code == 200
