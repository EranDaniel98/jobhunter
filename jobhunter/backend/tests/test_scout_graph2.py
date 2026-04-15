"""Additional unit tests for LangGraph scout pipeline nodes (error/edge paths)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**overrides):
    base = {
        "candidate_id": str(uuid.uuid4()),
        "plan_tier": "free",
        "parsed_companies": None,
        "scored_companies": None,
        "companies_created": 0,
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


# ---------------------------------------------------------------------------
# score_and_filter_node edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_and_filter_empty_input():
    from app.graphs.scout_pipeline import score_and_filter_node

    state = _state(parsed_companies=[])
    result = await score_and_filter_node(state)

    assert result["scored_companies"] == []
    assert result["companies_created"] == 0
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_score_and_filter_no_dna_embedding():
    from app.graphs.scout_pipeline import score_and_filter_node

    mock_dna = MagicMock()
    mock_dna.embedding = None

    mock_cm, mock_session = _make_mock_db_session()

    def side_effect_execute(*args, **kwargs):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_dna)
        mock_result.all = MagicMock(return_value=[])
        return mock_result

    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    state = _state(
        parsed_companies=[
            {
                "company_name": "Acme",
                "estimated_domain": "acme.com",
                "industry": "Tech",
                "description": "A great company",
                "funding_round": "Series A",
                "amount": "$10M",
            }
        ]
    )

    with patch("app.graphs.scout_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await score_and_filter_node(state)

    assert result["status"] == "failed"
    assert "embedding not found" in result["error"]


@pytest.mark.asyncio
async def test_score_and_filter_skips_existing_domains():
    """Companies whose domain already exists in DB are skipped."""
    from app.graphs.scout_pipeline import score_and_filter_node

    mock_dna = MagicMock()
    mock_dna.embedding = [0.1] * 1536

    mock_cm, mock_session = _make_mock_db_session()

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_dna)
        else:
            mock_result.all = MagicMock(return_value=[("acme.com",)])
        return mock_result

    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    state = _state(
        parsed_companies=[
            {
                "company_name": "Acme",
                "estimated_domain": "acme.com",
                "industry": "Tech",
                "description": "A great company",
                "funding_round": "Series A",
                "amount": "$10M",
            }
        ]
    )

    with patch("app.graphs.scout_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await score_and_filter_node(state)

    assert result["scored_companies"] == []


@pytest.mark.asyncio
async def test_score_and_filter_embed_failure_skips_company():
    """Embedding failure for a company logs warning and skips it."""
    from app.graphs.scout_pipeline import score_and_filter_node

    mock_dna = MagicMock()
    mock_dna.embedding = [0.1] * 1536

    mock_cm, mock_session = _make_mock_db_session()

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_dna)
        else:
            mock_result.all = MagicMock(return_value=[])
        return mock_result

    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    # parsed_companies WITHOUT _precomputed_embedding → forces embed_text() call
    state = _state(
        parsed_companies=[
            {
                "company_name": "Acme",
                "estimated_domain": "acme.com",
                "industry": "Tech",
                "description": "A great company",
                "funding_round": "Series A",
                "amount": "$10M",
            }
        ]
    )

    with (
        patch("app.graphs.scout_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.scout_pipeline.embed_text", AsyncMock(side_effect=Exception("embed fail"))),
    ):
        result = await score_and_filter_node(state)

    assert result["scored_companies"] == []


# ---------------------------------------------------------------------------
# create_companies_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_companies_node_empty_input():
    from app.graphs.scout_pipeline import create_companies_node

    state = _state(scored_companies=[])
    result = await create_companies_node(state)

    assert result["companies_created"] == 0


# ---------------------------------------------------------------------------
# notify_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_node_broadcasts():
    from app.graphs.scout_pipeline import notify_node

    candidate_id = str(uuid.uuid4())
    state = _state(candidate_id=candidate_id, companies_created=5)

    broadcast_mock = AsyncMock()
    with patch("app.graphs.scout_pipeline.ws_manager.broadcast", new=broadcast_mock):
        result = await notify_node(state)

    assert result["status"] == "completed"
    broadcast_mock.assert_called_once()


# ---------------------------------------------------------------------------
# mark_failed_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_failed_node():
    from app.graphs.scout_pipeline import mark_failed_node

    state = _state(error="Something went wrong")
    broadcast_mock = AsyncMock()
    with patch("app.graphs.scout_pipeline.ws_manager.broadcast", new=broadcast_mock):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"
    broadcast_mock.assert_called_once()


# ---------------------------------------------------------------------------
# _check_error / _check_empty_or_error routing
# ---------------------------------------------------------------------------


def test_check_error_routes_correctly():
    from app.graphs.scout_pipeline import _check_error

    assert _check_error(_state(status="failed")) == "mark_failed"
    assert _check_error(_state(status="pending")) == "continue"


def test_check_empty_or_error_routes():
    from app.graphs.scout_pipeline import _check_empty_or_error

    assert _check_empty_or_error(_state(status="failed")) == "mark_failed"
    assert _check_empty_or_error(_state(status="completed")) == "notify"
    assert _check_empty_or_error(_state(status="pending")) == "continue"
