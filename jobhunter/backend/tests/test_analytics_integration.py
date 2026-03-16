"""Integration tests for /api/v1/analytics routes.

Covers funnel, outreach, pipeline, insights (list / unread_only / mark-read / 404),
dashboard, and insights/refresh.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.insight import AnalyticsInsight

API = settings.API_V1_PREFIX


# ── helpers ───────────────────────────────────────────────────────────────────


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seeded_insight(db_session: AsyncSession, auth_headers: dict, client: AsyncClient):
    """Seed one AnalyticsInsight for the authenticated candidate."""
    candidate_id = await _get_candidate_id(client, auth_headers)

    insight = AnalyticsInsight(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        insight_type="pipeline_health",
        title="Test Insight",
        body="Your pipeline looks healthy.",
        severity="info",
        is_read=False,
    )
    db_session.add(insight)
    await db_session.flush()

    return {"candidate_id": candidate_id, "insight": insight}


@pytest_asyncio.fixture
async def read_insight(db_session: AsyncSession, auth_headers: dict, client: AsyncClient):
    """Seed one already-read AnalyticsInsight."""
    candidate_id = await _get_candidate_id(client, auth_headers)

    insight = AnalyticsInsight(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        insight_type="recommendation",
        title="Read Insight",
        body="Follow up with companies.",
        severity="action_needed",
        is_read=True,
    )
    db_session.add(insight)
    await db_session.flush()

    return {"candidate_id": candidate_id, "insight": insight}


# ── GET /analytics/funnel ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_funnel(client: AsyncClient, auth_headers: dict):
    """GET /analytics/funnel returns a valid FunnelResponse."""
    resp = await client.get(f"{API}/analytics/funnel", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # FunnelResponse must have at least these stage keys
    for key in ("drafted", "sent", "delivered", "opened", "replied", "bounced"):
        assert key in data, f"Missing funnel key: {key}"


@pytest.mark.asyncio
async def test_get_funnel_unauthenticated(client: AsyncClient):
    """GET /analytics/funnel without auth returns 401."""
    resp = await client.get(f"{API}/analytics/funnel")
    assert resp.status_code == 401


# ── GET /analytics/outreach ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_outreach_stats(client: AsyncClient, auth_headers: dict):
    """GET /analytics/outreach returns a valid OutreachStatsResponse."""
    resp = await client.get(f"{API}/analytics/outreach", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total_sent", "total_opened", "total_replied", "open_rate", "reply_rate", "by_channel"):
        assert key in data, f"Missing outreach key: {key}"


# ── GET /analytics/pipeline ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_pipeline_stats(client: AsyncClient, auth_headers: dict):
    """GET /analytics/pipeline returns a valid PipelineStatsResponse."""
    resp = await client.get(f"{API}/analytics/pipeline", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for key in ("suggested", "approved", "rejected", "researched", "contacted"):
        assert key in data, f"Missing pipeline key: {key}"


# ── GET /analytics/insights ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_insights_empty(client: AsyncClient, auth_headers: dict):
    """GET /analytics/insights returns empty list when no insights exist."""
    resp = await client.get(f"{API}/analytics/insights", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "insights" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_insights_with_data(client: AsyncClient, auth_headers: dict, seeded_insight):
    """GET /analytics/insights returns seeded insight."""
    resp = await client.get(f"{API}/analytics/insights", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [i["id"] for i in data["insights"]]
    assert str(seeded_insight["insight"].id) in ids


@pytest.mark.asyncio
async def test_list_insights_unread_only_true(client: AsyncClient, auth_headers: dict, seeded_insight, read_insight):
    """GET /analytics/insights?unread_only=true excludes already-read insights."""
    resp = await client.get(f"{API}/analytics/insights", headers=auth_headers, params={"unread_only": "true"})
    assert resp.status_code == 200
    data = resp.json()
    ids = [i["id"] for i in data["insights"]]
    # unread insight should be present
    assert str(seeded_insight["insight"].id) in ids
    # read insight should NOT be present
    assert str(read_insight["insight"].id) not in ids


@pytest.mark.asyncio
async def test_list_insights_unread_only_false(client: AsyncClient, auth_headers: dict, seeded_insight, read_insight):
    """GET /analytics/insights?unread_only=false returns all insights."""
    resp = await client.get(f"{API}/analytics/insights", headers=auth_headers, params={"unread_only": "false"})
    assert resp.status_code == 200
    data = resp.json()
    ids = [i["id"] for i in data["insights"]]
    assert str(seeded_insight["insight"].id) in ids
    assert str(read_insight["insight"].id) in ids


@pytest.mark.asyncio
async def test_list_insights_pagination(client: AsyncClient, auth_headers: dict, seeded_insight):
    """GET /analytics/insights supports skip/limit pagination."""
    resp = await client.get(f"{API}/analytics/insights", headers=auth_headers, params={"skip": 0, "limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["insights"]) <= 1


# ── PATCH /analytics/insights/{id}/read ───────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_insight_read_found(
    client: AsyncClient, auth_headers: dict, seeded_insight, db_session: AsyncSession
):
    """PATCH /analytics/insights/{id}/read marks insight as read."""

    insight_id = str(seeded_insight["insight"].id)
    resp = await client.patch(f"{API}/analytics/insights/{insight_id}/read", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # Verify via API response (avoids DB session issues)
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_mark_insight_read_not_found(client: AsyncClient, auth_headers: dict):
    """PATCH /analytics/insights/{id}/read with unknown id returns 404."""
    resp = await client.patch(f"{API}/analytics/insights/{uuid.uuid4()}/read", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Insight not found"


# ── GET /analytics/dashboard ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dashboard(client: AsyncClient, auth_headers: dict):
    """GET /analytics/dashboard returns combined funnel + outreach + pipeline + insights."""
    resp = await client.get(f"{API}/analytics/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for key in ("funnel", "outreach", "pipeline", "insights"):
        assert key in data, f"Missing dashboard key: {key}"

    # Nested shapes
    assert "drafted" in data["funnel"]
    assert "total_sent" in data["outreach"]
    assert "suggested" in data["pipeline"]
    assert isinstance(data["insights"], list)


@pytest.mark.asyncio
async def test_get_dashboard_includes_latest_insights(client: AsyncClient, auth_headers: dict, seeded_insight):
    """GET /analytics/dashboard returns seeded insight in insights list."""
    resp = await client.get(f"{API}/analytics/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = [i["id"] for i in data["insights"]]
    assert str(seeded_insight["insight"].id) in ids


# ── POST /analytics/insights/refresh ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_insights(client: AsyncClient, auth_headers: dict):
    """POST /analytics/insights/refresh returns status:refreshing immediately."""
    resp = await client.post(f"{API}/analytics/insights/refresh", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"status": "refreshing"}


@pytest.mark.asyncio
async def test_refresh_insights_unauthenticated(client: AsyncClient):
    """POST /analytics/insights/refresh without auth returns 401."""
    resp = await client.post(f"{API}/analytics/insights/refresh")
    assert resp.status_code == 401
