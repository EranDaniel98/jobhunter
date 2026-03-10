from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    tier: str


class CheckoutResponse(BaseModel):
    status: str
    url: str | None = None
    message: str | None = None


class PlanResponse(BaseModel):
    tier: str
    display_name: str
    price_monthly_cents: int
    description: str
    limits: dict[str, int]


class UpdatePlanRequest(BaseModel):
    plan_tier: str


class PortalResponse(BaseModel):
    url: str


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    current_period_end: str | None = None
    stripe_subscription_id: str | None = None
