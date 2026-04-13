"""LangGraph resume processing pipeline.

Replaces the monolithic _run_async_background() with a 5-node StateGraph:
  parse_resume → extract_skills → generate_dna → recalculate_fits → notify

Each node gets its own DB session and is independently checkpointed.
PostgreSQL checkpointing via langgraph-checkpoint-postgres enables crash
recovery and per-node retry.
"""

import json
import uuid

import structlog
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from typing_extensions import TypedDict

from app.dependencies import get_openai
from app.infrastructure import database as _db_mod
from app.infrastructure.websocket_manager import ws_manager
from app.models.candidate import CandidateDNA, Resume, Skill
from app.models.enums import ParseStatus
from app.services.company_service import recalculate_fit_scores
from app.services.embedding_service import batch_embed, embed_text
from app.services.resume_service import (
    DNA_SCHEMA,
    DNA_SUMMARY_PROMPT,
    RESUME_PARSE_PROMPT,
    RESUME_PARSE_SCHEMA,
    SKILLS_EXTRACTION_PROMPT,
    SKILLS_SCHEMA,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class ResumeProcessingState(TypedDict):
    resume_id: str
    candidate_id: str
    parsed_data: dict | None
    raw_text: str | None
    skills_data: dict | None
    dna_data: dict | None
    embedding: list[float] | None
    skills_vector: list[float] | None
    fit_scores_updated: int
    status: str  # "pending" | "completed" | "failed"
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


async def parse_resume_node(state: ResumeProcessingState) -> dict:
    """Load resume from DB, call OpenAI structured parse, save parsed_data."""
    resume_id = uuid.UUID(state["resume_id"])
    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if not resume:
            return {"status": "failed", "error": f"Resume {resume_id} not found"}
        if not resume.raw_text:
            resume.parse_status = ParseStatus.FAILED
            await db.commit()
            return {"status": "failed", "error": f"Resume {resume_id} has no extracted text"}

        try:
            client = get_openai()
            parsed = await client.parse_structured(RESUME_PARSE_PROMPT, resume.raw_text, RESUME_PARSE_SCHEMA)
            resume.parsed_data = parsed
            await db.commit()
        except Exception as e:
            logger.error("graph_parse_resume_failed", resume_id=str(resume_id), error=str(e))
            return {"status": "failed", "error": f"Resume parsing failed: {e}"}

        logger.info("graph_parse_resume_done", resume_id=str(resume_id))
        return {"parsed_data": parsed, "raw_text": resume.raw_text}


async def extract_skills_node(state: ResumeProcessingState) -> dict:
    """Extract categorized skills from resume text via OpenAI."""
    raw_text = state["raw_text"]
    if not raw_text:
        return {"status": "failed", "error": "No raw_text available for skills extraction"}
    try:
        client = get_openai()
        skills_data = await client.parse_structured(SKILLS_EXTRACTION_PROMPT, raw_text, SKILLS_SCHEMA)
    except Exception as e:
        logger.error("graph_extract_skills_failed", error=str(e))
        return {"status": "failed", "error": f"Skills extraction failed: {e}"}
    logger.info("graph_extract_skills_done", skill_count=len(skills_data.get("skills", [])))
    return {"skills_data": skills_data}


async def generate_dna_node(state: ResumeProcessingState) -> dict:
    """Generate candidate DNA, embeddings, and skill records."""
    candidate_id = uuid.UUID(state["candidate_id"])
    parsed_data = state["parsed_data"]
    skills_data = state["skills_data"]
    raw_text = state["raw_text"]

    if not parsed_data or not skills_data:
        return {"status": "failed", "error": "Missing parsed_data or skills_data for DNA generation"}

    try:
        client = get_openai()
        resume_text = raw_text or json.dumps(parsed_data)

        # Generate embeddings
        embedding = await embed_text(resume_text)

        # Generate DNA summary
        dna_data = await client.parse_structured(DNA_SUMMARY_PROMPT, json.dumps(parsed_data), DNA_SCHEMA)

        # Generate skills vector
        skill_names = [s["name"] for s in skills_data.get("skills", [])]
        skills_vector = await embed_text(" ".join(skill_names)) if skill_names else embedding
    except Exception as e:
        logger.error("graph_generate_dna_failed", candidate_id=str(candidate_id), error=str(e))
        return {"status": "failed", "error": f"DNA generation failed: {e}"}

    async with _db_mod.async_session_factory() as db:
        # Delete existing DNA and skills
        existing = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        old_dna = existing.scalar_one_or_none()
        if old_dna:
            await db.delete(old_dna)

        existing_skills = await db.execute(select(Skill).where(Skill.candidate_id == candidate_id))
        for s in existing_skills.scalars():
            await db.delete(s)

        # Create DNA
        dna = CandidateDNA(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            embedding=embedding,
            skills_vector=skills_vector,
            experience_summary=dna_data.get("experience_summary"),
            strengths=dna_data.get("strengths"),
            gaps=dna_data.get("gaps"),
            career_stage=dna_data.get("career_stage"),
            transferable_skills={
                s["name"]: s.get("evidence", "")
                for s in skills_data.get("skills", [])
                if s.get("category") == "transferable"
            },
        )
        db.add(dna)

        # Create skill records with embeddings (batched single API call)
        skills_list = skills_data.get("skills", [])
        skill_names_for_embed = [s["name"] for s in skills_list]
        skill_embeddings = await batch_embed(skill_names_for_embed) if skill_names_for_embed else []

        for skill_data_item, skill_embedding in zip(skills_list, skill_embeddings, strict=False):
            skill = Skill(
                id=uuid.uuid4(),
                candidate_id=candidate_id,
                name=skill_data_item["name"],
                category=skill_data_item.get("category", "explicit"),
                proficiency=skill_data_item.get("proficiency"),
                years_experience=skill_data_item.get("years_experience"),
                evidence=skill_data_item.get("evidence"),
                embedding=skill_embedding,
            )
            db.add(skill)

        await db.commit()

    logger.info("graph_generate_dna_done", candidate_id=str(candidate_id))
    return {"dna_data": dna_data, "embedding": embedding, "skills_vector": skills_vector}


async def recalculate_fits_node(state: ResumeProcessingState) -> dict:
    """Recalculate fit scores for all companies with updated DNA."""
    candidate_id = uuid.UUID(state["candidate_id"])
    try:
        async with _db_mod.async_session_factory() as db:
            updated = await recalculate_fit_scores(db, candidate_id)
    except Exception as e:
        logger.error("graph_recalculate_fits_failed", candidate_id=str(candidate_id), error=str(e))
        return {"status": "failed", "error": f"Fit score recalculation failed: {e}"}
    logger.info("graph_recalculate_fits_done", candidate_id=str(candidate_id), updated=updated)
    return {"fit_scores_updated": updated}


async def notify_node(state: ResumeProcessingState) -> dict:
    """Mark resume completed and broadcast via WebSocket."""
    resume_id = uuid.UUID(state["resume_id"])
    candidate_id = state["candidate_id"]
    fit_scores_updated = state.get("fit_scores_updated", 0)

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if resume:
            resume.parse_status = ParseStatus.COMPLETED
            await db.commit()

    await ws_manager.broadcast(
        str(candidate_id),
        "resume_parsed",
        {"resume_id": str(resume_id), "status": "completed", "fit_scores_updated": fit_scores_updated},
    )

    from app.events.bus import get_event_bus

    skills = state.get("skills_data", {}).get("skills", []) if state.get("skills_data") else []
    await get_event_bus().publish(
        "resume_parsed",
        {"candidate_id": str(candidate_id), "resume_id": str(resume_id), "skills": [s.get("name", "") for s in skills]},
        source="resume_pipeline.notify_node",
    )

    logger.info("graph_notify_done", resume_id=str(resume_id))
    return {"status": "completed"}


async def mark_failed_node(state: ResumeProcessingState) -> dict:
    """Mark resume as failed and broadcast failure notification."""
    resume_id = uuid.UUID(state["resume_id"])
    candidate_id = state["candidate_id"]
    error = state.get("error", "unknown error")

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if resume:
            resume.parse_status = ParseStatus.FAILED
            resume.parsed_data = {"_error": error}
            await db.commit()

    await ws_manager.broadcast(
        str(candidate_id),
        "resume_parsed",
        {"resume_id": str(resume_id), "status": "failed", "error": error},
    )
    logger.error("graph_mark_failed", resume_id=str(resume_id), error=error)
    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def _check_error(state: ResumeProcessingState) -> str:
    """Route to mark_failed if status is 'failed', otherwise continue."""
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_resume_pipeline() -> StateGraph:
    """Build (but don't compile) the resume processing graph."""
    builder = StateGraph(ResumeProcessingState)

    # Add nodes
    builder.add_node("parse_resume", parse_resume_node)
    builder.add_node("extract_skills", extract_skills_node)
    builder.add_node("generate_dna", generate_dna_node)
    builder.add_node("recalculate_fits", recalculate_fits_node)
    builder.add_node("notify", notify_node)
    builder.add_node("mark_failed", mark_failed_node)

    # Wire: START → parse_resume →(check)→ extract_skills →(check)→
    #        generate_dna →(check)→ recalculate_fits → notify → END
    builder.add_edge(START, "parse_resume")

    builder.add_conditional_edges(
        "parse_resume",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "extract_skills"},
    )
    builder.add_conditional_edges(
        "extract_skills",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "generate_dna"},
    )
    builder.add_conditional_edges(
        "generate_dna",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "recalculate_fits"},
    )
    builder.add_conditional_edges(
        "recalculate_fits",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "notify"},
    )
    builder.add_edge("notify", END)
    builder.add_edge("mark_failed", END)

    return builder


# Module-level builder (reusable)
_builder = build_resume_pipeline()

# ---------------------------------------------------------------------------
# Checkpointer management
# ---------------------------------------------------------------------------

_checkpointer = None
_checkpointer_cm = None


async def init_checkpointer(db_url: str) -> None:
    """Call once at app startup to initialize PostgreSQL checkpointing."""
    global _checkpointer, _checkpointer_cm
    # langgraph-checkpoint-postgres uses psycopg (sync driver), not asyncpg
    raw_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(raw_url)
    _checkpointer = await _checkpointer_cm.__aenter__()
    await _checkpointer.setup()
    logger.info("langgraph_checkpointer_initialized")


async def close_checkpointer() -> None:
    """Call at app shutdown to clean up checkpointer connections."""
    global _checkpointer, _checkpointer_cm
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
        _checkpointer = None


def get_resume_pipeline():
    """Production: compiled graph with PostgreSQL checkpointer."""
    return _builder.compile(checkpointer=_checkpointer)


def get_resume_pipeline_no_checkpointer():
    """Testing: compiled graph without checkpointer."""
    return _builder.compile()
