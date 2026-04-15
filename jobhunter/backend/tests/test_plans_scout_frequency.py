"""Verify scout_frequency_days per plan tier."""
from app.plans import PlanTier, get_limits_for_tier


def test_free_tier_scout_frequency_is_weekly():
    assert get_limits_for_tier(PlanTier.free)["scout_frequency_days"] == 7


def test_explorer_tier_scout_frequency_is_daily():
    assert get_limits_for_tier(PlanTier.explorer)["scout_frequency_days"] == 1


def test_hunter_tier_scout_frequency_is_daily():
    assert get_limits_for_tier(PlanTier.hunter)["scout_frequency_days"] == 1
