"""Additional unit tests for billing_service - covers _tier_for_price,
_price_id_for_tier, create_checkout_session error paths,
_handle_checkout_completed, and get_subscription with active sub."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.plans import PlanTier
from app.services import billing_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidate(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "email": "user@example.com",
        "full_name": "Test User",
        "stripe_customer_id": "cus_abc",
        "stripe_subscription_id": None,
        "plan_tier": "free",
        "subscription_status": None,
    }
    defaults.update(overrides)
    c = MagicMock()
    for k, v in defaults.items():
        setattr(c, k, v)
    return c


class _DictNS(SimpleNamespace):
    def __getitem__(self, key):
        return getattr(self, key)


def _fake_sub(price_id="price_explorer", status="active", sub_id="sub_xyz"):
    return _DictNS(
        id=sub_id,
        customer="cus_abc",
        status=status,
        current_period_end=1800000000,
        items={"data": [{"price": {"id": price_id}}]},
    )


# ---------------------------------------------------------------------------
# _tier_for_price / _price_id_for_tier
# ---------------------------------------------------------------------------


class TestTierMappings:
    def test_tier_for_price_hunter(self):
        with patch("app.services.billing_service.settings") as s:
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            assert billing_service._tier_for_price("price_hunt") == PlanTier.hunter

    def test_tier_for_price_explorer(self):
        with patch("app.services.billing_service.settings") as s:
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            assert billing_service._tier_for_price("price_exp") == PlanTier.explorer

    def test_tier_for_price_unknown_returns_free(self):
        with patch("app.services.billing_service.settings") as s:
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            assert billing_service._tier_for_price("price_other") == PlanTier.free

    def test_price_id_for_tier_explorer(self):
        with patch("app.services.billing_service.settings") as s:
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            assert billing_service._price_id_for_tier(PlanTier.explorer) == "price_exp"

    def test_price_id_for_tier_hunter(self):
        with patch("app.services.billing_service.settings") as s:
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            assert billing_service._price_id_for_tier(PlanTier.hunter) == "price_hunt"

    def test_price_id_for_tier_free_returns_none(self):
        with patch("app.services.billing_service.settings") as s:
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            assert billing_service._price_id_for_tier(PlanTier.free) is None


# ---------------------------------------------------------------------------
# create_checkout_session — Stripe error paths
# ---------------------------------------------------------------------------


class TestCreateCheckoutSessionErrors:
    @pytest.mark.asyncio
    async def test_stripe_customer_create_error_raises_http502(self):
        """StripeError during customer creation raises HTTPException 502."""
        from fastapi import HTTPException

        candidate = _make_candidate(stripe_customer_id=None)
        db = AsyncMock()

        with (
            patch("app.services.billing_service.stripe") as mock_stripe,
            patch("app.services.billing_service.settings") as s,
        ):
            s.STRIPE_SECRET_KEY = "sk_test"
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            s.FRONTEND_URL = "http://localhost:3000"
            mock_stripe.StripeError = Exception
            mock_stripe.Customer.create.side_effect = Exception("Stripe down")

            with pytest.raises(HTTPException) as exc_info:
                await billing_service.create_checkout_session(candidate, "explorer", db)

        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_stripe_checkout_session_create_error_raises_http502(self):
        """StripeError during session creation raises HTTPException 502."""
        from fastapi import HTTPException

        candidate = _make_candidate(stripe_customer_id="cus_existing")
        db = AsyncMock()

        with (
            patch("app.services.billing_service.stripe") as mock_stripe,
            patch("app.services.billing_service.settings") as s,
        ):
            s.STRIPE_SECRET_KEY = "sk_test"
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            s.FRONTEND_URL = "http://localhost:3000"
            mock_stripe.StripeError = Exception
            mock_stripe.checkout.Session.create.side_effect = Exception("Network error")

            with pytest.raises(HTTPException) as exc_info:
                await billing_service.create_checkout_session(candidate, "explorer", db)

        assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# _handle_checkout_completed (lines 152-177)
# ---------------------------------------------------------------------------


class TestHandleCheckoutCompleted:
    @pytest.mark.asyncio
    async def test_checkout_completed_subscription_mode(self):
        """checkout.session.completed in subscription mode updates DB."""
        db = AsyncMock()

        session = _DictNS(
            mode="subscription",
            customer="cus_abc",
            subscription="sub_new123",
        )
        event = SimpleNamespace(
            type="checkout.session.completed",
            data=SimpleNamespace(object=session),
        )

        sub = _fake_sub(price_id="price_exp", status="active", sub_id="sub_new123")

        with (
            patch("app.services.billing_service.stripe") as mock_stripe,
            patch("app.services.billing_service.settings") as s,
        ):
            s.STRIPE_SECRET_KEY = "sk_test"
            s.STRIPE_WEBHOOK_SECRET = "whsec_test"
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            mock_stripe.Webhook.construct_event.return_value = event
            mock_stripe.Subscription.retrieve.return_value = sub

            await billing_service.handle_webhook_event(b"payload", "sig", db)

        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_checkout_completed_non_subscription_mode_ignored(self):
        """checkout.session.completed in payment mode (not subscription) is a no-op."""
        db = AsyncMock()

        session = _DictNS(
            mode="payment",
            customer="cus_abc",
            subscription=None,
        )
        event = SimpleNamespace(
            type="checkout.session.completed",
            data=SimpleNamespace(object=session),
        )

        with (
            patch("app.services.billing_service.stripe") as mock_stripe,
            patch("app.services.billing_service.settings") as s,
        ):
            s.STRIPE_SECRET_KEY = "sk_test"
            s.STRIPE_WEBHOOK_SECRET = "whsec_test"
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            mock_stripe.Webhook.construct_event.return_value = event

            await billing_service.handle_webhook_event(b"payload", "sig", db)

        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_checkout_completed_no_subscription_id(self):
        """checkout.session.completed with no subscription_id skips DB update."""
        db = AsyncMock()

        session = _DictNS(
            mode="subscription",
            customer="cus_abc",
            subscription=None,  # no sub id
        )
        event = SimpleNamespace(
            type="checkout.session.completed",
            data=SimpleNamespace(object=session),
        )

        with (
            patch("app.services.billing_service.stripe") as mock_stripe,
            patch("app.services.billing_service.settings") as s,
        ):
            s.STRIPE_SECRET_KEY = "sk_test"
            s.STRIPE_WEBHOOK_SECRET = "whsec_test"
            s.STRIPE_PRICE_EXPLORER = "price_exp"
            s.STRIPE_PRICE_HUNTER = "price_hunt"
            mock_stripe.Webhook.construct_event.return_value = event

            await billing_service.handle_webhook_event(b"payload", "sig", db)

        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_subscription — active subscription path
# ---------------------------------------------------------------------------


class TestGetSubscriptionActive:
    @pytest.mark.asyncio
    async def test_active_subscription_fetches_period_end(self):
        """Active subscription retrieves period end from Stripe."""
        candidate = _make_candidate(
            plan_tier="hunter",
            subscription_status="active",
            stripe_subscription_id="sub_hunt",
        )

        with (
            patch("app.services.billing_service.stripe") as mock_stripe,
            patch("app.services.billing_service.settings") as s,
        ):
            s.STRIPE_SECRET_KEY = "sk_test"
            mock_stripe.Subscription.retrieve.return_value = SimpleNamespace(current_period_end=1800000000)

            result = await billing_service.get_subscription(candidate)

        assert result["tier"] == "hunter"
        assert result["status"] == "active"
        assert result["current_period_end"] is not None
        mock_stripe.Subscription.retrieve.assert_called_once_with("sub_hunt")

    @pytest.mark.asyncio
    async def test_stripe_fetch_error_returns_none_period_end(self):
        """When Stripe.Subscription.retrieve fails, period_end is None (graceful)."""
        candidate = _make_candidate(
            plan_tier="explorer",
            subscription_status="active",
            stripe_subscription_id="sub_exp",
        )

        with (
            patch("app.services.billing_service.stripe") as mock_stripe,
            patch("app.services.billing_service.settings") as s,
        ):
            s.STRIPE_SECRET_KEY = "sk_test"
            mock_stripe.Subscription.retrieve.side_effect = Exception("Stripe timeout")

            result = await billing_service.get_subscription(candidate)

        assert result["tier"] == "explorer"
        assert result["current_period_end"] is None
