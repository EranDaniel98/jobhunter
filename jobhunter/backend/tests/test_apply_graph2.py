"""Additional unit tests for LangGraph apply pipeline nodes (error/edge paths)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**overrides):
    base = {
        "candidate_id": str(uuid.uuid4()),
        "job_posting_id": str(uuid.uuid4()),
        "parsed_requirements": None,
        "candidate_skills": None,
        "matching_skills": None,
        "missing_skills": None,
        "resume_tips": None,
        "readiness_score": None,
        "cover_letter": None,
        "ats_keywords": None,
        "context": None,
        "status": "pending",
        "error": None,
    }
    base.update(overrides)
    return base


def _make_mock_db_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


def _sample_context():
    return {
        "title": "Software Engineer",
        "company_name": "Acme",
        "raw_text": "We need a Python developer",
        "candidate_summary": "5y backend",
        "gaps": "Frontend",
        "why_hire_me": "Strong fit",
    }


def _sample_parsed_requirements():
    return {
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["React"],
        "experience_years": 3,
        "education": "BS",
        "responsibilities": ["Build APIs"],
        "ats_keywords": ["python", "api"],
    }


# ---------------------------------------------------------------------------
# parse_job_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_job_node_posting_not_found():
    from app.graphs.apply_pipeline import parse_job_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state()

    with patch("app.graphs.apply_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await parse_job_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_parse_job_node_openai_failure():
    from app.graphs.apply_pipeline import parse_job_node

    mock_posting = MagicMock()
    mock_posting.id = uuid.uuid4()
    mock_posting.title = "Software Engineer"
    mock_posting.company_name = "Acme"
    mock_posting.raw_text = "We need Python"
    mock_posting.company_id = None

    mock_dna = MagicMock()
    mock_dna.experience_summary = "5y backend"
    mock_dna.gaps = []

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_posting)
        elif call_count == 2:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_dna)
        else:
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        return mock_result

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("OpenAI error"))

    state = _state()

    with (
        patch("app.graphs.apply_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.apply_pipeline.get_openai", return_value=mock_client),
    ):
        result = await parse_job_node(state)

    assert result["status"] == "failed"
    assert "Job parsing failed" in result["error"]


# ---------------------------------------------------------------------------
# match_skills_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_skills_node_missing_requirements():
    from app.graphs.apply_pipeline import match_skills_node

    state = _state(parsed_requirements=None, candidate_skills=None)
    result = await match_skills_node(state)

    assert result["status"] == "failed"
    assert "Missing requirements" in result["error"]


@pytest.mark.asyncio
async def test_match_skills_node_correct_matching():
    from app.graphs.apply_pipeline import match_skills_node

    state = _state(
        parsed_requirements={
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferred_skills": ["React"],
        },
        candidate_skills=["python", "fastapi", "docker"],
    )
    result = await match_skills_node(state)

    assert "matching_skills" in result
    assert "missing_skills" in result
    assert "python" in result["matching_skills"]
    assert "fastapi" in result["matching_skills"]
    # PostgreSQL is required but candidate doesn't have it
    assert "postgresql" in result["missing_skills"]
    # React is preferred but not in candidate → not in missing (only required go into missing)
    assert "react" not in result["missing_skills"]


@pytest.mark.asyncio
async def test_match_skills_node_empty_skills():
    from app.graphs.apply_pipeline import match_skills_node

    state = _state(
        parsed_requirements={
            "required_skills": ["Python"],
            "preferred_skills": [],
        },
        candidate_skills=[],
    )
    result = await match_skills_node(state)

    assert result["matching_skills"] == []
    assert "python" in result["missing_skills"]


# ---------------------------------------------------------------------------
# generate_tips_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_tips_node_openai_failure():
    from app.graphs.apply_pipeline import generate_tips_node

    state = _state(
        context=_sample_context(),
        parsed_requirements=_sample_parsed_requirements(),
        candidate_skills=["python"],
    )

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("Tips API error"))

    with patch("app.graphs.apply_pipeline.get_openai", return_value=mock_client):
        result = await generate_tips_node(state)

    assert result["status"] == "failed"
    assert "Tips generation failed" in result["error"]


@pytest.mark.asyncio
async def test_generate_tips_node_success():
    from app.graphs.apply_pipeline import generate_tips_node

    state = _state(
        context=_sample_context(),
        parsed_requirements=_sample_parsed_requirements(),
        candidate_skills=["python"],
    )

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(
        return_value={
            "tips": [{"section": "Skills", "tip": "Add FastAPI", "priority": "high"}],
            "readiness_score": 0.75,
        }
    )

    with patch("app.graphs.apply_pipeline.get_openai", return_value=mock_client):
        result = await generate_tips_node(state)

    assert result["resume_tips"] == [{"section": "Skills", "tip": "Add FastAPI", "priority": "high"}]
    assert result["readiness_score"] == 0.75


# ---------------------------------------------------------------------------
# generate_cover_letter_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_cover_letter_node_openai_failure():
    from app.graphs.apply_pipeline import generate_cover_letter_node

    state = _state(
        context=_sample_context(),
        parsed_requirements=_sample_parsed_requirements(),
        matching_skills=["python"],
    )

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("Cover letter error"))

    with patch("app.graphs.apply_pipeline.get_openai", return_value=mock_client):
        result = await generate_cover_letter_node(state)

    assert result["status"] == "failed"
    assert "Cover letter generation failed" in result["error"]


@pytest.mark.asyncio
async def test_generate_cover_letter_node_success():
    from app.graphs.apply_pipeline import generate_cover_letter_node

    state = _state(
        context=_sample_context(),
        parsed_requirements=_sample_parsed_requirements(),
        matching_skills=["python", "fastapi"],
    )

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(
        return_value={"cover_letter": "Dear Hiring Manager, I am excited to apply..."}
    )

    with patch("app.graphs.apply_pipeline.get_openai", return_value=mock_client):
        result = await generate_cover_letter_node(state)

    assert "cover_letter" in result
    assert "excited" in result["cover_letter"]


# ---------------------------------------------------------------------------
# save_and_notify_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_notify_node_redis_failure():
    from app.graphs.apply_pipeline import save_and_notify_node

    job_posting_id = str(uuid.uuid4())

    mock_posting = MagicMock()
    mock_posting.parsed_requirements = None
    mock_posting.ats_keywords = None
    mock_posting.status = "pending"

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_posting))

    mock_redis = MagicMock()
    mock_redis.set = AsyncMock(side_effect=Exception("Redis unavailable"))

    state = _state(
        job_posting_id=job_posting_id,
        parsed_requirements=_sample_parsed_requirements(),
        ats_keywords=["python"],
        readiness_score=0.8,
        resume_tips=[],
        cover_letter="Dear...",
        missing_skills=[],
        matching_skills=["python"],
    )

    with (
        patch("app.graphs.apply_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
    ):
        result = await save_and_notify_node(state)

    assert result["status"] == "failed"
    assert "Failed to cache analysis" in result["error"]


# ---------------------------------------------------------------------------
# mark_failed_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_failed_node_with_job_posting():
    from app.graphs.apply_pipeline import mark_failed_node

    mock_posting = MagicMock()
    mock_posting.status = "pending"

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_posting))

    job_posting_id = str(uuid.uuid4())
    state = _state(job_posting_id=job_posting_id, error="parse failed")

    broadcast_mock = AsyncMock()
    with (
        patch("app.graphs.apply_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.apply_pipeline.ws_manager.broadcast", new=broadcast_mock),
    ):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"
    assert mock_posting.status == "failed"
    broadcast_mock.assert_called_once()


@pytest.mark.asyncio
async def test_mark_failed_node_no_job_posting():
    from app.graphs.apply_pipeline import mark_failed_node

    state = _state(job_posting_id=None, error="some error")

    broadcast_mock = AsyncMock()
    with patch("app.graphs.apply_pipeline.ws_manager.broadcast", new=broadcast_mock):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# _check_error routing
# ---------------------------------------------------------------------------


def test_check_error_routes_correctly():
    from app.graphs.apply_pipeline import _check_error

    assert _check_error(_state(status="failed")) == "mark_failed"
    assert _check_error(_state(status="pending")) == "continue"
    assert _check_error(_state(status="completed")) == "continue"
