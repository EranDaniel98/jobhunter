"""Integration tests for app/api/plans.py — targeting uncovered lines.

Targets:
- POST /billing/create-checkout-session — with mock Stripe (success, invalid tier, free tier, error)
- GET /billing/portal — with/without stripe_customer_id (mock Stripe)
- GET /billing/subscription — free and paid candidates
- POST /billing/webhooks/stripe — invalid signature, generic exception
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate
from app.plans import PlanTier

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


# ---------------------------------------------------------------------------
# GET /plans (public, no auth)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_plans_public(client: AsyncClient):
    """GET /plans returns all plans without auth."""
    resp = await client.get(f"{API}/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert len(plans) == 3
    tiers = {p["tier"] for p in plans}
    assert tiers == {"free", "explorer", "hunter"}


@pytest.mark.asyncio
async def test_list_plans_no_openai_in_limits(client: AsyncClient):
    """openai is excluded from user-visible plan limits."""
    resp = await client.get(f"{API}/plans")
    for plan in resp.json():
        assert "openai" not in plan["limits"]


# ---------------------------------------------------------------------------
# POST /billing/create-checkout-session — no Stripe key (coming_soon)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_coming_soon_when_no_stripe_key(client: AsyncClient, auth_headers: dict):
    """When STRIPE_SECRET_KEY is empty, returns coming_soon status."""
    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = ""
    try:
        resp = await client.post(
            f"{API}/billing/create-checkout-session",
            headers=auth_headers,
            json={"tier": "explorer"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "coming_soon"
    finally:
        settings.STRIPE_SECRET_KEY = original


# ---------------------------------------------------------------------------
# POST /billing/create-checkout-session — with Stripe (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_invalid_tier_returns_400(client: AsyncClient, auth_headers: dict):
    """Invalid tier value returns 400."""
    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = "sk_test_fake"
    try:
        resp = await client.post(
            f"{API}/billing/create-checkout-session",
            headers=auth_headers,
            json={"tier": "ultra_premium"},
        )
        assert resp.status_code == 400
        assert "Invalid tier" in resp.json()["detail"]
    finally:
        settings.STRIPE_SECRET_KEY = original


@pytest.mark.asyncio
async def test_checkout_free_tier_returns_400(client: AsyncClient, auth_headers: dict):
    """Cannot checkout for the free tier."""
    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = "sk_test_fake"
    try:
        resp = await client.post(
            f"{API}/billing/create-checkout-session",
            headers=auth_headers,
            json={"tier": "free"},
        )
        assert resp.status_code == 400
        assert "free tier" in resp.json()["detail"].lower()
    finally:
        settings.STRIPE_SECRET_KEY = original


@pytest.mark.asyncio
async def test_checkout_with_stripe_creates_session(client: AsyncClient, auth_headers: dict):
    """With Stripe mocked, checkout session creates and returns URL."""
    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = "sk_test_fake"
    try:
        with patch("app.services.billing_service.stripe") as mock_stripe:
            mock_stripe.Customer.create.return_value = SimpleNamespace(id="cus_mock")
            mock_stripe.checkout.Session.create.return_value = SimpleNamespace(
                url="https://checkout.stripe.com/test_session"
            )

            resp = await client.post(
                f"{API}/billing/create-checkout-session",
                headers=auth_headers,
                json={"tier": "explorer"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["url"] == "https://checkout.stripe.com/test_session"
    finally:
        settings.STRIPE_SECRET_KEY = original


@pytest.mark.asyncio
async def test_checkout_stripe_error_returns_500(client: AsyncClient, auth_headers: dict):
    """When billing_service raises unexpected exception, returns 500."""
    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = "sk_test_fake"
    try:
        with patch(
            "app.services.billing_service.create_checkout_session",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Stripe network error"),
        ):
            resp = await client.post(
                f"{API}/billing/create-checkout-session",
                headers=auth_headers,
                json={"tier": "hunter"},
            )
            assert resp.status_code == 500
            assert "checkout session" in resp.json()["detail"].lower()
    finally:
        settings.STRIPE_SECRET_KEY = original


@pytest.mark.asyncio
async def test_checkout_value_error_returns_400(client: AsyncClient, auth_headers: dict):
    """When billing_service raises ValueError, returns 400."""
    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = "sk_test_fake"
    try:
        with patch(
            "app.services.billing_service.create_checkout_session",
            new_callable=AsyncMock,
            side_effect=ValueError("No Stripe price configured for free"),
        ):
            resp = await client.post(
                f"{API}/billing/create-checkout-session",
                headers=auth_headers,
                json={"tier": "explorer"},
            )
            assert resp.status_code == 400
            assert "No Stripe price" in resp.json()["detail"]
    finally:
        settings.STRIPE_SECRET_KEY = original


# ---------------------------------------------------------------------------
# GET /billing/portal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portal_coming_soon_when_no_stripe_key(client: AsyncClient, auth_headers: dict):
    """Portal returns coming_soon when STRIPE_SECRET_KEY not set."""
    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = ""
    try:
        resp = await client.get(f"{API}/billing/portal", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "coming_soon"
    finally:
        settings.STRIPE_SECRET_KEY = original


@pytest.mark.asyncio
async def test_portal_success_with_stripe_customer(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Portal returns URL when candidate has Stripe customer ID."""
    candidate_id = await _get_candidate_id(client, auth_headers)

    # Set stripe_customer_id on the candidate
    result = await db_session.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one()
    candidate.stripe_customer_id = "cus_portal_test"
    await db_session.commit()

    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = "sk_test_fake"
    try:
        with patch("app.services.billing_service.stripe") as mock_stripe:
            mock_stripe.billing_portal.Session.create.return_value = SimpleNamespace(
                url="https://billing.stripe.com/portal_session"
            )
            resp = await client.get(f"{API}/billing/portal", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["url"] == "https://billing.stripe.com/portal_session"
    finally:
        settings.STRIPE_SECRET_KEY = original


@pytest.mark.asyncio
async def test_portal_no_customer_returns_400(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Portal returns 400 when candidate has no Stripe customer ID."""
    candidate_id = await _get_candidate_id(client, auth_headers)

    # Ensure no stripe_customer_id
    result = await db_session.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one()
    candidate.stripe_customer_id = None
    await db_session.commit()

    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = "sk_test_fake"
    try:
        resp = await client.get(f"{API}/billing/portal", headers=auth_headers)
        assert resp.status_code == 400
        assert "billing account" in resp.json()["detail"].lower()
    finally:
        settings.STRIPE_SECRET_KEY = original


@pytest.mark.asyncio
async def test_portal_stripe_error_returns_500(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Portal returns 500 on unexpected Stripe error."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    result = await db_session.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one()
    candidate.stripe_customer_id = "cus_error_test"
    await db_session.commit()

    original = settings.STRIPE_SECRET_KEY
    settings.STRIPE_SECRET_KEY = "sk_test_fake"
    try:
        with patch(
            "app.services.billing_service.create_portal_session",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Connection refused"),
        ):
            resp = await client.get(f"{API}/billing/portal", headers=auth_headers)
            assert resp.status_code == 500
            assert "portal" in resp.json()["detail"].lower()
    finally:
        settings.STRIPE_SECRET_KEY = original


# ---------------------------------------------------------------------------
# GET /billing/subscription
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_subscription_free_user(client: AsyncClient, auth_headers: dict):
    """Free user subscription returns tier=free."""
    resp = await client.get(f"{API}/billing/subscription", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "free"
    assert data["current_period_end"] is None
    assert data["stripe_subscription_id"] is None


@pytest.mark.asyncio
async def test_get_subscription_paid_user(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Paid user subscription returns tier and subscription info."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    result = await db_session.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one()
    candidate.plan_tier = PlanTier.explorer
    candidate.subscription_status = "active"
    candidate.stripe_subscription_id = "sub_test_123"
    await db_session.commit()

    with patch("app.services.billing_service.stripe") as mock_stripe:
        mock_stripe.Subscription.retrieve.return_value = SimpleNamespace(current_period_end=1800000000, status="active")
        resp = await client.get(f"{API}/billing/subscription", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "explorer"
    assert data["status"] == "active"
    assert data["stripe_subscription_id"] == "sub_test_123"


# ---------------------------------------------------------------------------
# POST /billing/webhooks/stripe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stripe_webhook_invalid_signature_returns_400(client: AsyncClient):
    """Webhook with invalid signature returns 400."""
    with patch("app.services.billing_service.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.side_effect = stripe.SignatureVerificationError("Bad sig", "sig_header")
        resp = await client.post(
            f"{API}/billing/webhooks/stripe",
            content=b'{"type": "customer.subscription.created"}',
            headers={"stripe-signature": "invalid_sig"},
        )
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stripe_webhook_processing_error_returns_400(client: AsyncClient):
    """Webhook that raises generic exception during processing returns 400."""
    with patch(
        "app.services.billing_service.handle_webhook_event",
        new_callable=AsyncMock,
        side_effect=RuntimeError("DB error during webhook"),
    ):
        resp = await client.post(
            f"{API}/billing/webhooks/stripe",
            content=b'{"type": "invoice.paid"}',
            headers={"stripe-signature": "t=123,v1=abc"},
        )
    assert resp.status_code == 400
    assert "failed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stripe_webhook_success(client: AsyncClient):
    """Valid webhook event returns {status: ok}."""
    with patch(
        "app.services.billing_service.handle_webhook_event",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await client.post(
            f"{API}/billing/webhooks/stripe",
            content=b'{"type": "invoice.paid"}',
            headers={"stripe-signature": "t=123,v1=abc"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_stripe_webhook_no_signature_header(client: AsyncClient):
    """Webhook without stripe-signature header still processes (empty string)."""
    with patch(
        "app.services.billing_service.handle_webhook_event",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await client.post(
            f"{API}/billing/webhooks/stripe",
            content=b'{"type": "test.event"}',
        )
    assert resp.status_code == 200
