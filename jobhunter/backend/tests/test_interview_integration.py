"""Integration tests for app/api/interview.py — covers uncovered route lines."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import CandidateDNA
from app.models.company import Company
from app.models.enums import PrepType, SessionStatus
from app.models.interview import InterviewPrepSession, MockInterviewMessage

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


async def _seed_company_and_dna(db_session: AsyncSession, candidate_id: uuid.UUID) -> Company:
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name="TestCo",
        domain="testco.com",
    )
    db_session.add(company)
    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="Senior software engineer with 8 years Python experience.",
        strengths=["Python", "System Design"],
        gaps=[],
        career_stage="senior",
    )
    db_session.add(dna)
    await db_session.flush()
    return company


async def _seed_mock_session(
    db_session: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
) -> InterviewPrepSession:
    session = InterviewPrepSession(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        company_id=company_id,
        prep_type=PrepType.MOCK_INTERVIEW,
        content={"interview_type": "behavioral", "status": SessionStatus.IN_PROGRESS, "score": None},
        status=SessionStatus.IN_PROGRESS,
    )
    db_session.add(session)
    # Add an initial interviewer message so the session has content
    msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="interviewer",
        content="Tell me about yourself.",
        turn_number=1,
    )
    db_session.add(msg)
    await db_session.flush()
    return session


# ---------------------------------------------------------------------------
# POST /interview-prep/generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_prep_valid_type(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)

    resp = await client.post(
        f"{API}/interview-prep/generate",
        headers=auth_headers,
        json={"company_id": str(company.id), "prep_type": "company_qa"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["prep_type"] == "company_qa"


@pytest.mark.asyncio
async def test_generate_prep_invalid_type(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)

    resp = await client.post(
        f"{API}/interview-prep/generate",
        headers=auth_headers,
        json={"company_id": str(company.id), "prep_type": "invalid_type"},
    )
    assert resp.status_code == 400
    assert "Invalid prep_type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_prep_company_not_found(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _get_candidate_id(client, auth_headers)
    fake_id = str(uuid.uuid4())

    resp = await client.post(
        f"{API}/interview-prep/generate",
        headers=auth_headers,
        json={"company_id": fake_id, "prep_type": "behavioral"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_prep_each_valid_type(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)

    for prep_type in ("behavioral", "technical", "culture_fit", "salary_negotiation"):
        resp = await client.post(
            f"{API}/interview-prep/generate",
            headers=auth_headers,
            json={"company_id": str(company.id), "prep_type": prep_type},
        )
        assert resp.status_code == 200, f"Failed for prep_type={prep_type}: {resp.text}"


# ---------------------------------------------------------------------------
# GET /interview-prep/sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/interview-prep/sessions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert "total" in data
    assert isinstance(data["sessions"], list)


@pytest.mark.asyncio
async def test_list_sessions_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)
    await _seed_mock_session(db_session, candidate_id, company.id)

    resp = await client.get(f"{API}/interview-prep/sessions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["sessions"]) >= 1


# ---------------------------------------------------------------------------
# GET /interview-prep/sessions/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_found(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)
    session = await _seed_mock_session(db_session, candidate_id, company.id)

    resp = await client.get(f"{API}/interview-prep/sessions/{session.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(session.id)
    assert data["prep_type"] == PrepType.MOCK_INTERVIEW


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = uuid.uuid4()
    resp = await client.get(f"{API}/interview-prep/sessions/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /interview-prep/mock/start
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_mock_interview(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)

    resp = await client.post(
        f"{API}/interview-prep/mock/start",
        headers=auth_headers,
        json={"company_id": str(company.id), "interview_type": "behavioral"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == SessionStatus.IN_PROGRESS
    assert data["prep_type"] == PrepType.MOCK_INTERVIEW
    # Should have at least one interviewer message
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["role"] == "interviewer"


@pytest.mark.asyncio
async def test_start_mock_interview_invalid_type(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)

    resp = await client.post(
        f"{API}/interview-prep/mock/start",
        headers=auth_headers,
        json={"company_id": str(company.id), "interview_type": "invalid"},
    )
    assert resp.status_code == 400
    assert "Invalid interview_type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_start_mock_interview_company_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"{API}/interview-prep/mock/start",
        headers=auth_headers,
        json={"company_id": str(uuid.uuid4()), "interview_type": "technical"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /interview-prep/mock/reply
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_mock_interview(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)
    session = await _seed_mock_session(db_session, candidate_id, company.id)

    resp = await client.post(
        f"{API}/interview-prep/mock/reply",
        headers=auth_headers,
        json={"session_id": str(session.id), "answer": "I have 8 years of Python experience."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "interviewer"
    assert data["content"] == "Test chat response"
    assert "turn_number" in data


@pytest.mark.asyncio
async def test_reply_mock_interview_session_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"{API}/interview-prep/mock/reply",
        headers=auth_headers,
        json={"session_id": str(uuid.uuid4()), "answer": "Some answer"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /interview-prep/mock/end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_mock_interview(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company_and_dna(db_session, candidate_id)
    session = await _seed_mock_session(db_session, candidate_id, company.id)

    resp = await client.post(
        f"{API}/interview-prep/mock/end",
        headers=auth_headers,
        json={"session_id": str(session.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == SessionStatus.COMPLETED
    # Session should have messages (original interviewer + feedback)
    assert len(data["messages"]) >= 1


@pytest.mark.asyncio
async def test_end_mock_interview_session_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"{API}/interview-prep/mock/end",
        headers=auth_headers,
        json={"session_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404
