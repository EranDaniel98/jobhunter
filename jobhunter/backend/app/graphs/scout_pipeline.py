"""LangGraph scout pipeline - proactive company discovery via funding news.

6-node StateGraph + mark_failed:
  build_search_queries → search_news → parse_articles → score_and_filter → create_companies → notify
                                                                                              ↗
  mark_failed ─────────────────────────────────────────────────────────────────────────────→ END

Discovers companies that recently raised funding, matches against CandidateDNA,
and creates them as status="suggested" with source="scout_funding".
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing_extensions import TypedDict

from app.config import settings
from app.dependencies import get_newsapi, get_openai
from app.infrastructure import database as _db_mod
from app.infrastructure.redis_client import get_redis
from app.infrastructure.websocket_manager import ws_manager
from app.models.candidate import CandidateDNA
from app.models.company import Company
from app.models.signal import CompanySignal
from app.services.embedding_service import cosine_similarity, embed_text

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class ScoutState(TypedDict):
    candidate_id: str
    plan_tier: str
    search_queries: list[str] | None
    raw_articles: list[dict] | None
    parsed_companies: list[dict] | None
    scored_companies: list[dict] | None
    companies_created: int
    status: str  # "pending" | "completed" | "failed"
    error: str | None


# ---------------------------------------------------------------------------
# Prompts & schemas
# ---------------------------------------------------------------------------

SCOUT_QUERIES_PROMPT = (
    "You are a job market intelligence assistant. Based on the candidate's profile,"
    " generate 2-3 NewsAPI search queries to find companies that recently raised"
    " funding rounds.\n\n"
    "CANDIDATE PROFILE:\n"
    "{experience_summary}\n\n"
    "SKILLS: {skills}\n"
    "CAREER STAGE: {career_stage}\n"
    "TARGET INDUSTRIES: {industries}\n\n"
    "Generate search queries that will find recent funding news for companies relevant"
    " to this candidate's skills and experience."
    " Focus on Series A, B, C rounds and companies in related industries.\n\n"
    "Each query should be a concise NewsAPI search string"
    ' (e.g. "Series A funding fintech" or "startup raises round AI machine learning").'
)

SCOUT_QUERIES_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["queries"],
    "additionalProperties": False,
}

PARSE_ARTICLES_PROMPT = (
    "You are a company data extraction assistant. From the following news articles"
    " about funding rounds, extract structured company data.\n\n"
    "ARTICLES:\n"
    "{articles}\n\n"
    "For each unique company mentioned that raised funding, extract:\n"
    "- company_name: The company name\n"
    '- estimated_domain: Best guess at their website domain (e.g. "stripe.com")\n'
    '- funding_round: The round type (e.g. "Series A", "Series B", "Seed")\n'
    '- amount: The amount raised (e.g. "$50M", "undisclosed")\n'
    "- industry: The company's primary industry\n"
    "- description: A brief description of what the company does\n\n"
    "Only include companies where a funding round is clearly mentioned."
    " Deduplicate - each company should appear only once."
)

PARSE_ARTICLES_SCHEMA = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "estimated_domain": {"type": "string"},
                    "funding_round": {"type": "string"},
                    "amount": {"type": "string"},
                    "industry": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": [
                    "company_name",
                    "estimated_domain",
                    "funding_round",
                    "amount",
                    "industry",
                    "description",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["companies"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


async def build_search_queries_node(state: ScoutState) -> dict:
    """Load CandidateDNA, generate NewsAPI search queries via OpenAI."""
    candidate_id = uuid.UUID(state["candidate_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        dna = result.scalar_one_or_none()
        if not dna:
            return {"status": "failed", "error": "No CandidateDNA found - upload a resume first"}

        # Load candidate for target industries
        from app.models.candidate import Candidate

        cand_result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
        candidate = cand_result.scalar_one_or_none()

    skills = ", ".join(dna.strengths or [])
    industries = ", ".join((candidate.target_industries if candidate else None) or ["technology"])

    try:
        client = get_openai()
        result = await client.parse_structured(
            SCOUT_QUERIES_PROMPT.format(
                experience_summary=dna.experience_summary or "Software engineer",
                skills=skills or "general software engineering",
                career_stage=dna.career_stage or "mid",
                industries=industries,
            ),
            "",
            SCOUT_QUERIES_SCHEMA,
            model=settings.SCOUT_QUERIES_MODEL,
        )
        queries = result.get("queries", [])[:3]  # Cap at 3
    except Exception as e:
        logger.error("scout_build_queries_failed", error=str(e))
        return {"status": "failed", "error": f"Query generation failed: {e}"}

    logger.info("scout_queries_built", count=len(queries), queries=queries)
    return {"search_queries": queries}


async def search_news_node(state: ScoutState) -> dict:
    """Search NewsAPI for each query. Deduplicate by URL. Soft failure."""
    queries = state.get("search_queries") or []
    if not queries:
        return {"status": "failed", "error": "No search queries generated"}

    # Rate limit: check daily NewsAPI counter
    try:
        redis = get_redis()
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        count_key = f"newsapi:daily:{today}"
        current = await redis.get(count_key)
        if current and int(current) > 90:
            logger.warning("scout_newsapi_rate_limit_reached", daily_count=int(current))
            return {"raw_articles": [], "status": "pending"}
    except Exception as e:
        logger.warning("scout_redis_rate_check_failed", error=str(e))

    newsapi = get_newsapi()
    from_date = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
    to_date = datetime.now(UTC).strftime("%Y-%m-%d")

    all_articles = []
    seen_urls = set()

    for query in queries:
        try:
            articles = await newsapi.search_articles(
                query=query,
                from_date=from_date,
                to_date=to_date,
                page_size=50,
            )
            # Track daily usage
            try:
                redis = get_redis()
                today = datetime.now(UTC).strftime("%Y-%m-%d")
                pipe = redis.pipeline()
                pipe.incr(f"newsapi:daily:{today}")
                pipe.expire(f"newsapi:daily:{today}", 86400)
                await pipe.execute()
            except Exception as e:
                logger.warning("scout_redis_usage_tracking_failed", error=str(e))

            for article in articles:
                url = article.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_articles.append(article)
        except Exception as e:
            logger.warning("scout_search_query_failed", query=query, error=str(e))

    # Also search DuckDuckGo for broader coverage (best-effort)
    try:
        import asyncio

        from duckduckgo_search import DDGS

        ddg_queries = [f"{q} hiring" for q in queries[:2]]

        def _ddg_search_sync() -> list[dict]:
            collected = []
            with DDGS() as ddgs:
                for query in ddg_queries:
                    try:
                        results = ddgs.text(query, max_results=5)
                        for r in results:
                            url = r.get("href", "")
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                collected.append(
                                    {
                                        "title": r.get("title", ""),
                                        "description": r.get("body", ""),
                                        "url": url,
                                        "source": {"name": "DuckDuckGo"},
                                    }
                                )
                    except Exception:
                        continue
            return collected

        ddg_results = await asyncio.to_thread(_ddg_search_sync)
        all_articles.extend(ddg_results)
        if ddg_results:
            logger.info("scout_ddg_searched", ddg_articles=len(ddg_results))
    except Exception as e:
        logger.warning("scout_ddg_search_failed", error=str(e))

    logger.info("scout_news_searched", total_articles=len(all_articles))

    if not all_articles:
        # Empty results - not a failure, just nothing found
        return {"raw_articles": [], "companies_created": 0, "status": "completed"}

    return {"raw_articles": all_articles}


async def parse_articles_node(state: ScoutState) -> dict:
    """Parse articles into structured company data via OpenAI."""
    articles = state.get("raw_articles") or []
    if not articles:
        return {"parsed_companies": [], "companies_created": 0, "status": "completed"}

    # Format articles for prompt
    articles_text = "\n\n".join(
        f"Title: {a.get('title', 'N/A')}\n"
        f"Description: {a.get('description', 'N/A')}\n"
        f"Source: {a.get('source', {}).get('name', 'N/A')}\n"
        f"URL: {a.get('url', 'N/A')}\n"
        f"Published: {a.get('publishedAt', 'N/A')}"
        for a in articles[:50]  # Cap at 50 articles for prompt size
    )

    try:
        client = get_openai()
        result = await client.parse_structured(
            PARSE_ARTICLES_PROMPT.format(articles=articles_text),
            "",
            PARSE_ARTICLES_SCHEMA,
            model=settings.SCOUT_PARSE_MODEL,
        )
        companies = result.get("companies", [])
    except Exception as e:
        logger.error("scout_parse_articles_failed", error=str(e))
        return {"status": "failed", "error": f"Article parsing failed: {e}"}

    logger.info("scout_articles_parsed", companies_found=len(companies))

    if not companies:
        return {"parsed_companies": [], "companies_created": 0, "status": "completed"}

    # Attach source URLs from articles (best effort match by company name)
    article_urls: dict[str, list[str]] = {}
    for a in articles:
        title = (a.get("title") or "").lower()
        desc = (a.get("description") or "").lower()
        url = a.get("url", "")
        for c in companies:
            name = c["company_name"].lower()
            if name in title or name in desc:
                article_urls.setdefault(c["company_name"], []).append(url)

    for c in companies:
        urls = article_urls.get(c["company_name"], [])
        c["source_url"] = urls[0] if urls else None

    return {"parsed_companies": companies}


async def score_and_filter_node(state: ScoutState) -> dict:
    """Score each company against CandidateDNA, filter by fit_score >= 0.55."""
    parsed = state.get("parsed_companies") or []
    if not parsed:
        return {"scored_companies": [], "companies_created": 0, "status": "completed"}

    candidate_id = uuid.UUID(state["candidate_id"])

    async with _db_mod.async_session_factory() as db:
        # Load DNA embedding
        result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        dna = result.scalar_one_or_none()
        if not dna or dna.embedding is None:
            return {"status": "failed", "error": "CandidateDNA embedding not found"}

        candidate_embedding = [float(x) for x in dna.embedding]

        # Get existing domains for this candidate
        existing_result = await db.execute(select(Company.domain).where(Company.candidate_id == candidate_id))
        existing_domains = {row[0] for row in existing_result.all()}

    scored = []
    failed_count = 0
    for company in parsed:
        domain = company.get("estimated_domain", "").strip().lower()
        if not domain or domain in existing_domains:
            continue

        # Compute embedding and fit score
        company_text = f"{company['company_name']} {company['description']} {company['industry']}"
        try:
            embedding = await embed_text(company_text)
            fit_score = cosine_similarity(candidate_embedding, embedding)
        except Exception as e:
            failed_count += 1
            logger.warning("scout_score_failed", company=company["company_name"], error=str(e))
            continue

        if fit_score >= 0.55:
            company["domain"] = domain
            company["embedding"] = embedding
            company["fit_score"] = fit_score
            scored.append(company)
            existing_domains.add(domain)  # Prevent duplicates within batch

    if failed_count > 0:
        logger.error("scout_scoring_partial_failure", failed=failed_count, total=len(parsed))
    logger.info("scout_scored_and_filtered", input=len(parsed), output=len(scored), failed=failed_count)
    return {"scored_companies": scored}


async def create_companies_node(state: ScoutState) -> dict:
    """Create Company + CompanySignal records for each scoring company."""
    scored = state.get("scored_companies") or []
    if not scored:
        return {"companies_created": 0}

    candidate_id = uuid.UUID(state["candidate_id"])
    created = 0

    for c in scored:
        try:
            async with _db_mod.async_session_factory() as db:
                company = Company(
                    id=uuid.uuid4(),
                    candidate_id=candidate_id,
                    name=c["company_name"],
                    domain=c["domain"],
                    industry=c.get("industry"),
                    description=c.get("description"),
                    funding_stage=c.get("funding_round"),
                    fit_score=c.get("fit_score"),
                    embedding=c.get("embedding"),
                    status="suggested",
                    research_status="pending",
                    source="scout_funding",
                )
                db.add(company)
                await db.flush()

                signal = CompanySignal(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    candidate_id=candidate_id,
                    signal_type="funding_round",
                    title=f"{c['company_name']} raised {c.get('funding_round', 'funding')}",
                    description=c.get("description"),
                    source_url=c.get("source_url"),
                    signal_strength=c.get("fit_score"),
                    detected_at=datetime.now(UTC),
                    metadata_={
                        "funding_round": c.get("funding_round"),
                        "amount": c.get("amount"),
                    },
                )
                db.add(signal)
                await db.commit()
                created += 1
        except IntegrityError:
            logger.info("scout_company_duplicate", domain=c.get("domain"))
            continue
        except Exception as e:
            logger.error("scout_company_create_failed", domain=c.get("domain"), error=str(e))
            continue

    logger.info("scout_companies_created", count=created)
    return {"companies_created": created}


async def notify_node(state: ScoutState) -> dict:
    """Broadcast scout completion via WebSocket."""
    candidate_id = state["candidate_id"]
    companies_created = state.get("companies_created", 0)

    await ws_manager.broadcast(
        str(candidate_id),
        "scout_completed",
        {"companies_found": companies_created, "status": "completed"},
    )

    logger.info("scout_notify_done", candidate_id=candidate_id, companies_found=companies_created)
    return {"status": "completed"}


async def mark_failed_node(state: ScoutState) -> dict:
    """Log error and broadcast failure notification."""
    candidate_id = state["candidate_id"]
    error = state.get("error", "unknown error")

    await ws_manager.broadcast(
        str(candidate_id),
        "scout_failed",
        {"error": error},
    )

    logger.error("scout_mark_failed", candidate_id=candidate_id, error=error)
    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def _check_error(state: ScoutState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


def _check_empty_or_error(state: ScoutState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    if state.get("status") == "completed":
        return "notify"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_scout_pipeline() -> StateGraph:
    """Build (but don't compile) the scout graph."""
    builder = StateGraph(ScoutState)

    builder.add_node("build_search_queries", build_search_queries_node)
    builder.add_node("search_news", search_news_node)
    builder.add_node("parse_articles", parse_articles_node)
    builder.add_node("score_and_filter", score_and_filter_node)
    builder.add_node("create_companies", create_companies_node)
    builder.add_node("notify", notify_node)
    builder.add_node("mark_failed", mark_failed_node)

    # START → build_search_queries
    builder.add_edge(START, "build_search_queries")

    # build_search_queries → search_news | mark_failed
    builder.add_conditional_edges(
        "build_search_queries",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "search_news"},
    )

    # search_news → parse_articles | notify (empty) | mark_failed
    builder.add_conditional_edges(
        "search_news",
        _check_empty_or_error,
        {"mark_failed": "mark_failed", "notify": "notify", "continue": "parse_articles"},
    )

    # parse_articles → score_and_filter | notify (empty) | mark_failed
    builder.add_conditional_edges(
        "parse_articles",
        _check_empty_or_error,
        {"mark_failed": "mark_failed", "notify": "notify", "continue": "score_and_filter"},
    )

    # score_and_filter → create_companies | mark_failed
    builder.add_conditional_edges(
        "score_and_filter",
        _check_empty_or_error,
        {"mark_failed": "mark_failed", "notify": "notify", "continue": "create_companies"},
    )

    # create_companies → notify | mark_failed
    builder.add_conditional_edges(
        "create_companies",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "notify"},
    )

    builder.add_edge("notify", END)
    builder.add_edge("mark_failed", END)

    return builder


# Module-level builder (reusable)
_builder = build_scout_pipeline()


# ---------------------------------------------------------------------------
# Graph accessors
# ---------------------------------------------------------------------------


def get_scout_pipeline(checkpointer=None):
    """Production: compiled graph with PostgreSQL checkpointer."""
    from app.graphs.resume_pipeline import _checkpointer as shared

    return _builder.compile(checkpointer=checkpointer or shared)


def get_scout_pipeline_no_checkpointer():
    """Testing: compiled graph without checkpointer."""
    return _builder.compile()
