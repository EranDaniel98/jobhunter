import uuid

import pytest
import pytest_asyncio

from app.config import settings
from app.graphs.apply_pipeline import build_apply_pipeline
from app.infrastructure.url_scraper import scrape_job_url


class TestApplyGraph:
    def test_graph_builds_and_compiles(self):
        builder = build_apply_pipeline()
        graph = builder.compile()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        builder = build_apply_pipeline()
        graph = builder.compile()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {"parse_job", "match_skills", "generate_tips", "generate_cover_letter", "save_and_notify", "mark_failed"}
        assert expected.issubset(node_names)


class TestApplyAPI:
    @pytest.mark.asyncio
    async def test_analyze_endpoint(self, client, auth_headers, db_session):
        resp = await client.post(
            f"{settings.API_V1_PREFIX}/apply/analyze",
            json={
                "title": "Senior Python Engineer",
                "company_name": "TestCo",
                "raw_text": "We are looking for a Senior Python Engineer with 3+ years experience in FastAPI and PostgreSQL.",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Senior Python Engineer"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_postings_empty(self, client, auth_headers):
        resp = await client.get(
            f"{settings.API_V1_PREFIX}/apply/postings",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["postings"] == []

    @pytest.mark.asyncio
    async def test_analysis_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"{settings.API_V1_PREFIX}/apply/postings/{fake_id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_analyze_creates_posting(self, client, auth_headers, db_session):
        resp = await client.post(
            f"{settings.API_V1_PREFIX}/apply/analyze",
            json={
                "title": "Backend Developer",
                "raw_text": "Looking for a backend developer.",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Verify it appears in the list
        list_resp = await client.get(
            f"{settings.API_V1_PREFIX}/apply/postings",
            headers=auth_headers,
        )
        data = list_resp.json()
        assert data["total"] >= 1
        titles = [p["title"] for p in data["postings"]]
        assert "Backend Developer" in titles


class TestScrapeUrlAPI:
    @pytest.mark.asyncio
    async def test_scrape_url_success(self, client, auth_headers, monkeypatch):
        fake_text = "# Senior Engineer at Acme\n\nWe need a Python developer..."

        async def mock_scrape(url):
            return fake_text

        monkeypatch.setattr("app.api.apply.scrape_job_url", mock_scrape)

        resp = await client.post(
            f"{settings.API_V1_PREFIX}/apply/scrape-url",
            json={"url": "https://example.com/job/123"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Senior Engineer" in data["raw_text"]

    @pytest.mark.asyncio
    async def test_scrape_url_failure_returns_422(self, client, auth_headers, monkeypatch):
        async def mock_scrape(url):
            raise RuntimeError("Connection refused")

        monkeypatch.setattr("app.api.apply.scrape_job_url", mock_scrape)

        resp = await client.post(
            f"{settings.API_V1_PREFIX}/apply/scrape-url",
            json={"url": "https://blocked.com/job"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "paste" in resp.json()["detail"].lower()
