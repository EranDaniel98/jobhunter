import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.plans import PLANS, PlanTier
from app.rate_limit import limiter
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    PlanResponse,
    PortalResponse,
    SubscriptionResponse,
)
from app.services import billing_service

router = APIRouter(tags=["plans"])
logger = structlog.get_logger()

# Labels shown to users (openai is hidden)
QUOTA_USER_LABELS = {
    "discovery": "Company Discoveries",
    "research": "Company Research",
    "hunter": "Contact Lookups",
    "email": "Emails Sent",
}


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans():
    """Return all available plans (public, no auth required)."""
    result = []
    for plan in PLANS.values():
        # Exclude openai from user-visible limits
        user_limits = {k: v for k, v in plan.limits.items() if k != "openai"}
        result.append(
            PlanResponse(
                tier=plan.tier.value,
                display_name=plan.display_name,
                price_monthly_cents=plan.price_monthly_cents,
                description=plan.description,
                limits=user_limits,
            )
        )
    return result


@router.post("/billing/create-checkout-session", response_model=CheckoutResponse)
@limiter.limit("5/minute")
async def create_checkout_session(
    request: Request,
    data: CheckoutRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for the requested plan tier."""
    try:
        PlanTier(data.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {data.tier}") from None

    if data.tier == PlanTier.free:
        raise HTTPException(status_code=400, detail="Cannot checkout for the free tier")

    try:
        url = await billing_service.create_checkout_session(candidate, data.tier, db)
        return CheckoutResponse(status="ok", url=url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("checkout_session_failed", error=str(e), candidate_id=str(candidate.id))
        raise HTTPException(status_code=500, detail="Failed to create checkout session") from e


@router.get("/billing/portal", response_model=PortalResponse)
@limiter.limit("10/minute")
async def billing_portal(
    request: Request,
    candidate: Candidate = Depends(get_current_candidate),
):
    """Create a Stripe Customer Portal session for managing subscription."""
    try:
        url = await billing_service.create_portal_session(candidate)
        return PortalResponse(url=url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("portal_session_failed", error=str(e), candidate_id=str(candidate.id))
        raise HTTPException(status_code=500, detail="Failed to create portal session") from e


@router.get("/billing/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    candidate: Candidate = Depends(get_current_candidate),
):
    """Get the current candidate's subscription details."""
    result = await billing_service.get_subscription(candidate)
    return SubscriptionResponse(**result)


@router.post("/billing/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events (no auth — verified by signature)."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        await billing_service.handle_webhook_event(payload, sig_header, db)
        return {"status": "ok"}
    except stripe.SignatureVerificationError:
        logger.warning("stripe_webhook_invalid_signature")
        raise HTTPException(status_code=400, detail="Invalid signature") from None
    except Exception as e:
        logger.error("stripe_webhook_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Webhook processing failed") from e
