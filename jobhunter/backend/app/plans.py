"""Plan tier definitions for the Free / Explorer / Hunter system."""

from dataclasses import dataclass
from enum import StrEnum


class PlanTier(StrEnum):
    free = "free"
    explorer = "explorer"
    hunter = "hunter"


@dataclass(frozen=True)
class PlanDefinition:
    tier: PlanTier
    display_name: str
    price_monthly_cents: int
    description: str
    limits: dict[str, int]
    stripe_price_id: str | None = None


PLANS: dict[PlanTier, PlanDefinition] = {
    PlanTier.free: PlanDefinition(
        tier=PlanTier.free,
        display_name="Free",
        price_monthly_cents=0,
        description="Get started with basic job search tools",
        limits={
            "discovery": 3,
            "research": 2,
            "hunter": 5,
            "email": 3,
            "openai": 30,
        },
    ),
    PlanTier.explorer: PlanDefinition(
        tier=PlanTier.explorer,
        display_name="Explorer",
        price_monthly_cents=1900,
        description="For active job seekers who want more reach",
        limits={
            "discovery": 15,
            "research": 10,
            "hunter": 30,
            "email": 20,
            "openai": 150,
        },
    ),
    PlanTier.hunter: PlanDefinition(
        tier=PlanTier.hunter,
        display_name="Hunter",
        price_monthly_cents=4900,
        description="Unlimited-feeling power for serious job hunters",
        limits={
            "discovery": 50,
            "research": 30,
            "hunter": 100,
            "email": 75,
            "openai": 500,
        },
    ),
}


def get_limits_for_tier(tier: PlanTier) -> dict[str, int]:
    """Return the quota limits dict for a given plan tier."""
    return PLANS[tier].limits
