"""Stripe billing service — checkout sessions, portal, webhook handling."""

from datetime import datetime, timezone

import stripe
import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate
from app.plans import PLANS, PlanTier

logger = structlog.get_logger()


def _get_stripe() -> None:
    """Set stripe API key lazily (avoids issues when key is empty during tests)."""
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _tier_for_price(price_id: str) -> PlanTier:
    """Map a Stripe price ID to a PlanTier."""
    if price_id == settings.STRIPE_PRICE_EXPLORER:
        return PlanTier.explorer
    if price_id == settings.STRIPE_PRICE_HUNTER:
        return PlanTier.hunter
    return PlanTier.free


def _price_id_for_tier(tier: PlanTier) -> str | None:
    """Map a PlanTier to the configured Stripe price ID."""
    if tier == PlanTier.explorer:
        return settings.STRIPE_PRICE_EXPLORER
    if tier == PlanTier.hunter:
        return settings.STRIPE_PRICE_HUNTER
    return None


async def create_checkout_session(
    candidate: Candidate,
    tier: str,
    db: AsyncSession,
) -> str:
    """Create a Stripe Checkout session and return the URL."""
    _get_stripe()

    plan_tier = PlanTier(tier)
    price_id = _price_id_for_tier(plan_tier)
    if not price_id:
        raise ValueError(f"No Stripe price configured for tier: {tier}")

    # Create or reuse Stripe customer
    if not candidate.stripe_customer_id:
        customer = stripe.Customer.create(
            email=candidate.email,
            name=candidate.full_name,
            metadata={"candidate_id": str(candidate.id)},
        )
        candidate.stripe_customer_id = customer.id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=candidate.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.FRONTEND_URL}/plans?success=true",
        cancel_url=f"{settings.FRONTEND_URL}/plans?canceled=true",
        metadata={"candidate_id": str(candidate.id), "tier": tier},
    )
    return session.url


async def create_portal_session(candidate: Candidate) -> str:
    """Create a Stripe Customer Portal session and return the URL."""
    _get_stripe()

    if not candidate.stripe_customer_id:
        raise ValueError("No billing account found — subscribe to a plan first")

    session = stripe.billing_portal.Session.create(
        customer=candidate.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/plans",
    )
    return session.url


async def handle_webhook_event(payload: bytes, sig_header: str, db: AsyncSession) -> None:
    """Process Stripe webhook events and update candidate billing state."""
    _get_stripe()

    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )

    handler = _WEBHOOK_HANDLERS.get(event.type)
    if handler:
        await handler(event, db)
    else:
        logger.debug("stripe_event_ignored", event_type=event.type)


async def _handle_subscription_upsert(event: stripe.Event, db: AsyncSession) -> None:
    """Handle subscription created/updated events."""
    subscription = event.data.object
    customer_id = subscription.customer
    status = subscription.status  # active, past_due, canceled, etc.

    # Determine tier from the subscription's price
    price_id = subscription["items"]["data"][0]["price"]["id"]
    tier = _tier_for_price(price_id)

    await db.execute(
        update(Candidate)
        .where(Candidate.stripe_customer_id == customer_id)
        .values(
            plan_tier=tier.value,
            subscription_status=status,
            stripe_subscription_id=subscription.id,
        )
    )
    await db.commit()
    logger.info("subscription_updated", customer_id=customer_id, tier=tier.value, status=status)


async def _handle_subscription_deleted(event: stripe.Event, db: AsyncSession) -> None:
    """Handle subscription deleted (canceled at period end or immediate)."""
    subscription = event.data.object
    customer_id = subscription.customer

    await db.execute(
        update(Candidate)
        .where(Candidate.stripe_customer_id == customer_id)
        .values(
            plan_tier=PlanTier.free.value,
            subscription_status="canceled",
            stripe_subscription_id=None,
        )
    )
    await db.commit()
    logger.info("subscription_canceled", customer_id=customer_id)


async def _handle_checkout_completed(event: stripe.Event, db: AsyncSession) -> None:
    """Handle checkout.session.completed — link subscription if not already linked."""
    session = event.data.object
    if session.mode != "subscription":
        return

    customer_id = session.customer
    subscription_id = session.subscription

    if subscription_id:
        # Fetch the subscription to get the price/tier
        sub = stripe.Subscription.retrieve(subscription_id)
        price_id = sub["items"]["data"][0]["price"]["id"]
        tier = _tier_for_price(price_id)

        await db.execute(
            update(Candidate)
            .where(Candidate.stripe_customer_id == customer_id)
            .values(
                plan_tier=tier.value,
                subscription_status=sub.status,
                stripe_subscription_id=subscription_id,
            )
        )
        await db.commit()
        logger.info("checkout_completed", customer_id=customer_id, tier=tier.value)


_WEBHOOK_HANDLERS = {
    "customer.subscription.created": _handle_subscription_upsert,
    "customer.subscription.updated": _handle_subscription_upsert,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "checkout.session.completed": _handle_checkout_completed,
}


async def get_subscription(candidate: Candidate) -> dict:
    """Get current subscription details for a candidate."""
    result = {
        "tier": candidate.plan_tier,
        "status": candidate.subscription_status,
        "current_period_end": None,
        "stripe_subscription_id": candidate.stripe_subscription_id,
    }

    if candidate.stripe_subscription_id and candidate.subscription_status == "active":
        try:
            _get_stripe()
            sub = stripe.Subscription.retrieve(candidate.stripe_subscription_id)
            result["current_period_end"] = datetime.fromtimestamp(
                sub.current_period_end, tz=timezone.utc
            ).isoformat()
        except Exception as e:
            logger.warning("stripe_subscription_fetch_failed", error=str(e))

    return result
