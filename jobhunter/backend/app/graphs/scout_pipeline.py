"""LangGraph scout pipeline - proactive company discovery.

After the cost-reduction refactor, the NewsAPI fetch + LLM article parsing
happens ONCE per day in a shared ingest job (see app.services.news_ingest_service).
This per-candidate pipeline simply reads the shared funding_signals pool and
scores each entry against the candidate's DNA embedding.

Pipeline (4 nodes + mark_failed):
  load_shared_signals → score_and_filter → create_companies → notify
                                                                 ↗
  mark_failed ───────────────────────────────────────────────→ END
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing_extensions import TypedDict

from app.infrastructure import database as _db_mod
from app.infrastructure.websocket_manager import ws_manager
from app.models.candidate import CandidateDNA
from app.models.company import Company
from app.models.funding_signal import FundingSignal
from app.models.signal import CompanySignal
from app.services.embedding_service import cosine_similarity, embed_text

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class ScoutState(TypedDict):
    candidate_id: str
    plan_tier: str
    parsed_companies: list[dict] | None
    scored_companies: list[dict] | None
    companies_created: int
    status: str  # "pending" | "completed" | "failed"
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


async def load_shared_signals_node(state: ScoutState) -> dict:
    """Read recent FundingSignal rows from the shared pool. These were populated
    once daily by run_daily_news_ingest; this node is cheap and per-candidate."""
    cutoff = datetime.now(UTC) - timedelta(days=7)

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(
            select(FundingSignal)
            .where(FundingSignal.published_at >= cutoff)
            .where(FundingSignal.company_name.is_not(None))
            .order_by(FundingSignal.published_at.desc())
            .limit(200)
        )
        sigs = result.scalars().all()

    parsed = [
        {
            "company_name": s.company_name,
            "estimated_domain": (s.estimated_domain or "").strip().lower(),
            "funding_round": s.funding_round,
            "amount": s.amount,
            "industry": s.industry,
            "description": s.description,
            "source_url": s.source_url,
            "_precomputed_embedding": s.embedding,
        }
        for s in sigs
        if s.company_name
    ]
    logger.info("scout_loaded_shared_signals", count=len(parsed))
    return {"parsed_companies": parsed}


async def score_and_filter_node(state: ScoutState) -> dict:
    """Score each company against CandidateDNA, filter by
    fit_score >= settings.SCOUT_FIT_THRESHOLD. Reuses precomputed embeddings
    from the shared pool when available."""
    from app.config import settings

    parsed = state.get("parsed_companies") or []
    if not parsed:
        return {"scored_companies": [], "companies_created": 0, "status": "completed"}

    candidate_id = uuid.UUID(state["candidate_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        dna = result.scalar_one_or_none()
        if not dna or dna.embedding is None:
            return {"status": "failed", "error": "CandidateDNA embedding not found"}

        candidate_embedding = [float(x) for x in dna.embedding]

        existing_result = await db.execute(select(Company.domain).where(Company.candidate_id == candidate_id))
        existing_domains = {row[0] for row in existing_result.all()}

    scored: list[dict] = []
    failed_count = 0
    for company in parsed:
        domain = company.get("estimated_domain", "").strip().lower()
        if not domain or domain in existing_domains:
            continue

        embedding = company.get("_precomputed_embedding")
        try:
            if embedding is None:
                text = f"{company['company_name']} {company.get('description', '')} {company.get('industry', '')}"
                embedding = await embed_text(text)
            fit_score = cosine_similarity(candidate_embedding, embedding)
        except Exception as e:
            failed_count += 1
            logger.warning("scout_score_failed", company=company["company_name"], error=str(e))
            continue

        if fit_score >= settings.SCOUT_FIT_THRESHOLD:
            company["domain"] = domain
            company["embedding"] = embedding
            company["fit_score"] = fit_score
            scored.append(company)
            existing_domains.add(domain)

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


def _check_empty_or_error(state: ScoutState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    if state.get("status") == "completed":
        return "notify"
    return "continue"


def _check_error(state: ScoutState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_scout_pipeline() -> StateGraph:
    """Build (but don't compile) the scout graph."""
    builder = StateGraph(ScoutState)

    builder.add_node("load_shared_signals", load_shared_signals_node)
    builder.add_node("score_and_filter", score_and_filter_node)
    builder.add_node("create_companies", create_companies_node)
    builder.add_node("notify", notify_node)
    builder.add_node("mark_failed", mark_failed_node)

    builder.add_edge(START, "load_shared_signals")

    builder.add_conditional_edges(
        "load_shared_signals",
        _check_empty_or_error,
        {"mark_failed": "mark_failed", "notify": "notify", "continue": "score_and_filter"},
    )

    builder.add_conditional_edges(
        "score_and_filter",
        _check_empty_or_error,
        {"mark_failed": "mark_failed", "notify": "notify", "continue": "create_companies"},
    )

    builder.add_conditional_edges(
        "create_companies",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "notify"},
    )

    builder.add_edge("notify", END)
    builder.add_edge("mark_failed", END)

    return builder


_builder = build_scout_pipeline()


def get_scout_pipeline(checkpointer=None):
    """Production: compiled graph with PostgreSQL checkpointer."""
    from app.graphs.resume_pipeline import _checkpointer as shared

    return _builder.compile(checkpointer=checkpointer or shared)


def get_scout_pipeline_no_checkpointer():
    """Testing: compiled graph without checkpointer."""
    return _builder.compile()
