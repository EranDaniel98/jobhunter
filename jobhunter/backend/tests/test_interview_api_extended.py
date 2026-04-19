"""Extended unit tests for the interview-prep API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import CandidateDNA
from app.models.company import Company
from app.models.enums import PrepType, SessionStatus
from app.models.interview import InterviewPrepSession

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_candidate_id(client: AsyncClient, headers: dict) -> uuid.UUID:
    me = await client.get(f"{API}/auth/me", headers=headers)
    return uuid.UUID(me.json()["id"])


async def _create_company(db: AsyncSession, candidate_id: uuid.UUID, name: str = "TestCo") -> Company:
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=name,
        domain=f"{name.lower().replace(' ', '')}-{uuid.uuid4().hex[:6]}.com",
        status="approved",
        research_status="completed",
    )
    db.add(company)
    await db.flush()
    return company


async def _create_dna(db: AsyncSession, candidate_id: uuid.UUID) -> CandidateDNA:
    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="Software engineer with 5 years Python experience.",
        strengths=["Python", "Backend"],
        gaps=[],
        career_stage="mid",
    )
    db.add(dna)
    await db.flush()
    return dna


async def _create_session(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
    prep_type: PrepType = PrepType.COMPANY_QA,
    status: SessionStatus = SessionStatus.COMPLETED,
) -> InterviewPrepSession:
    session = InterviewPrepSession(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        company_id=company_id,
        prep_type=prep_type,
        status=status,
        content={"prep_type": prep_type.value},
    )
    db.add(session)
    await db.flush()
    return session


# ---------------------------------------------------------------------------
# POST /interview-prep/generate
# ---------------------------------------------------------------------------


class TestInterviewPrepGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_pending(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        await _create_dna(db_session, candidate_id)
        company = await _create_company(db_session, candidate_id)

        resp = await client.post(
            f"{API}/interview-prep/generate",
            headers=auth_headers,
            json={"company_id": str(company.id), "prep_type": "company_qa"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prep_type"] == "company_qa"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_generate_invalid_prep_type(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        company = await _create_company(db_session, candidate_id)

        resp = await client.post(
            f"{API}/interview-prep/generate",
            headers=auth_headers,
            json={"company_id": str(company.id), "prep_type": "invalid_type"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_generate_company_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            f"{API}/interview-prep/generate",
            headers=auth_headers,
            json={"company_id": str(uuid.uuid4()), "prep_type": "company_qa"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_all_valid_prep_types(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        from app.models.enums import PrepType

        candidate_id = await _get_candidate_id(client, auth_headers)
        await _create_dna(db_session, candidate_id)
        company = await _create_company(db_session, candidate_id, name="TypeTestCo")

        valid_types = [t.value for t in PrepType if t != PrepType.MOCK_INTERVIEW]
        for prep_type in valid_types:
            resp = await client.post(
                f"{API}/interview-prep/generate",
                headers=auth_headers,
                json={"company_id": str(company.id), "prep_type": prep_type},
            )
            assert resp.status_code == 200, f"prep_type '{prep_type}' failed: {resp.text}"

    @pytest.mark.asyncio
    async def test_generate_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/interview-prep/generate",
            json={"company_id": str(uuid.uuid4()), "prep_type": "company_qa"},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /interview-prep/sessions
# ---------------------------------------------------------------------------


class TestInterviewPrepListSessions:
    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(f"{API}/interview-prep/sessions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_sessions_shows_created(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        company = await _create_company(db_session, candidate_id, "ListSessionsCo")
        await _create_session(db_session, candidate_id, company.id)

        resp = await client.get(f"{API}/interview-prep/sessions", headers=auth_headers)
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_company(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        candidate_id = await _get_candidate_id(client, auth_headers)
        company_a = await _create_company(db_session, candidate_id, "CompanyA")
        company_b = await _create_company(db_session, candidate_id, "CompanyB")
        await _create_session(db_session, candidate_id, company_a.id)
        await _create_session(db_session, candidate_id, company_b.id)

        resp = await client.get(
            f"{API}/interview-prep/sessions",
            headers=auth_headers,
            params={"company_id": str(company_a.id)},
        )
        data = resp.json()
        for s in data["sessions"]:
            assert s["company_id"] == str(company_a.id)

    @pytest.mark.asyncio
    async def test_list_sessions_pagination(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        company = await _create_company(db_session, candidate_id, "PaginateCo")
        for _ in range(3):
            await _create_session(db_session, candidate_id, company.id)

        resp = await client.get(
            f"{API}/interview-prep/sessions",
            headers=auth_headers,
            params={"skip": 0, "limit": 2},
        )
        data = resp.json()
        assert len(data["sessions"]) <= 2

    @pytest.mark.asyncio
    async def test_list_sessions_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{API}/interview-prep/sessions")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /interview-prep/sessions/{id}
# ---------------------------------------------------------------------------


class TestInterviewPrepGetSession:
    @pytest.mark.asyncio
    async def test_get_session_returns_data(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        company = await _create_company(db_session, candidate_id, "GetSessionCo")
        session = await _create_session(db_session, candidate_id, company.id)

        resp = await client.get(f"{API}/interview-prep/sessions/{session.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_id"] == str(company.id)

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(f"{API}/interview-prep/sessions/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_session_isolation(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, invite_code: str
    ):
        """Users cannot access other users' sessions."""
        # Create a second user
        other_email = f"other-{uuid.uuid4().hex[:8]}@test.com"
        await client.post(
            f"{API}/auth/register",
            json={
                "email": other_email,
                "password": "Testpass123",
                "full_name": "Other",
                "invite_code": invite_code,
            },
        )
        other_login = await client.post(
            f"{API}/auth/login",
            json={"email": other_email, "password": "Testpass123"},
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

        # Other user creates a session
        other_candidate_id = await _get_candidate_id(client, other_headers)
        company = await _create_company(db_session, other_candidate_id, "OtherCo")
        session = await _create_session(db_session, other_candidate_id, company.id)

        # Current user should not see it
        resp = await client.get(f"{API}/interview-prep/sessions/{session.id}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /interview-prep/mock/start
# ---------------------------------------------------------------------------


class TestMockInterviewStart:
    @pytest.mark.asyncio
    async def test_start_mock_interview(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        candidate_id = await _get_candidate_id(client, auth_headers)
        await _create_dna(db_session, candidate_id)
        company = await _create_company(db_session, candidate_id, "MockInterviewCo")

        resp = await client.post(
            f"{API}/interview-prep/mock/start",
            headers=auth_headers,
            json={"company_id": str(company.id), "interview_type": "behavioral"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prep_type"] == PrepType.MOCK_INTERVIEW.value
        assert "messages" in data
        # Should have the first question from the interviewer
        assert len(data["messages"]) >= 1
        assert data["messages"][0]["role"] == "interviewer"

    @pytest.mark.asyncio
    async def test_start_mock_invalid_interview_type(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        candidate_id = await _get_candidate_id(client, auth_headers)
        company = await _create_company(db_session, candidate_id, "BadTypeCo")

        resp = await client.post(
            f"{API}/interview-prep/mock/start",
            headers=auth_headers,
            json={"company_id": str(company.id), "interview_type": "invalid"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_start_mock_company_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            f"{API}/interview-prep/mock/start",
            headers=auth_headers,
            json={"company_id": str(uuid.uuid4()), "interview_type": "technical"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_start_mock_all_interview_types(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        candidate_id = await _get_candidate_id(client, auth_headers)
        await _create_dna(db_session, candidate_id)

        for interview_type in ("behavioral", "technical", "mixed"):
            company = await _create_company(db_session, candidate_id, f"MockCo-{interview_type}")
            resp = await client.post(
                f"{API}/interview-prep/mock/start",
                headers=auth_headers,
                json={"company_id": str(company.id), "interview_type": interview_type},
            )
            assert resp.status_code == 200, f"interview_type '{interview_type}' failed: {resp.text}"

    @pytest.mark.asyncio
    async def test_start_mock_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/interview-prep/mock/start",
            json={"company_id": str(uuid.uuid4()), "interview_type": "behavioral"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_start_mock_no_dna_still_works(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """Should work even if candidate has no CandidateDNA (falls back to default)."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        # Explicitly do NOT create DNA
        company = await _create_company(db_session, candidate_id, "NoDnaCo")

        resp = await client.post(
            f"{API}/interview-prep/mock/start",
            headers=auth_headers,
            json={"company_id": str(company.id), "interview_type": "behavioral"},
        )
        assert resp.status_code == 200
