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
        "search_queries": None,
        "raw_articles": None,
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
# build_search_queries_node error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_queries_no_dna():
    from app.graphs.scout_pipeline import build_search_queries_node

    mock_cm, mock_session = _make_mock_db_session()

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    state = _state()

    with patch("app.graphs.scout_pipeline._db_mod.async_session_factory", return_value=mock_cm):
        result = await build_search_queries_node(state)

    assert result["status"] == "failed"
    assert "No CandidateDNA" in result["error"]


@pytest.mark.asyncio
async def test_build_queries_openai_failure():
    from app.graphs.scout_pipeline import build_search_queries_node

    mock_dna = MagicMock()
    mock_dna.experience_summary = "5y backend"
    mock_dna.strengths = ["Python", "FastAPI"]
    mock_dna.career_stage = "mid"

    mock_candidate = MagicMock()
    mock_candidate.target_industries = ["technology"]

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_dna)
        else:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_candidate)
        return mock_result

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("OpenAI timeout"))

    state = _state()

    with (
        patch("app.graphs.scout_pipeline._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.scout_pipeline.get_openai", return_value=mock_client),
    ):
        result = await build_search_queries_node(state)

    assert result["status"] == "failed"
    assert "Query generation failed" in result["error"]


# ---------------------------------------------------------------------------
# search_news_node edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_news_node_no_queries():
    from app.graphs.scout_pipeline import search_news_node

    state = _state(search_queries=[])
    result = await search_news_node(state)

    assert result["status"] == "failed"
    assert "No search queries" in result["error"]


@pytest.mark.asyncio
async def test_search_news_node_rate_limit_reached():
    """Daily rate limit > 90 → return empty articles with status=pending."""
    from app.graphs.scout_pipeline import search_news_node

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=b"95")

    state = _state(search_queries=["Series A funding"])

    with patch("app.graphs.scout_pipeline.get_redis", return_value=mock_redis):
        result = await search_news_node(state)

    assert result["raw_articles"] == []
    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_search_news_node_redis_failure_continues():
    """Redis failure during rate check should be swallowed, pipeline continues."""
    from app.graphs.scout_pipeline import search_news_node

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))

    mock_newsapi = MagicMock()
    mock_newsapi.search_articles = AsyncMock(return_value=[])

    state = _state(search_queries=["Series A funding"])

    with (
        patch("app.graphs.scout_pipeline.get_redis", return_value=mock_redis),
        patch("app.graphs.scout_pipeline.get_newsapi", return_value=mock_newsapi),
    ):
        result = await search_news_node(state)

    # Empty articles → status=completed
    assert result["status"] == "completed"
    assert result["raw_articles"] == []


@pytest.mark.asyncio
async def test_search_news_node_query_failure_continues():
    """Individual query failure should not stop other queries."""
    from app.graphs.scout_pipeline import search_news_node

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.pipeline = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.incr = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[1, True])
    mock_redis.pipeline.return_value = mock_pipe

    mock_newsapi = MagicMock()
    mock_newsapi.search_articles = AsyncMock(side_effect=Exception("NewsAPI failed"))

    state = _state(search_queries=["query1", "query2"])

    with (
        patch("app.graphs.scout_pipeline.get_redis", return_value=mock_redis),
        patch("app.graphs.scout_pipeline.get_newsapi", return_value=mock_newsapi),
    ):
        result = await search_news_node(state)

    # All queries failed → empty → completed
    assert result["status"] == "completed"
    assert result["raw_articles"] == []


# ---------------------------------------------------------------------------
# parse_articles_node edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_articles_node_empty_input():
    from app.graphs.scout_pipeline import parse_articles_node

    state = _state(raw_articles=[])
    result = await parse_articles_node(state)

    assert result["parsed_companies"] == []
    assert result["companies_created"] == 0
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_parse_articles_node_openai_failure():
    from app.graphs.scout_pipeline import parse_articles_node

    articles = [
        {
            "title": "Acme raises Series A",
            "description": "Acme raised $10M",
            "url": "https://example.com/1",
            "publishedAt": "2026-01-01",
            "source": {"name": "TechCrunch"},
        }
    ]

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("API error"))

    state = _state(raw_articles=articles)

    with patch("app.graphs.scout_pipeline.get_openai", return_value=mock_client):
        result = await parse_articles_node(state)

    assert result["status"] == "failed"
    assert "Article parsing failed" in result["error"]


@pytest.mark.asyncio
async def test_parse_articles_node_no_companies_found():
    """OpenAI returns empty companies list → completed."""
    from app.graphs.scout_pipeline import parse_articles_node

    articles = [
        {
            "title": "No funding here",
            "description": "Just some news",
            "url": "https://example.com/2",
            "publishedAt": "2026-01-01",
            "source": {"name": "Reuters"},
        }
    ]

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(return_value={"companies": []})

    state = _state(raw_articles=articles)

    with patch("app.graphs.scout_pipeline.get_openai", return_value=mock_client):
        result = await parse_articles_node(state)

    assert result["parsed_companies"] == []
    assert result["companies_created"] == 0
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_parse_articles_attaches_source_urls():
    """Source URLs are matched and attached to companies."""
    from app.graphs.scout_pipeline import parse_articles_node

    articles = [
        {
            "title": "Stripe raises Series C",
            "description": "Stripe the payments company raised $500M",
            "url": "https://techcrunch.com/stripe-series-c",
            "publishedAt": "2026-01-01",
            "source": {"name": "TechCrunch"},
        }
    ]

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(
        return_value={
            "companies": [
                {
                    "company_name": "Stripe",
                    "estimated_domain": "stripe.com",
                    "funding_round": "Series C",
                    "amount": "$500M",
                    "industry": "Fintech",
                    "description": "Payments infrastructure",
                }
            ]
        }
    )

    state = _state(raw_articles=articles)

    with patch("app.graphs.scout_pipeline.get_openai", return_value=mock_client):
        result = await parse_articles_node(state)

    assert len(result["parsed_companies"]) == 1
    # The URL should be attached (company name "stripe" appears in title/description)
    company = result["parsed_companies"][0]
    assert company.get("source_url") == "https://techcrunch.com/stripe-series-c"


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

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
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

    existing_row = MagicMock()
    existing_row.__iter__ = MagicMock(return_value=iter([("acme.com",)]))

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_dna)
        else:
            # Return existing domains
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

    # Domain already exists → skipped → empty scored list
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

    # Company was skipped due to embed failure
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
