"""LangGraph company research pipeline.

Replaces the monolithic research_company() with a 7-node StateGraph:
  enrich_company -> web_search -> generate_dossier -> create_contacts
  -> embed_company -> notify -> END

Each node gets its own DB session and is independently checkpointed.
On failure, the graph routes to mark_failed -> END.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime

import structlog
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from typing_extensions import TypedDict

from app.dependencies import get_hunter, get_openai
from app.infrastructure import database as _db_mod
from app.infrastructure.dossier_cache import (
    _compute_input_hash,
    acquire_stampede_lock,
    cache_dossier,
    get_cached_dossier,
    release_stampede_lock,
    wait_for_cache,
)
from app.infrastructure.websocket_manager import ws_manager
from app.models.candidate import CandidateDNA
from app.models.company import Company, CompanyDossier
from app.models.enums import ResearchStatus
from app.services.company_service import (
    DOSSIER_GENERIC_PROMPT,
    DOSSIER_GENERIC_SCHEMA,
    DOSSIER_PERSONAL_PROMPT,
    DOSSIER_PERSONAL_SCHEMA,
    _create_contacts_from_hunter,
)
from app.services.embedding_service import embed_text

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class CompanyResearchState(TypedDict):
    company_id: str
    candidate_id: str
    plan_tier: str
    hunter_data: dict | None
    web_context: str | None
    dossier_data: dict | None
    contacts_created: int
    embedding_set: bool
    status: str  # "pending" | "completed" | "failed"
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


async def enrich_company_node(state: CompanyResearchState) -> dict:
    """Load Company from DB, call Hunter domain_search, update empty fields."""
    company_id = uuid.UUID(state["company_id"])
    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"status": "failed", "error": f"Company {company_id} not found"}

        try:
            hunter = get_hunter()
            hunter_data = await hunter.domain_search(company.domain)

            # Update empty fields from Hunter data
            # Hunter.io may nest org data under "organization" key (as a dict)
            # or return it as a plain string (company name). Fall back to top-level dict.
            raw_org = hunter_data.get("organization")
            org = raw_org if isinstance(raw_org, dict) else hunter_data
            if not company.industry and (org.get("industry") or hunter_data.get("industry")):
                company.industry = org.get("industry") or hunter_data.get("industry")
            if not company.size_range and (org.get("size") or hunter_data.get("size")):
                company.size_range = org.get("size") or hunter_data.get("size")
            if not company.location_hq:
                # Try top-level "location" first, then construct from city/state/country
                location = hunter_data.get("location") or org.get("location")
                if not location:
                    parts = [
                        org.get("city") or hunter_data.get("city"),
                        org.get("state") or hunter_data.get("state"),
                        org.get("country") or hunter_data.get("country"),
                    ]
                    location = ", ".join(p for p in parts if p) or None
                if location:
                    company.location_hq = location
            if not company.description and (org.get("description") or hunter_data.get("description")):
                company.description = org.get("description") or hunter_data.get("description")
            if not company.tech_stack and (org.get("technologies") or hunter_data.get("technologies")):
                company.tech_stack = org.get("technologies") or hunter_data.get("technologies")

            company.research_status = ResearchStatus.IN_PROGRESS
            await db.commit()
        except Exception as e:
            logger.error("graph_enrich_company_failed", company_id=str(company_id), error=str(e))
            error_str = str(e).lower()
            if "rate" in error_str and "limit" in error_str:
                error_msg = "Hunter.io rate limit reached. Please try again later."
            elif "quota" in error_str or "credit" in error_str:
                error_msg = "Hunter.io quota exhausted for today."
            elif "timeout" in error_str or "connect" in error_str or "unreachable" in error_str:
                error_msg = "Hunter.io is currently unavailable. Please try again later."
            else:
                error_msg = f"Company enrichment failed: {e}"
            return {"status": "failed", "error": error_msg}

    logger.info("graph_enrich_company_done", company_id=str(company_id))
    return {"hunter_data": hunter_data}


async def web_search_node(state: CompanyResearchState) -> dict:
    """Search DuckDuckGo for company context. Graceful degradation on any error."""
    company_id = uuid.UUID(state["company_id"])

    try:
        from duckduckgo_search import DDGS

        # Load company name and industry from DB
        async with _db_mod.async_session_factory() as db:
            result = await db.execute(select(Company).where(Company.id == company_id))
            company = result.scalar_one_or_none()
            if not company:
                return {"web_context": ""}

            name = company.name
            industry = company.industry or ""

        queries = [
            f"{name} glassdoor reviews culture",
            f"{name} recent news 2026",
            f"{name} {industry} funding hiring",
        ]

        def _search_sync() -> list[str]:
            """Run synchronous DDGS searches in a thread."""
            collected = []
            with DDGS() as ddgs:
                for query in queries:
                    try:
                        results = ddgs.text(query, max_results=3)
                        for r in results:
                            collected.append(f"{r.get('title', '')}: {r.get('body', '')}")
                    except Exception as e:
                        logger.debug("web_search_query_failed", query=query, error=str(e))
                        continue
            return collected

        all_results = await asyncio.to_thread(_search_sync)
        web_context = "\n".join(all_results)[:2000]
        logger.info("graph_web_search_done", company_id=str(company_id), chars=len(web_context))
        return {"web_context": web_context}

    except Exception as e:
        # Graceful degradation: never fail the pipeline
        logger.warning("graph_web_search_skipped", company_id=str(company_id), error=str(e))
        return {"web_context": ""}


async def generate_dossier_node(state: CompanyResearchState) -> dict:
    """Two-phase dossier generation: generic (cached) + personal (fresh)."""
    company_id = uuid.UUID(state["company_id"])
    candidate_id = uuid.UUID(state["candidate_id"])
    web_context = state.get("web_context") or ""

    async with _db_mod.async_session_factory() as db:
        # Load company
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"status": "failed", "error": f"Company {company_id} not found"}

        # Load candidate DNA
        dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        dna = dna_result.scalar_one_or_none()
        candidate_summary = dna.experience_summary if dna else "No candidate DNA available"

        try:
            client = get_openai()
            tech_stack_str = ", ".join(company.tech_stack or [])

            # --- Phase 1: Generic dossier (cached) ---
            input_hash = _compute_input_hash(
                name=company.name,
                domain=company.domain,
                industry=company.industry,
                size=company.size_range,
                description=company.description,
                tech_stack=tech_stack_str,
            )

            generic_data = await get_cached_dossier(company.domain, input_hash)

            if generic_data:
                logger.info("dossier_cache.hit", domain=company.domain)
            else:
                logger.info("dossier_cache.miss", domain=company.domain)
                lock_acquired = await acquire_stampede_lock(company.domain)

                if lock_acquired:
                    try:
                        generic_prompt = DOSSIER_GENERIC_PROMPT.format(
                            company_name=company.name,
                            domain=company.domain,
                            industry=company.industry or "Unknown",
                            size=company.size_range or "Unknown",
                            location=company.location_hq or "Unknown",
                            description=company.description or "No description available",
                            tech_stack=tech_stack_str,
                        )
                        if web_context:
                            generic_prompt += f"\n\nAdditional web research context:\n{web_context}"

                        hunter_data = state.get("hunter_data") or {}
                        generic_data = await client.parse_structured(
                            generic_prompt, json.dumps(hunter_data), DOSSIER_GENERIC_SCHEMA,
                        )
                        await cache_dossier(company.domain, input_hash, generic_data)
                    finally:
                        await release_stampede_lock(company.domain)
                else:
                    # Another worker is generating — wait for cache
                    generic_data = await wait_for_cache(company.domain, input_hash)
                    if not generic_data:
                        # Timeout — generate anyway
                        logger.warning("dossier_cache.stampede_fallback", domain=company.domain)
                        generic_prompt = DOSSIER_GENERIC_PROMPT.format(
                            company_name=company.name,
                            domain=company.domain,
                            industry=company.industry or "Unknown",
                            size=company.size_range or "Unknown",
                            location=company.location_hq or "Unknown",
                            description=company.description or "No description available",
                            tech_stack=tech_stack_str,
                        )
                        if web_context:
                            generic_prompt += f"\n\nAdditional web research context:\n{web_context}"

                        hunter_data = state.get("hunter_data") or {}
                        generic_data = await client.parse_structured(
                            generic_prompt, json.dumps(hunter_data), DOSSIER_GENERIC_SCHEMA,
                        )

            # --- Phase 2: Personal dossier (always fresh) ---
            personal_prompt = DOSSIER_PERSONAL_PROMPT.format(
                generic_dossier=json.dumps(generic_data, indent=2),
                candidate_summary=candidate_summary,
            )
            personal_data = await client.parse_structured(
                personal_prompt, "", DOSSIER_PERSONAL_SCHEMA,
            )

            # --- Merge and save ---
            dossier_data = {**generic_data, **personal_data}

            existing = await db.execute(select(CompanyDossier).where(CompanyDossier.company_id == company_id))
            dossier = existing.scalar_one_or_none()
            if not dossier:
                dossier = CompanyDossier(id=uuid.uuid4(), company_id=company_id)
                db.add(dossier)

            dossier.culture_summary = dossier_data.get("culture_summary")
            dossier.culture_score = dossier_data.get("culture_score")
            dossier.red_flags = dossier_data.get("red_flags")
            dossier.interview_format = dossier_data.get("interview_format")
            dossier.interview_questions = dossier_data.get("interview_questions")
            dossier.compensation_data = dossier_data.get("compensation_data")
            dossier.key_people = dossier_data.get("key_people")
            dossier.why_hire_me = dossier_data.get("why_hire_me")
            dossier.resume_bullets = dossier_data.get("resume_bullets")
            dossier.fit_score_tips = dossier_data.get("fit_score_tips")
            dossier.recent_news = dossier_data.get("recent_news")

            await db.commit()
        except Exception as e:
            logger.error("graph_generate_dossier_failed", company_id=str(company_id), error=str(e))
            return {"status": "failed", "error": f"Dossier generation failed: {e}"}

    logger.info("graph_generate_dossier_done", company_id=str(company_id))
    return {"dossier_data": dossier_data}


async def create_contacts_node(state: CompanyResearchState) -> dict:
    """Create contacts from Hunter data."""
    company_id = uuid.UUID(state["company_id"])
    candidate_id = uuid.UUID(state["candidate_id"])
    hunter_data = state.get("hunter_data") or {}

    async with _db_mod.async_session_factory() as db:
        try:
            contacts = await _create_contacts_from_hunter(db, candidate_id, company_id, hunter_data)
            await db.commit()
        except Exception as e:
            logger.error("graph_create_contacts_failed", company_id=str(company_id), error=str(e))
            return {"status": "failed", "error": f"Contact creation failed: {e}"}

    count = len(contacts)
    logger.info("graph_create_contacts_done", company_id=str(company_id), count=count)
    return {"contacts_created": count}


async def embed_company_node(state: CompanyResearchState) -> dict:
    """Generate embedding for company and set last_enriched."""
    company_id = uuid.UUID(state["company_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"status": "failed", "error": f"Company {company_id} not found"}

        try:
            embed_text_content = f"{company.name} {company.description or ''} {company.industry or ''}"
            company.embedding = await embed_text(embed_text_content)
            company.last_enriched = datetime.now(UTC)
            await db.commit()
        except Exception as e:
            logger.error("graph_embed_company_failed", company_id=str(company_id), error=str(e))
            return {"status": "failed", "error": f"Embedding failed: {e}"}

    logger.info("graph_embed_company_done", company_id=str(company_id))
    return {"embedding_set": True}


async def notify_node(state: CompanyResearchState) -> dict:
    """Mark company research as completed, broadcast via WebSocket."""
    company_id = uuid.UUID(state["company_id"])
    candidate_id = state["candidate_id"]
    contacts_created = state.get("contacts_created", 0)

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        company_name = ""
        if company:
            company.research_status = ResearchStatus.COMPLETED
            company_name = company.name
            await db.commit()

    await ws_manager.broadcast(
        str(candidate_id),
        "research_completed",
        {
            "company_id": str(company_id),
            "company_name": company_name,
            "status": "completed",
            "contacts_created": contacts_created,
        },
    )
    logger.info("graph_notify_done", company_id=str(company_id))
    return {"status": "completed"}


async def mark_failed_node(state: CompanyResearchState) -> dict:
    """Mark company research as failed, broadcast failure notification."""
    company_id = uuid.UUID(state["company_id"])
    candidate_id = state["candidate_id"]
    error = state.get("error", "unknown error")

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if company:
            company.research_status = ResearchStatus.FAILED
            await db.commit()

    await ws_manager.broadcast(
        str(candidate_id),
        "research_completed",
        {
            "company_id": str(company_id),
            "status": "failed",
            "error": error,
        },
    )
    logger.error("graph_mark_failed", company_id=str(company_id), error=error)
    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def _check_error(state: CompanyResearchState) -> str:
    """Route to mark_failed if status is 'failed', otherwise continue."""
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_company_research_graph() -> StateGraph:
    """Build (but don't compile) the company research graph."""
    builder = StateGraph(CompanyResearchState)

    # Add nodes
    builder.add_node("enrich_company", enrich_company_node)
    builder.add_node("web_search", web_search_node)
    builder.add_node("generate_dossier", generate_dossier_node)
    builder.add_node("create_contacts", create_contacts_node)
    builder.add_node("embed_company", embed_company_node)
    builder.add_node("notify", notify_node)
    builder.add_node("mark_failed", mark_failed_node)

    # Wire: START -> enrich_company ->(check)-> web_search ->(check)->
    #   generate_dossier ->(check)-> create_contacts ->(check)->
    #   embed_company ->(check)-> notify -> END
    builder.add_edge(START, "enrich_company")

    builder.add_conditional_edges(
        "enrich_company",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "web_search"},
    )
    builder.add_conditional_edges(
        "web_search",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "generate_dossier"},
    )
    builder.add_conditional_edges(
        "generate_dossier",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "create_contacts"},
    )
    builder.add_conditional_edges(
        "create_contacts",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "embed_company"},
    )
    builder.add_conditional_edges(
        "embed_company",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "notify"},
    )
    builder.add_edge("notify", END)
    builder.add_edge("mark_failed", END)

    return builder


# Module-level builder (reusable)
_builder = build_company_research_graph()


# ---------------------------------------------------------------------------
# Graph accessors
# ---------------------------------------------------------------------------


def get_company_research_pipeline(checkpointer=None):
    """Production: uses shared checkpointer from resume_pipeline."""
    from app.graphs.resume_pipeline import _checkpointer as shared_checkpointer

    cp = checkpointer or shared_checkpointer
    return _builder.compile(checkpointer=cp)


def get_company_research_pipeline_no_checkpointer():
    """Testing: no checkpointer."""
    return _builder.compile()
