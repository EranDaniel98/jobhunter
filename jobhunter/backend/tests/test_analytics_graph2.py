"""Additional unit tests for LangGraph analytics pipeline nodes (error/edge paths)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**overrides):
    base = {
        "candidate_id": str(uuid.uuid4()),
        "include_email": False,
        "raw_data": None,
        "insights": None,
        "insights_saved": 0,
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


def _sample_raw_data():
    return {
        "funnel": {"applied": 10, "responded": 3},
        "outreach": {"sent": 20, "opened": 8},
        "pipeline": {"active": 5},
        "skill_count": 12,
        "skills": ["Python", "FastAPI"],
        "career_stage": "mid",
        "experience_summary": "5y backend",
    }


def _sample_insights():
    return [
        {
            "insight_type": "pipeline_health",
            "title": "Good pipeline velocity",
            "body": "You have 5 active opportunities.",
            "severity": "info",
            "data": {"active": 5},
        }
    ]


# ---------------------------------------------------------------------------
# gather_data_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_data_node_db_failure():
    from app.graphs.analytics_pipeline import gather_data_node

    state = _state()

    with patch("app.graphs.analytics_pipeline._db_mod.async_session_factory") as mock_factory:
        mock_factory.side_effect = Exception("DB connection failed")
        result = await gather_data_node(state)

    assert result["status"] == "failed"
    assert "Data gathering failed" in result["error"]


@pytest.mark.asyncio
async def test_gather_data_node_analytics_service_failure():
    from app.graphs.analytics_pipeline import gather_data_node

    mock_cm, mock_session = _make_mock_db_session()

    # Make skills query return empty
    mock_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        scalar_one_or_none=MagicMock(return_value=None),
    )

    state = _state()

    with (
        patch("app.graphs.analytics_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch(
            "app.services.analytics_service.get_funnel",
            AsyncMock(side_effect=Exception("Analytics service error")),
        ),
    ):
        result = await gather_data_node(state)

    assert result["status"] == "failed"
    assert "Data gathering failed" in result["error"]


# ---------------------------------------------------------------------------
# generate_insights_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_insights_node_openai_failure():
    from app.graphs.analytics_pipeline import generate_insights_node

    state = _state(raw_data=_sample_raw_data())

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("OpenAI rate limit"))

    with patch("app.graphs.analytics_pipeline.get_openai", return_value=mock_client):
        result = await generate_insights_node(state)

    assert result["status"] == "failed"
    assert "Insight generation failed" in result["error"]


@pytest.mark.asyncio
async def test_generate_insights_node_empty_raw_data():
    """Empty raw_data should still call OpenAI (with empty values)."""
    from app.graphs.analytics_pipeline import generate_insights_node

    state = _state(raw_data={})

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(return_value={"insights": []})

    with patch("app.graphs.analytics_pipeline.get_openai", return_value=mock_client):
        result = await generate_insights_node(state)

    assert result["insights"] == []


@pytest.mark.asyncio
async def test_generate_insights_node_success():
    from app.graphs.analytics_pipeline import generate_insights_node

    state = _state(raw_data=_sample_raw_data())

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(return_value={"insights": _sample_insights()})

    with patch("app.graphs.analytics_pipeline.get_openai", return_value=mock_client):
        result = await generate_insights_node(state)

    assert len(result["insights"]) == 1
    assert result["insights"][0]["insight_type"] == "pipeline_health"


# ---------------------------------------------------------------------------
# save_insights_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_insights_node_db_failure():
    from app.graphs.analytics_pipeline import save_insights_node

    state = _state(insights=_sample_insights())

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(side_effect=Exception("DB write error"))
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.graphs.analytics_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await save_insights_node(state)

    assert result["status"] == "failed"
    assert "Failed to save insights" in result["error"]


@pytest.mark.asyncio
async def test_save_insights_node_empty_insights():
    from app.graphs.analytics_pipeline import save_insights_node

    mock_cm, _mock_session = _make_mock_db_session()

    state = _state(insights=[])

    with patch("app.graphs.analytics_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await save_insights_node(state)

    assert result["insights_saved"] == 0


@pytest.mark.asyncio
async def test_save_insights_node_saves_correctly():
    from app.graphs.analytics_pipeline import save_insights_node

    mock_cm, mock_session = _make_mock_db_session()

    state = _state(insights=_sample_insights())

    with patch("app.graphs.analytics_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await save_insights_node(state)

    assert result["insights_saved"] == 1
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# notify_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_node_basic():
    from app.graphs.analytics_pipeline import notify_node

    candidate_id = str(uuid.uuid4())
    state = _state(candidate_id=candidate_id, insights_saved=3, include_email=False)

    broadcast_mock = AsyncMock()
    with patch("app.graphs.analytics_pipeline.ws_manager.broadcast", new=broadcast_mock):
        result = await notify_node(state)

    assert result["status"] == "completed"
    broadcast_mock.assert_called_once()


@pytest.mark.asyncio
async def test_notify_node_broadcast_failure_swallowed():
    """Broadcast failure should not prevent completion."""
    from app.graphs.analytics_pipeline import notify_node

    state = _state(insights_saved=2, include_email=False)

    with patch(
        "app.graphs.analytics_pipeline.ws_manager.broadcast",
        new=AsyncMock(side_effect=Exception("WS down")),
    ):
        result = await notify_node(state)

    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_notify_node_with_email():
    from app.graphs.analytics_pipeline import notify_node

    candidate_id = str(uuid.uuid4())

    mock_candidate = MagicMock()
    mock_candidate.email = "test@example.com"
    mock_candidate.id = uuid.UUID(candidate_id)

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))

    mock_email_client = MagicMock()
    mock_email_client.send = AsyncMock(return_value={"id": "email-123"})

    state = _state(
        candidate_id=candidate_id,
        include_email=True,
        insights=_sample_insights(),
        insights_saved=1,
    )

    with (
        patch("app.graphs.analytics_pipeline.ws_manager.broadcast", new=AsyncMock()),
        patch("app.graphs.analytics_pipeline.get_email_client", return_value=mock_email_client),
        patch("app.graphs.analytics_pipeline._db_mod.async_session_factory", return_value=mock_cm),
    ):
        result = await notify_node(state)

    assert result["status"] == "completed"
    mock_email_client.send.assert_called_once()


@pytest.mark.asyncio
async def test_notify_node_email_failure_swallowed():
    """Email send failure should not prevent completion (logged as warning)."""
    from app.graphs.analytics_pipeline import notify_node

    candidate_id = str(uuid.uuid4())

    mock_candidate = MagicMock()
    mock_candidate.email = "test@example.com"

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))

    mock_email_client = MagicMock()
    mock_email_client.send = AsyncMock(side_effect=Exception("SMTP error"))

    state = _state(
        candidate_id=candidate_id,
        include_email=True,
        insights=_sample_insights(),
        insights_saved=1,
    )

    with (
        patch("app.graphs.analytics_pipeline.ws_manager.broadcast", new=AsyncMock()),
        patch("app.graphs.analytics_pipeline.get_email_client", return_value=mock_email_client),
        patch("app.graphs.analytics_pipeline._db_mod.async_session_factory", return_value=mock_cm),
    ):
        result = await notify_node(state)

    # Should still complete despite email failure
    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# mark_failed_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_failed_node_broadcasts():
    from app.graphs.analytics_pipeline import mark_failed_node

    state = _state(error="insights failed")

    broadcast_mock = AsyncMock()
    with patch("app.graphs.analytics_pipeline.ws_manager.broadcast", new=broadcast_mock):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"
    broadcast_mock.assert_called_once()


@pytest.mark.asyncio
async def test_mark_failed_node_broadcast_failure_swallowed():
    from app.graphs.analytics_pipeline import mark_failed_node

    state = _state(error="something failed")

    with patch(
        "app.graphs.analytics_pipeline.ws_manager.broadcast",
        new=AsyncMock(side_effect=Exception("WS down")),
    ):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# _check_error routing
# ---------------------------------------------------------------------------


def test_check_error_routes_correctly():
    from app.graphs.analytics_pipeline import _check_error

    assert _check_error(_state(status="failed")) == "mark_failed"
    assert _check_error(_state(status="pending")) == "continue"
    assert _check_error(_state(status="completed")) == "continue"
