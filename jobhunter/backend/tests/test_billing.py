"""Tests for billing service and API routes."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.plans import PlanTier
from app.services import billing_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(**overrides) -> Candidate:
    defaults = {
        "id": uuid.uuid4(),
        "email": "billing@example.com",
        "full_name": "Billing User",
        "stripe_customer_id": "cus_test123",
        "stripe_subscription_id": None,
        "plan_tier": "free",
        "subscription_status": None,
    }
    defaults.update(overrides)
    c = MagicMock(spec=Candidate)
    for k, v in defaults.items():
        setattr(c, k, v)
    return c


class _DictNamespace(SimpleNamespace):
    """SimpleNamespace that also supports dict-style access like Stripe objects."""

    def __getitem__(self, key):
        return getattr(self, key)


def _fake_subscription(price_id="price_explorer", status="active", sub_id="sub_123"):
    """Return a dict-like object that supports both attribute and subscript access."""
    return _DictNamespace(
        id=sub_id,
        customer="cus_test123",
        status=status,
        current_period_end=1740000000,
        items={"data": [{"price": {"id": price_id}}]},
    )


# ---------------------------------------------------------------------------
# billing_service.create_checkout_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_checkout_session_new_customer():
    """Checkout creates Stripe customer when candidate has none, then creates session."""
    candidate = _make_candidate(stripe_customer_id=None)
    db = AsyncMock(spec=AsyncSession)

    with (
        patch("app.services.billing_service.stripe") as mock_stripe,
        patch("app.services.billing_service.settings") as mock_settings,
    ):
        mock_settings.STRIPE_SECRET_KEY = "sk_test"
        mock_settings.STRIPE_PRICE_EXPLORER = "price_explorer"
        mock_settings.STRIPE_PRICE_HUNTER = "price_hunter"
        mock_settings.FRONTEND_URL = "http://localhost:3000"

        mock_stripe.Customer.create.return_value = SimpleNamespace(id="cus_new")
        mock_stripe.checkout.Session.create.return_value = SimpleNamespace(url="https://checkout.stripe.com/session")

        url = await billing_service.create_checkout_session(candidate, "explorer", db)

        assert url == "https://checkout.stripe.com/session"
        mock_stripe.Customer.create.assert_called_once()
        assert candidate.stripe_customer_id == "cus_new"
        db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_checkout_session_existing_customer():
    """Checkout reuses existing Stripe customer ID."""
    candidate = _make_candidate(stripe_customer_id="cus_existing")
    db = AsyncMock(spec=AsyncSession)

    with (
        patch("app.services.billing_service.stripe") as mock_stripe,
        patch("app.services.billing_service.settings") as mock_settings,
    ):
        mock_settings.STRIPE_SECRET_KEY = "sk_test"
        mock_settings.STRIPE_PRICE_EXPLORER = "price_explorer"
        mock_settings.STRIPE_PRICE_HUNTER = "price_hunter"
        mock_settings.FRONTEND_URL = "http://localhost:3000"

        mock_stripe.checkout.Session.create.return_value = SimpleNamespace(url="https://checkout.stripe.com/s2")

        url = await billing_service.create_checkout_session(candidate, "explorer", db)

        assert url == "https://checkout.stripe.com/s2"
        mock_stripe.Customer.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_checkout_session_free_tier_raises():
    """Checkout for free tier raises ValueError (no price configured)."""
    candidate = _make_candidate()
    db = AsyncMock(spec=AsyncSession)

    with (
        patch("app.services.billing_service.stripe"),
        patch("app.services.billing_service.settings") as mock_settings,
    ):
        mock_settings.STRIPE_SECRET_KEY = "sk_test"
        mock_settings.STRIPE_PRICE_EXPLORER = "price_explorer"
        mock_settings.STRIPE_PRICE_HUNTER = "price_hunter"

        with pytest.raises(ValueError, match="No Stripe price configured"):
            await billing_service.create_checkout_session(candidate, "free", db)


# ---------------------------------------------------------------------------
# billing_service.create_portal_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_portal_session_success():
    """Portal session created for candidate with Stripe customer."""
    candidate = _make_candidate(stripe_customer_id="cus_portal")

    with (
        patch("app.services.billing_service.stripe") as mock_stripe,
        patch("app.services.billing_service.settings") as mock_settings,
    ):
        mock_settings.STRIPE_SECRET_KEY = "sk_test"
        mock_settings.FRONTEND_URL = "http://localhost:3000"

        mock_stripe.billing_portal.Session.create.return_value = SimpleNamespace(url="https://portal.stripe.com/s1")

        url = await billing_service.create_portal_session(candidate)

        assert url == "https://portal.stripe.com/s1"
        mock_stripe.billing_portal.Session.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_portal_session_no_customer_raises():
    """Portal raises ValueError when candidate has no Stripe customer."""
    candidate = _make_candidate(stripe_customer_id=None)

    with pytest.raises(ValueError, match="No billing account found"):
        await billing_service.create_portal_session(candidate)


# ---------------------------------------------------------------------------
# billing_service.handle_webhook_event — subscription lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_subscription_created():
    """Webhook subscription.created updates candidate plan tier and status."""
    db = AsyncMock(spec=AsyncSession)
    fake_sub = _fake_subscription(price_id="price_explorer", status="active")

    fake_event = SimpleNamespace(
        type="customer.subscription.created",
        data=SimpleNamespace(object=fake_sub),
    )

    with (
        patch("app.services.billing_service.stripe") as mock_stripe,
        patch("app.services.billing_service.settings") as mock_settings,
    ):
        mock_settings.STRIPE_SECRET_KEY = "sk_test"
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_settings.STRIPE_PRICE_EXPLORER = "price_explorer"
        mock_settings.STRIPE_PRICE_HUNTER = "price_hunter"

        mock_stripe.Webhook.construct_event.return_value = fake_event

        await billing_service.handle_webhook_event(b"payload", "sig_header", db)

        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_subscription_deleted():
    """Webhook subscription.deleted resets candidate to free tier."""
    db = AsyncMock(spec=AsyncSession)
    fake_sub = SimpleNamespace(customer="cus_test123", id="sub_del")

    fake_event = SimpleNamespace(
        type="customer.subscription.deleted",
        data=SimpleNamespace(object=fake_sub),
    )

    with (
        patch("app.services.billing_service.stripe") as mock_stripe,
        patch("app.services.billing_service.settings") as mock_settings,
    ):
        mock_settings.STRIPE_SECRET_KEY = "sk_test"
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

        mock_stripe.Webhook.construct_event.return_value = fake_event

        await billing_service.handle_webhook_event(b"payload", "sig_header", db)

        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_unknown_event_ignored():
    """Unknown webhook event type is silently ignored."""
    db = AsyncMock(spec=AsyncSession)

    fake_event = SimpleNamespace(type="invoice.payment_succeeded")

    with (
        patch("app.services.billing_service.stripe") as mock_stripe,
        patch("app.services.billing_service.settings") as mock_settings,
    ):
        mock_settings.STRIPE_SECRET_KEY = "sk_test"
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

        mock_stripe.Webhook.construct_event.return_value = fake_event

        # Should not raise
        await billing_service.handle_webhook_event(b"payload", "sig_header", db)

        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# billing_service.get_subscription
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_subscription_active():
    """get_subscription returns tier, status, and period end for active sub."""
    candidate = _make_candidate(
        plan_tier="explorer",
        subscription_status="active",
        stripe_subscription_id="sub_active",
    )

    with (
        patch("app.services.billing_service.stripe") as mock_stripe,
        patch("app.services.billing_service.settings") as mock_settings,
    ):
        mock_settings.STRIPE_SECRET_KEY = "sk_test"
        mock_stripe.Subscription.retrieve.return_value = SimpleNamespace(
            current_period_end=1740000000, status="active"
        )

        result = await billing_service.get_subscription(candidate)

        assert result["tier"] == "explorer"
        assert result["status"] == "active"
        assert result["current_period_end"] is not None
        assert result["stripe_subscription_id"] == "sub_active"


@pytest.mark.asyncio
async def test_get_subscription_free_no_stripe_call():
    """get_subscription for free user doesn't call Stripe."""
    candidate = _make_candidate(
        plan_tier="free",
        subscription_status=None,
        stripe_subscription_id=None,
    )

    with patch("app.services.billing_service.stripe") as mock_stripe:
        result = await billing_service.get_subscription(candidate)

        assert result["tier"] == "free"
        assert result["current_period_end"] is None
        mock_stripe.Subscription.retrieve.assert_not_called()


# ---------------------------------------------------------------------------
# Plan tier mapping helpers
# ---------------------------------------------------------------------------

def test_tier_for_price_explorer():
    with patch("app.services.billing_service.settings") as mock_settings:
        mock_settings.STRIPE_PRICE_EXPLORER = "price_explorer"
        mock_settings.STRIPE_PRICE_HUNTER = "price_hunter"
        assert billing_service._tier_for_price("price_explorer") == PlanTier.explorer


def test_tier_for_price_unknown_defaults_to_free():
    with patch("app.services.billing_service.settings") as mock_settings:
        mock_settings.STRIPE_PRICE_EXPLORER = "price_explorer"
        mock_settings.STRIPE_PRICE_HUNTER = "price_hunter"
        assert billing_service._tier_for_price("price_unknown") == PlanTier.free
