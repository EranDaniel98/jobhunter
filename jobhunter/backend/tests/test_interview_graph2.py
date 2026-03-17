"""Additional unit tests for LangGraph interview prep pipeline nodes (error/edge paths)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**overrides):
    base = {
        "candidate_id": str(uuid.uuid4()),
        "company_id": str(uuid.uuid4()),
        "prep_type": "company_qa",
        "session_id": None,
        "context": None,
        "content": None,
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
        "company_name": "Acme",
        "industry": "Technology",
        "tech_stack": "Python, React",
        "size_range": "50-200",
        "culture_summary": "Collaborative culture",
        "red_flags": "None",
        "interview_format": "2 rounds",
        "compensation_data": "Unknown",
        "why_hire_me": "Strong fit",
        "candidate_summary": "5y backend",
        "strengths": "Python, FastAPI",
        "gaps": "Frontend",
        "career_stage": "mid",
    }


# ---------------------------------------------------------------------------
# load_context_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_context_company_not_found():
    from app.graphs.interview_prep import load_context_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state()

    with patch("app.graphs.interview_prep._db_mod.async_session_factory", return_value=mock_cm):
        result = await load_context_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_load_context_no_dossier_no_dna():
    """Should use defaults when dossier and DNA are missing."""
    from app.graphs.interview_prep import load_context_node

    mock_company = MagicMock()
    mock_company.id = uuid.uuid4()
    mock_company.name = "Acme"
    mock_company.industry = None
    mock_company.tech_stack = []
    mock_company.size_range = None

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_company)
        else:
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
        return mock_result

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute = AsyncMock(side_effect=side_effect_execute)
    mock_session.add = MagicMock()

    state = _state()

    with patch("app.graphs.interview_prep._db_mod.async_session_factory", return_value=mock_cm):
        result = await load_context_node(state)

    # Should succeed with defaults
    assert "session_id" in result
    assert result["status"] == "generating"
    ctx = result["context"]
    assert ctx["company_name"] == "Acme"
    assert ctx["candidate_summary"] == "No candidate profile"
    assert ctx["culture_summary"] == "Unknown"


# ---------------------------------------------------------------------------
# generate_prep_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_prep_node_unknown_prep_type():
    from app.graphs.interview_prep import generate_prep_node

    state = _state(prep_type="unknown_type", context=_sample_context())
    result = await generate_prep_node(state)

    assert result["status"] == "failed"
    assert "Unknown prep_type" in result["error"]


@pytest.mark.asyncio
async def test_generate_prep_node_openai_failure():
    from app.graphs.interview_prep import generate_prep_node

    state = _state(prep_type="company_qa", context=_sample_context())

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("OpenAI failure"))

    with patch("app.graphs.interview_prep.get_openai", return_value=mock_client):
        result = await generate_prep_node(state)

    assert result["status"] == "failed"
    assert "Generation failed" in result["error"]


@pytest.mark.asyncio
async def test_generate_prep_node_success():
    from app.graphs.interview_prep import generate_prep_node

    state = _state(prep_type="behavioral", context=_sample_context())

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(
        return_value={
            "stories": [
                {
                    "question": "Tell me about a time...",
                    "situation": "At previous job",
                    "task": "Lead a migration",
                    "action": "Designed new architecture",
                    "result": "Reduced latency by 50%",
                }
            ]
        }
    )

    with patch("app.graphs.interview_prep.get_openai", return_value=mock_client):
        result = await generate_prep_node(state)

    assert "content" in result
    assert len(result["content"]["stories"]) == 1


@pytest.mark.asyncio
async def test_generate_prep_node_all_prep_types():
    """Each known prep_type should build a valid prompt without errors."""
    from app.graphs.interview_prep import INTERVIEW_PREP_PROMPTS, generate_prep_node

    for prep_type in INTERVIEW_PREP_PROMPTS:
        mock_client = MagicMock()
        mock_client.parse_structured = AsyncMock(
            return_value={
                "stories": [],
                "questions": [],
                "topics": [],
                "values": [],
                "tips": [],
                "strategies": [],
                "talking_points": [],
                "salary_range": {"low": 80000, "mid": 100000, "high": 120000},
            }
        )

        state = _state(prep_type=prep_type, context=_sample_context())

        with patch("app.graphs.interview_prep.get_openai", return_value=mock_client):
            result = await generate_prep_node(state)

        # None of the valid prep types should fail
        assert result.get("status") != "failed", f"prep_type={prep_type} failed unexpectedly"


# ---------------------------------------------------------------------------
# save_and_notify_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_notify_session_not_found():
    from app.graphs.interview_prep import save_and_notify_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    session_id = str(uuid.uuid4())
    state = _state(
        session_id=session_id,
        content={"questions": []},
        status="generating",
    )

    with patch("app.graphs.interview_prep._db_mod.async_session_factory", return_value=mock_cm):
        result = await save_and_notify_node(state)

    assert result["status"] == "failed"
    assert "Session not found" in result["error"]


@pytest.mark.asyncio
async def test_save_and_notify_db_failure():
    from app.graphs.interview_prep import save_and_notify_node

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(side_effect=Exception("DB connection lost"))
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    session_id = str(uuid.uuid4())
    state = _state(
        session_id=session_id,
        content={"questions": []},
        status="generating",
    )

    with patch("app.graphs.interview_prep._db_mod.async_session_factory", return_value=mock_cm):
        result = await save_and_notify_node(state)

    assert result["status"] == "failed"
    assert "Failed to save prep session" in result["error"]


@pytest.mark.asyncio
async def test_save_and_notify_success():
    from app.graphs.interview_prep import save_and_notify_node

    mock_prep_session = MagicMock()
    mock_prep_session.content = None
    mock_prep_session.status = "generating"

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_prep_session))

    session_id = str(uuid.uuid4())
    state = _state(
        session_id=session_id,
        content={"questions": [{"question": "Q1", "answer": "A1", "category": "technical"}]},
        status="generating",
        prep_type="company_qa",
    )

    broadcast_mock = AsyncMock()
    with (
        patch("app.graphs.interview_prep._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.interview_prep.ws_manager.broadcast", new=broadcast_mock),
    ):
        result = await save_and_notify_node(state)

    assert result["status"] == "completed"
    assert mock_prep_session.status == "completed"
    broadcast_mock.assert_called_once()


# ---------------------------------------------------------------------------
# mark_failed_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_failed_node_with_session():
    from app.graphs.interview_prep import mark_failed_node

    mock_prep_session = MagicMock()
    mock_prep_session.status = "generating"
    mock_prep_session.error = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_prep_session))

    session_id = str(uuid.uuid4())
    state = _state(session_id=session_id, error="generation failed")

    broadcast_mock = AsyncMock()
    with (
        patch("app.graphs.interview_prep._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.interview_prep.ws_manager.broadcast", new=broadcast_mock),
    ):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"
    assert mock_prep_session.status == "failed"
    assert mock_prep_session.error == "generation failed"
    broadcast_mock.assert_called_once()


@pytest.mark.asyncio
async def test_mark_failed_node_no_session():
    from app.graphs.interview_prep import mark_failed_node

    state = _state(session_id=None, error="early failure")

    broadcast_mock = AsyncMock()
    with patch("app.graphs.interview_prep.ws_manager.broadcast", new=broadcast_mock):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"
    broadcast_mock.assert_called_once()


# ---------------------------------------------------------------------------
# _check_error routing
# ---------------------------------------------------------------------------


def test_check_error_routes_correctly():
    from app.graphs.interview_prep import _check_error

    assert _check_error(_state(status="failed")) == "mark_failed"
    assert _check_error(_state(status="pending")) == "continue"
    assert _check_error(_state(status="generating")) == "continue"
    assert _check_error(_state(status="completed")) == "continue"
