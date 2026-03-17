import uuid

import pytest

from app.config import settings
from app.graphs.interview_prep import build_interview_prep_pipeline


class TestInterviewPrepGraph:
    def test_graph_builds_and_compiles(self):
        builder = build_interview_prep_pipeline()
        graph = builder.compile()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        builder = build_interview_prep_pipeline()
        graph = builder.compile()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {"load_context", "generate_prep", "save_and_notify", "mark_failed"}
        assert expected.issubset(node_names)


class TestInterviewPrepAPI:
    @pytest.mark.asyncio
    async def test_generate_prep_endpoint(self, client, auth_headers, db_session):
        from tests.conftest import seed_candidate_dna
        await seed_candidate_dna(db_session, client, auth_headers)

        me = await client.get(f"{settings.API_V1_PREFIX}/auth/me", headers=auth_headers)
        candidate_id = me.json()["id"]

        from app.models.company import Company
        company = Company(
            id=uuid.uuid4(), candidate_id=uuid.UUID(candidate_id),
            name="TestCo", domain="testco-interview.com", status="approved", research_status="completed",
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.post(
            f"{settings.API_V1_PREFIX}/interview-prep/generate",
            json={"company_id": str(company.id), "prep_type": "company_qa"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prep_type"] == "company_qa"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, client, auth_headers):
        resp = await client.get(
            f"{settings.API_V1_PREFIX}/interview-prep/sessions",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["sessions"] == []

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"{settings.API_V1_PREFIX}/interview-prep/sessions/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_prep_type(self, client, auth_headers):
        resp = await client.post(
            f"{settings.API_V1_PREFIX}/interview-prep/generate",
            json={"company_id": str(uuid.uuid4()), "prep_type": "invalid_type"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_mock_start_endpoint(self, client, auth_headers, db_session):
        from tests.conftest import seed_candidate_dna
        await seed_candidate_dna(db_session, client, auth_headers)

        me = await client.get(f"{settings.API_V1_PREFIX}/auth/me", headers=auth_headers)
        candidate_id = me.json()["id"]

        from app.models.company import Company
        company = Company(
            id=uuid.uuid4(), candidate_id=uuid.UUID(candidate_id),
            name="MockCo", domain="mockco-interview.com", status="approved", research_status="completed",
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.post(
            f"{settings.API_V1_PREFIX}/interview-prep/mock/start",
            json={"company_id": str(company.id), "interview_type": "behavioral"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prep_type"] == "mock_interview"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "interviewer"

    @pytest.mark.asyncio
    async def test_mock_invalid_interview_type(self, client, auth_headers):
        resp = await client.post(
            f"{settings.API_V1_PREFIX}/interview-prep/mock/start",
            json={"company_id": str(uuid.uuid4()), "interview_type": "invalid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
