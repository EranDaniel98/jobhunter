"""Additional unit tests for LangGraph company research pipeline nodes (error/edge paths)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**overrides):
    base = {
        "company_id": str(uuid.uuid4()),
        "candidate_id": str(uuid.uuid4()),
        "plan_tier": "free",
        "hunter_data": None,
        "web_context": None,
        "dossier_data": None,
        "contacts_created": 0,
        "embedding_set": False,
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
# enrich_company_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_company_node_not_found():
    from app.graphs.company_research import enrich_company_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state()

    with patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm):
        result = await enrich_company_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_enrich_company_node_rate_limit_error():
    from app.graphs.company_research import enrich_company_node

    mock_company = MagicMock()
    mock_company.domain = "acme.com"
    mock_company.industry = None
    mock_company.size_range = None
    mock_company.location_hq = None
    mock_company.description = None
    mock_company.tech_stack = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_company))

    mock_hunter = MagicMock()
    mock_hunter.domain_search = AsyncMock(side_effect=Exception("rate limit exceeded"))

    state = _state()

    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.company_research.get_hunter", return_value=mock_hunter),
    ):
        result = await enrich_company_node(state)

    assert result["status"] == "failed"
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_enrich_company_node_quota_error():
    from app.graphs.company_research import enrich_company_node

    mock_company = MagicMock()
    mock_company.domain = "acme.com"
    mock_company.industry = None
    mock_company.size_range = None
    mock_company.location_hq = None
    mock_company.description = None
    mock_company.tech_stack = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_company))

    mock_hunter = MagicMock()
    mock_hunter.domain_search = AsyncMock(side_effect=Exception("quota exhausted for credits"))

    state = _state()

    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.company_research.get_hunter", return_value=mock_hunter),
    ):
        result = await enrich_company_node(state)

    assert result["status"] == "failed"
    assert "quota" in result["error"].lower()


@pytest.mark.asyncio
async def test_enrich_company_node_timeout_error():
    from app.graphs.company_research import enrich_company_node

    mock_company = MagicMock()
    mock_company.domain = "acme.com"
    mock_company.industry = None
    mock_company.size_range = None
    mock_company.location_hq = None
    mock_company.description = None
    mock_company.tech_stack = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_company))

    mock_hunter = MagicMock()
    mock_hunter.domain_search = AsyncMock(side_effect=Exception("connection timeout"))

    state = _state()

    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.company_research.get_hunter", return_value=mock_hunter),
    ):
        result = await enrich_company_node(state)

    assert result["status"] == "failed"
    assert "unavailable" in result["error"].lower()


@pytest.mark.asyncio
async def test_enrich_company_node_generic_error():
    from app.graphs.company_research import enrich_company_node

    mock_company = MagicMock()
    mock_company.domain = "acme.com"
    mock_company.industry = None
    mock_company.size_range = None
    mock_company.location_hq = None
    mock_company.description = None
    mock_company.tech_stack = None

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_company))

    mock_hunter = MagicMock()
    mock_hunter.domain_search = AsyncMock(side_effect=Exception("Something unexpected"))

    state = _state()

    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.company_research.get_hunter", return_value=mock_hunter),
    ):
        result = await enrich_company_node(state)

    assert result["status"] == "failed"
    assert "enrichment failed" in result["error"].lower()


# ---------------------------------------------------------------------------
# web_search_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_node_company_not_found_graceful():
    """Company not found in DB still returns empty web_context gracefully."""
    from app.graphs.company_research import web_search_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state()

    with patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm):
        result = await web_search_node(state)

    assert result == {"web_context": ""}


@pytest.mark.asyncio
async def test_web_search_node_ddgs_exception_graceful():
    """DuckDuckGo import failure results in empty web_context, not a pipeline failure."""
    from app.graphs.company_research import web_search_node

    state = _state()

    with patch("app.graphs.company_research._db_mod.async_session_factory") as mock_factory:
        # Trigger outer exception by making factory raise
        mock_factory.side_effect = Exception("DDGS unavailable")
        result = await web_search_node(state)

    # Graceful degradation: returns empty string, does not set status=failed
    assert "web_context" in result
    assert result["web_context"] == ""


# ---------------------------------------------------------------------------
# generate_dossier_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_dossier_node_company_not_found():
    from app.graphs.company_research import generate_dossier_node

    mock_cm, mock_session = _make_mock_db_session()

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    state = _state()

    with patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm):
        result = await generate_dossier_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_generate_dossier_node_openai_failure():
    from app.graphs.company_research import generate_dossier_node

    mock_company = MagicMock()
    mock_company.id = uuid.uuid4()
    mock_company.name = "Acme"
    mock_company.domain = "acme.com"
    mock_company.industry = "Tech"
    mock_company.size_range = "50-200"
    mock_company.location_hq = "NY"
    mock_company.description = "A tech company"
    mock_company.tech_stack = ["Python"]

    mock_dna = MagicMock()
    mock_dna.experience_summary = "5y backend"

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_company)
        else:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_dna)
        return mock_result

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("OpenAI failure"))

    state = _state(hunter_data={}, web_context="Some context")

    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.company_research.get_openai", return_value=mock_client),
        patch("app.graphs.company_research.get_cached_dossier", AsyncMock(return_value=None)),
        patch("app.graphs.company_research.acquire_stampede_lock", AsyncMock(return_value=True)),
        patch("app.graphs.company_research.release_stampede_lock", AsyncMock()),
    ):
        result = await generate_dossier_node(state)

    assert result["status"] == "failed"
    assert "Dossier generation failed" in result["error"]


# ---------------------------------------------------------------------------
# embed_company_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_company_node_not_found():
    from app.graphs.company_research import embed_company_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state()

    with patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm):
        result = await embed_company_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_embed_company_node_embed_failure():
    from app.graphs.company_research import embed_company_node

    mock_company = MagicMock()
    mock_company.name = "Acme"
    mock_company.description = "A company"
    mock_company.industry = "Tech"

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_company))

    state = _state()

    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.company_research.embed_text", AsyncMock(side_effect=Exception("embed error"))),
    ):
        result = await embed_company_node(state)

    assert result["status"] == "failed"
    assert "Embedding failed" in result["error"]


# ---------------------------------------------------------------------------
# create_contacts_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_contacts_node_failure():
    from app.graphs.company_research import create_contacts_node

    mock_cm, mock_session = _make_mock_db_session()

    mock_company = MagicMock()
    mock_company.size_range = "50-200"

    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_company))

    state = _state(hunter_data={"emails": []})

    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch(
            "app.graphs.company_research._create_contacts_from_hunter",
            AsyncMock(side_effect=Exception("DB error")),
        ),
    ):
        result = await create_contacts_node(state)

    assert result["status"] == "failed"
    assert "Contact creation failed" in result["error"]


# ---------------------------------------------------------------------------
# notify_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_node_company_not_found_still_completes():
    from app.graphs.company_research import notify_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state(contacts_created=3)

    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.company_research.ws_manager.broadcast", new=AsyncMock()),
    ):
        result = await notify_node(state)

    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# mark_failed_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_failed_node_broadcasts_failure():
    from app.graphs.company_research import mark_failed_node

    mock_company = MagicMock()

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_company))

    state = _state(error="Hunter API down")

    broadcast_mock = AsyncMock()
    with (
        patch("app.graphs.company_research._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.company_research.ws_manager.broadcast", new=broadcast_mock),
    ):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"
    broadcast_mock.assert_called_once()


# ---------------------------------------------------------------------------
# _check_error routing
# ---------------------------------------------------------------------------


def test_check_error_routes_correctly():
    from app.graphs.company_research import _check_error

    assert _check_error(_state(status="failed")) == "mark_failed"
    assert _check_error(_state(status="pending")) == "continue"
    assert _check_error(_state(status="completed")) == "continue"
