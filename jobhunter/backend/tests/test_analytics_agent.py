import pytest
import uuid

from app.config import settings
from app.graphs.analytics_pipeline import build_analytics_pipeline


class TestAnalyticsGraph:
    def test_graph_builds(self):
        builder = build_analytics_pipeline()
        graph = builder.compile()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        builder = build_analytics_pipeline()
        graph = builder.compile()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {"gather_data", "generate_insights", "save_insights", "notify", "mark_failed"}
        assert expected.issubset(node_names)


class TestAnalyticsAPI:
    @pytest.mark.asyncio
    async def test_insights_endpoint_empty(self, client, auth_headers):
        resp = await client.get(
            f"{settings.API_V1_PREFIX}/analytics/insights",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["insights"] == []

    @pytest.mark.asyncio
    async def test_refresh_endpoint(self, client, auth_headers):
        resp = await client.post(
            f"{settings.API_V1_PREFIX}/analytics/insights/refresh",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "refreshing"

    @pytest.mark.asyncio
    async def test_dashboard_endpoint(self, client, auth_headers):
        resp = await client.get(
            f"{settings.API_V1_PREFIX}/analytics/dashboard",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "funnel" in data
        assert "outreach" in data
        assert "pipeline" in data
        assert "insights" in data

    @pytest.mark.asyncio
    async def test_mark_read_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.patch(
            f"{settings.API_V1_PREFIX}/analytics/insights/{fake_id}/read",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_read(self, client, auth_headers, db_session):
        """Create an insight directly, then mark it as read."""
        from app.models.insight import AnalyticsInsight

        # Get candidate ID
        me = await client.get(f"{settings.API_V1_PREFIX}/auth/me", headers=auth_headers)
        candidate_id = uuid.UUID(me.json()["id"])

        insight = AnalyticsInsight(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            insight_type="recommendation",
            title="Test Insight",
            body="This is a test insight.",
            severity="info",
        )
        db_session.add(insight)
        await db_session.commit()

        resp = await client.patch(
            f"{settings.API_V1_PREFIX}/analytics/insights/{insight.id}/read",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
