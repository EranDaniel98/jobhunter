"""Integration tests for app/api/interview.py — second pass.

Targets uncovered lines:
- Lines 187-240: POST /mock/start full flow (with/without DNA, various interview types)
- Lines 264-316: POST /mock/reply — save answer + get interviewer response, completed session
- Lines 340-387: POST /mock/end — feedback generation, re-fetch session
"""

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


async def _seed_company(db_session: AsyncSession, candidate_id: uuid.UUID, name: str = "MockCo") -> Company:
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=name,
        domain=f"{name.lower().replace(' ', '')}.com",
        industry="Technology",
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def _seed_dna(
    db_session: AsyncSession,
    candidate_id: uuid.UUID,
    summary: str = "Senior Python engineer with 8 years experience.",
) -> CandidateDNA:
    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary=summary,
        strengths=["Python", "System Design", "APIs"],
        gaps=["Mobile development"],
        career_stage="senior",
    )
    db_session.add(dna)
    await db_session.flush()
    return dna


async def _seed_mock_session(
    db_session: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
    status: SessionStatus = SessionStatus.IN_PROGRESS,
    interview_type: str = "behavioral",
) -> InterviewPrepSession:
    session = InterviewPrepSession(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        company_id=company_id,
        prep_type=PrepType.MOCK_INTERVIEW,
        content={"interview_type": interview_type, "status": status, "score": None},
        status=status,
    )
    db_session.add(session)
    msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="interviewer",
        content="Tell me about your greatest technical challenge.",
        turn_number=1,
    )
    db_session.add(msg)
    await db_session.flush()
    return session


# ---------------------------------------------------------------------------
# POST /mock/start — full flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_mock_interview_with_dna(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Start mock interview with DNA seeded — uses DNA for system prompt."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)
    await _seed_dna(db_session, candidate_id)

    resp = await client.post(
        f"{API}/interview-prep/mock/start",
        headers=auth_headers,
        json={"company_id": str(company.id), "interview_type": "behavioral"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == SessionStatus.IN_PROGRESS
    assert data["prep_type"] == PrepType.MOCK_INTERVIEW
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["role"] == "interviewer"
    assert data["messages"][0]["content"] == "Test chat response"


@pytest.mark.asyncio
async def test_start_mock_interview_without_dna(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Start mock interview without DNA — falls back to 'Software engineer' summary."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id, "NoDnaCo")
    # No DNA seeded intentionally

    resp = await client.post(
        f"{API}/interview-prep/mock/start",
        headers=auth_headers,
        json={"company_id": str(company.id), "interview_type": "technical"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == SessionStatus.IN_PROGRESS
    # First message must be from interviewer
    assert data["messages"][0]["role"] == "interviewer"


@pytest.mark.asyncio
async def test_start_mock_interview_mixed_type(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Start mock interview with interview_type='mixed'."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id, "MixedCo")
    await _seed_dna(db_session, candidate_id)

    resp = await client.post(
        f"{API}/interview-prep/mock/start",
        headers=auth_headers,
        json={"company_id": str(company.id), "interview_type": "mixed"},
    )
    assert resp.status_code == 200
    assert resp.json()["prep_type"] == PrepType.MOCK_INTERVIEW


@pytest.mark.asyncio
async def test_start_mock_interview_invalid_type(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Invalid interview_type returns 400."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)

    resp = await client.post(
        f"{API}/interview-prep/mock/start",
        headers=auth_headers,
        json={"company_id": str(company.id), "interview_type": "panel"},
    )
    assert resp.status_code == 400
    assert "Invalid interview_type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_start_mock_interview_company_not_found(client: AsyncClient, auth_headers: dict):
    """Company not in candidate's scope returns 404."""
    resp = await client.post(
        f"{API}/interview-prep/mock/start",
        headers=auth_headers,
        json={"company_id": str(uuid.uuid4()), "interview_type": "behavioral"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /mock/reply — answer + interviewer response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_mock_interview_full_flow(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Reply saves candidate answer and returns interviewer response."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)
    await _seed_dna(db_session, candidate_id)
    session = await _seed_mock_session(db_session, candidate_id, company.id)

    resp = await client.post(
        f"{API}/interview-prep/mock/reply",
        headers=auth_headers,
        json={
            "session_id": str(session.id),
            "answer": "I overcame the challenge by refactoring the legacy system.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "interviewer"
    assert data["content"] == "Test chat response"
    assert data["turn_number"] == 3  # turn 1 = first question, 2 = answer, 3 = response


@pytest.mark.asyncio
async def test_reply_mock_interview_without_dna(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Reply works without DNA — uses fallback summary."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id, "NoDnaCo2")
    # No DNA
    session = await _seed_mock_session(db_session, candidate_id, company.id)

    resp = await client.post(
        f"{API}/interview-prep/mock/reply",
        headers=auth_headers,
        json={"session_id": str(session.id), "answer": "My answer here."},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "interviewer"


@pytest.mark.asyncio
async def test_reply_completed_session_returns_400(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Replying to a COMPLETED mock session returns 400."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)
    session = await _seed_mock_session(db_session, candidate_id, company.id, status=SessionStatus.COMPLETED)

    resp = await client.post(
        f"{API}/interview-prep/mock/reply",
        headers=auth_headers,
        json={"session_id": str(session.id), "answer": "Too late."},
    )
    assert resp.status_code == 400
    assert "completed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reply_session_not_found(client: AsyncClient, auth_headers: dict):
    """Reply to non-existent session returns 404."""
    resp = await client.post(
        f"{API}/interview-prep/mock/reply",
        headers=auth_headers,
        json={"session_id": str(uuid.uuid4()), "answer": "Some answer"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reply_wrong_prep_type_returns_404(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Reply requires MOCK_INTERVIEW prep type; other types return 404."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)
    # Create a non-mock session
    session = InterviewPrepSession(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        company_id=company.id,
        prep_type=PrepType.BEHAVIORAL,
        content={},
        status=SessionStatus.COMPLETED,
    )
    db_session.add(session)
    await db_session.flush()

    resp = await client.post(
        f"{API}/interview-prep/mock/reply",
        headers=auth_headers,
        json={"session_id": str(session.id), "answer": "Wrong type"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /mock/end — feedback generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_mock_interview_full_flow(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """End interview generates feedback and marks session COMPLETED."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)
    await _seed_dna(db_session, candidate_id)
    session = await _seed_mock_session(db_session, candidate_id, company.id)

    resp = await client.post(
        f"{API}/interview-prep/mock/end",
        headers=auth_headers,
        json={"session_id": str(session.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == SessionStatus.COMPLETED
    assert data["id"] == str(session.id)
    # Should have at least the original interviewer message
    assert len(data["messages"]) >= 1


@pytest.mark.asyncio
async def test_end_mock_interview_sets_score(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """End interview stores overall_score in session content."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)
    session = await _seed_mock_session(db_session, candidate_id, company.id)

    resp = await client.post(
        f"{API}/interview-prep/mock/end",
        headers=auth_headers,
        json={"session_id": str(session.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    # content should have score (from OpenAI stub: 7.5)
    assert data["content"] is not None
    assert data["content"].get("score") == 7.5


@pytest.mark.asyncio
async def test_end_mock_interview_session_not_found(client: AsyncClient, auth_headers: dict):
    """End non-existent session returns 404."""
    resp = await client.post(
        f"{API}/interview-prep/mock/end",
        headers=auth_headers,
        json={"session_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_end_mock_interview_wrong_prep_type_returns_404(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """End requires MOCK_INTERVIEW prep type; other types return 404."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)
    session = InterviewPrepSession(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        company_id=company.id,
        prep_type=PrepType.TECHNICAL,
        content={},
        status=SessionStatus.IN_PROGRESS,
    )
    db_session.add(session)
    await db_session.flush()

    resp = await client.post(
        f"{API}/interview-prep/mock/end",
        headers=auth_headers,
        json={"session_id": str(session.id)},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /sessions — filter by company_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_filter_by_company(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Listing sessions with company_id filter returns only that company's sessions."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    co1 = await _seed_company(db_session, candidate_id, "FilterCo1")
    co2 = await _seed_company(db_session, candidate_id, "FilterCo2")
    s1 = await _seed_mock_session(db_session, candidate_id, co1.id)
    await _seed_mock_session(db_session, candidate_id, co2.id)

    resp = await client.get(
        f"{API}/interview-prep/sessions?company_id={co1.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    session_ids = [s["id"] for s in data["sessions"]]
    assert str(s1.id) in session_ids
    # co2's session should not appear
    for s in data["sessions"]:
        assert s["company_id"] == str(co1.id)
