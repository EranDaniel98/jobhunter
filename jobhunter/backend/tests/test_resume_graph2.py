"""Additional unit tests for LangGraph resume pipeline nodes (error/edge paths)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**overrides):
    base = {
        "resume_id": str(uuid.uuid4()),
        "candidate_id": str(uuid.uuid4()),
        "parsed_data": None,
        "raw_text": None,
        "skills_data": None,
        "dna_data": None,
        "embedding": None,
        "skills_vector": None,
        "fit_scores_updated": 0,
        "status": "pending",
        "error": None,
    }
    base.update(overrides)
    return base


def _make_mock_db_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


# ---------------------------------------------------------------------------
# parse_resume_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_resume_node_not_found():
    from app.graphs.resume_pipeline import parse_resume_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state()

    with patch("app.graphs.resume_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await parse_resume_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_parse_resume_node_no_raw_text():
    from app.graphs.resume_pipeline import parse_resume_node

    mock_resume = MagicMock()
    mock_resume.raw_text = None
    mock_resume.parse_status = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_resume))

    state = _state()

    with patch("app.graphs.resume_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await parse_resume_node(state)

    assert result["status"] == "failed"
    assert "no extracted text" in result["error"]
    assert mock_resume.parse_status is not None  # Was set to FAILED


@pytest.mark.asyncio
async def test_parse_resume_node_openai_failure():
    from app.graphs.resume_pipeline import parse_resume_node

    mock_resume = MagicMock()
    mock_resume.raw_text = "John Doe, Software Engineer"
    mock_resume.parsed_data = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_resume))

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("OpenAI down"))

    state = _state()

    with (
        patch("app.graphs.resume_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.resume_pipeline.get_openai", return_value=mock_client),
    ):
        result = await parse_resume_node(state)

    assert result["status"] == "failed"
    assert "Resume parsing failed" in result["error"]


# ---------------------------------------------------------------------------
# extract_skills_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_skills_node_no_raw_text():
    from app.graphs.resume_pipeline import extract_skills_node

    state = _state(raw_text=None)
    result = await extract_skills_node(state)

    assert result["status"] == "failed"
    assert "No raw_text" in result["error"]


@pytest.mark.asyncio
async def test_extract_skills_node_empty_raw_text():
    from app.graphs.resume_pipeline import extract_skills_node

    state = _state(raw_text="")
    result = await extract_skills_node(state)

    assert result["status"] == "failed"
    assert "No raw_text" in result["error"]


@pytest.mark.asyncio
async def test_extract_skills_node_openai_failure():
    from app.graphs.resume_pipeline import extract_skills_node

    state = _state(raw_text="Senior Python engineer with 5 years experience")

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("API error"))

    with patch("app.graphs.resume_pipeline.get_openai", return_value=mock_client):
        result = await extract_skills_node(state)

    assert result["status"] == "failed"
    assert "Skills extraction failed" in result["error"]


# ---------------------------------------------------------------------------
# generate_dna_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_dna_node_missing_parsed_data():
    from app.graphs.resume_pipeline import generate_dna_node

    state = _state(parsed_data=None, skills_data={"skills": []}, raw_text="text")
    result = await generate_dna_node(state)

    assert result["status"] == "failed"
    assert "Missing parsed_data or skills_data" in result["error"]


@pytest.mark.asyncio
async def test_generate_dna_node_missing_skills_data():
    from app.graphs.resume_pipeline import generate_dna_node

    state = _state(parsed_data={"name": "John"}, skills_data=None, raw_text="text")
    result = await generate_dna_node(state)

    assert result["status"] == "failed"
    assert "Missing parsed_data or skills_data" in result["error"]


@pytest.mark.asyncio
async def test_generate_dna_node_embed_failure():
    from app.graphs.resume_pipeline import generate_dna_node

    state = _state(
        parsed_data={"name": "John", "experience": []},
        skills_data={"skills": [{"name": "Python", "category": "explicit"}]},
        raw_text="Python developer",
    )

    with patch("app.graphs.resume_pipeline.embed_text", AsyncMock(side_effect=Exception("embed error"))):
        result = await generate_dna_node(state)

    assert result["status"] == "failed"
    assert "DNA generation failed" in result["error"]


# ---------------------------------------------------------------------------
# recalculate_fits_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recalculate_fits_node_failure():
    from app.graphs.resume_pipeline import recalculate_fits_node

    mock_cm, _mock_session = _make_mock_db_session()

    state = _state()

    with (
        patch("app.graphs.resume_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch(
            "app.graphs.resume_pipeline.recalculate_fit_scores",
            AsyncMock(side_effect=Exception("DB constraint")),
        ),
    ):
        result = await recalculate_fits_node(state)

    assert result["status"] == "failed"
    assert "Fit score recalculation failed" in result["error"]


@pytest.mark.asyncio
async def test_recalculate_fits_node_success():
    from app.graphs.resume_pipeline import recalculate_fits_node

    mock_cm, _mock_session = _make_mock_db_session()

    state = _state()

    with (
        patch("app.graphs.resume_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.resume_pipeline.recalculate_fit_scores", AsyncMock(return_value=5)),
    ):
        result = await recalculate_fits_node(state)

    assert result["fit_scores_updated"] == 5


# ---------------------------------------------------------------------------
# notify_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_node_broadcasts_completed():
    from app.graphs.resume_pipeline import notify_node

    mock_resume = MagicMock()
    mock_resume.parse_status = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_resume))

    resume_id = str(uuid.uuid4())
    candidate_id = str(uuid.uuid4())
    state = _state(
        resume_id=resume_id,
        candidate_id=candidate_id,
        fit_scores_updated=3,
        skills_data={"skills": [{"name": "Python"}]},
    )

    broadcast_mock = AsyncMock()
    mock_event_bus = MagicMock()
    mock_event_bus.publish = AsyncMock()

    with (
        patch("app.graphs.resume_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.resume_pipeline.ws_manager.broadcast", new=broadcast_mock),
        patch("app.events.bus.get_event_bus", return_value=mock_event_bus),
    ):
        result = await notify_node(state)

    assert result["status"] == "completed"
    broadcast_mock.assert_called_once()
    mock_event_bus.publish.assert_called_once()


@pytest.mark.asyncio
async def test_notify_node_resume_not_found_still_completes():
    from app.graphs.resume_pipeline import notify_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    resume_id = str(uuid.uuid4())
    candidate_id = str(uuid.uuid4())
    state = _state(resume_id=resume_id, candidate_id=candidate_id, skills_data=None)

    mock_event_bus = MagicMock()
    mock_event_bus.publish = AsyncMock()

    with (
        patch("app.graphs.resume_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.resume_pipeline.ws_manager.broadcast", new=AsyncMock()),
        patch("app.events.bus.get_event_bus", return_value=mock_event_bus),
    ):
        result = await notify_node(state)

    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# mark_failed_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_failed_node_marks_resume():
    from app.graphs.resume_pipeline import mark_failed_node

    mock_resume = MagicMock()
    mock_resume.parse_status = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_resume))

    resume_id = str(uuid.uuid4())
    candidate_id = str(uuid.uuid4())
    state = _state(resume_id=resume_id, candidate_id=candidate_id, error="parse error")

    broadcast_mock = AsyncMock()
    with (
        patch("app.graphs.resume_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.resume_pipeline.ws_manager.broadcast", new=broadcast_mock),
    ):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"
    assert mock_resume.parse_status is not None  # Was set to FAILED
    broadcast_mock.assert_called_once()


# ---------------------------------------------------------------------------
# init_checkpointer / close_checkpointer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_checkpointer():
    from app.graphs.resume_pipeline import init_checkpointer

    mock_saver = MagicMock()
    mock_saver.setup = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.from_conn_string",
        return_value=mock_cm,
    ):
        await init_checkpointer("postgresql+asyncpg://user:pass@localhost/testdb")

    mock_saver.setup.assert_called_once()


@pytest.mark.asyncio
async def test_close_checkpointer_noop_when_none():
    """close_checkpointer should be a no-op when not initialized."""
    import app.graphs.resume_pipeline as pipeline_mod
    from app.graphs.resume_pipeline import close_checkpointer

    # Save originals
    orig_cm = pipeline_mod._checkpointer_cm
    orig_cp = pipeline_mod._checkpointer

    try:
        pipeline_mod._checkpointer_cm = None
        pipeline_mod._checkpointer = None
        await close_checkpointer()  # Should not raise
    finally:
        pipeline_mod._checkpointer_cm = orig_cm
        pipeline_mod._checkpointer = orig_cp


@pytest.mark.asyncio
async def test_close_checkpointer_calls_aexit():
    import app.graphs.resume_pipeline as pipeline_mod
    from app.graphs.resume_pipeline import close_checkpointer

    orig_cm = pipeline_mod._checkpointer_cm
    orig_cp = pipeline_mod._checkpointer

    try:
        mock_cm = MagicMock()
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        pipeline_mod._checkpointer_cm = mock_cm
        pipeline_mod._checkpointer = MagicMock()

        await close_checkpointer()

        mock_cm.__aexit__.assert_called_once_with(None, None, None)
        assert pipeline_mod._checkpointer_cm is None
        assert pipeline_mod._checkpointer is None
    finally:
        pipeline_mod._checkpointer_cm = orig_cm
        pipeline_mod._checkpointer = orig_cp


# ---------------------------------------------------------------------------
# _check_error routing
# ---------------------------------------------------------------------------


def test_check_error_routes_correctly():
    from app.graphs.resume_pipeline import _check_error

    assert _check_error(_state(status="failed")) == "mark_failed"
    assert _check_error(_state(status="pending")) == "continue"
    assert _check_error(_state(status="completed")) == "continue"
