import structlog
from fastapi import APIRouter, Depends

from app.dependencies import get_current_candidate
from app.models.candidate import Candidate
from app.plans import PLANS, PlanTier
from app.schemas.billing import CheckoutRequest, CheckoutResponse, PlanResponse

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
        result.append(PlanResponse(
            tier=plan.tier.value,
            display_name=plan.display_name,
            price_monthly_cents=plan.price_monthly_cents,
            description=plan.description,
            limits=user_limits,
        ))
    return result


@router.post("/billing/create-checkout-session", response_model=CheckoutResponse)
async def create_checkout_session(
    data: CheckoutRequest,
    candidate: Candidate = Depends(get_current_candidate),
):
    """Stub for Stripe checkout session creation."""
    # Validate tier
    try:
        PlanTier(data.tier)
    except ValueError:
        return CheckoutResponse(status="error", message=f"Invalid tier: {data.tier}")

    return CheckoutResponse(
        status="coming_soon",
        message="Paid plans are coming soon! Stay tuned.",
    )


@router.get("/billing/portal", response_model=CheckoutResponse)
async def billing_portal(
    candidate: Candidate = Depends(get_current_candidate),
):
    """Stub for Stripe customer portal."""
    return CheckoutResponse(
        status="coming_soon",
        message="Billing portal is coming soon!",
    )
