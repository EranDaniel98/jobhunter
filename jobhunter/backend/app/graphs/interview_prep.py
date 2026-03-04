"""LangGraph interview prep pipeline.

4-node StateGraph:
  load_context -> generate_prep -> save_and_notify -> END
  (mark_failed on any error)
"""

import json
import uuid
from typing_extensions import TypedDict

import structlog
from langgraph.graph import StateGraph, START, END
from sqlalchemy import select

from app.infrastructure import database as _db_mod
from app.dependencies import get_openai
from app.models.candidate import CandidateDNA
from app.models.company import Company, CompanyDossier
from app.models.interview import InterviewPrepSession
from app.infrastructure.websocket_manager import ws_manager

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Prompts per prep type
# ---------------------------------------------------------------------------

INTERVIEW_PREP_PROMPTS = {
    "company_qa": (
        "You are an expert interview coach. Generate company-specific interview preparation.\n"
        "Company: {company_name} ({industry})\n"
        "Culture: {culture_summary}\n"
        "Interview format: {interview_format}\n"
        "Candidate profile: {candidate_summary}\n"
        "Why hire: {why_hire_me}\n\n"
        "Generate 10-15 likely interview questions with suggested answers tailored to this candidate. "
        "Group by category: technical, behavioral, culture-fit, role-specific."
    ),
    "behavioral": (
        "You are an expert interview coach. Generate STAR-format behavioral stories.\n"
        "Candidate profile: {candidate_summary}\n"
        "Target company: {company_name} ({industry})\n"
        "Key skills: {strengths}\n\n"
        "Generate 5-7 STAR stories (Situation, Task, Action, Result) from the candidate's background "
        "that would resonate with this company. Each story should map to a common behavioral question."
    ),
    "technical": (
        "You are a technical interview coach. Generate technical preparation material.\n"
        "Company: {company_name}\n"
        "Tech stack: {tech_stack}\n"
        "Candidate skills: {strengths}\n"
        "Candidate gaps: {gaps}\n\n"
        "Generate preparation topics covering: system design, coding patterns, and domain-specific questions "
        "relevant to this company's tech stack. Include 3-5 questions per topic with answers."
    ),
    "culture_fit": (
        "You are a culture-fit interview coach.\n"
        "Company: {company_name}\n"
        "Culture: {culture_summary}\n"
        "Red flags: {red_flags}\n"
        "Candidate profile: {candidate_summary}\n\n"
        "Generate culture-fit preparation with:\n"
        "- 'values': an array of company values, each with 'value' (the value name), "
        "'description' (what it means at this company), and 'how_to_demonstrate' "
        "(specific advice for the candidate to show genuine alignment in an interview).\n"
        "- 'tips': general tips for culture-fit interviews at this company."
    ),
    "salary_negotiation": (
        "You are a salary negotiation coach.\n"
        "Company: {company_name} ({industry}, {size_range})\n"
        "Compensation data: {compensation_data}\n"
        "Candidate profile: {candidate_summary}\n"
        "Career stage: {career_stage}\n\n"
        "Generate salary negotiation prep: market range analysis, talking points, "
        "counter-offer strategies, and how to discuss compensation confidently."
    ),
}

# Strict JSON schemas for OpenAI structured output
INTERVIEW_PREP_SCHEMAS = {
    "company_qa": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                        "category": {"type": "string"},
                    },
                    "required": ["question", "answer", "category"],
                    "additionalProperties": False,
                },
            },
            "tips": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["questions", "tips"],
        "additionalProperties": False,
    },
    "behavioral": {
        "type": "object",
        "properties": {
            "stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "situation": {"type": "string"},
                        "task": {"type": "string"},
                        "action": {"type": "string"},
                        "result": {"type": "string"},
                    },
                    "required": ["question", "situation", "task", "action", "result"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["stories"],
        "additionalProperties": False,
    },
    "technical": {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "answer": {"type": "string"},
                                    "difficulty": {"type": "string"},
                                },
                                "required": ["question", "answer", "difficulty"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["topic", "questions"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["topics"],
        "additionalProperties": False,
    },
    "culture_fit": {
        "type": "object",
        "properties": {
            "values": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "description": {"type": "string"},
                        "how_to_demonstrate": {"type": "string"},
                    },
                    "required": ["value", "description", "how_to_demonstrate"],
                    "additionalProperties": False,
                },
            },
            "tips": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["values", "tips"],
        "additionalProperties": False,
    },
    "salary_negotiation": {
        "type": "object",
        "properties": {
            "salary_range": {
                "type": "object",
                "properties": {
                    "low": {"type": "number"},
                    "mid": {"type": "number"},
                    "high": {"type": "number"},
                },
                "required": ["low", "mid", "high"],
                "additionalProperties": False,
            },
            "strategies": {"type": "array", "items": {"type": "string"}},
            "talking_points": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["salary_range", "strategies", "talking_points"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class InterviewPrepState(TypedDict):
    candidate_id: str
    company_id: str
    prep_type: str
    session_id: str | None
    context: dict | None
    content: dict | None
    status: str  # "pending" | "generating" | "completed" | "failed"
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def load_context_node(state: InterviewPrepState) -> dict:
    """Load company dossier and candidate DNA for prep generation."""
    candidate_id = uuid.UUID(state["candidate_id"])
    company_id = uuid.UUID(state["company_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"status": "failed", "error": f"Company {company_id} not found"}

        result = await db.execute(select(CompanyDossier).where(CompanyDossier.company_id == company_id))
        dossier = result.scalar_one_or_none()

        result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        dna = result.scalar_one_or_none()

        # Create session record
        session = InterviewPrepSession(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            company_id=company_id,
            prep_type=state["prep_type"],
            status="generating",
        )
        db.add(session)
        await db.commit()

    context = {
        "company_name": company.name,
        "industry": company.industry or "Unknown",
        "tech_stack": ", ".join(company.tech_stack or []),
        "size_range": company.size_range or "Unknown",
        "culture_summary": dossier.culture_summary if dossier else "Unknown",
        "red_flags": ", ".join(dossier.red_flags or []) if dossier else "None",
        "interview_format": dossier.interview_format if dossier else "Unknown",
        "compensation_data": json.dumps(dossier.compensation_data) if dossier and dossier.compensation_data else "Unknown",
        "why_hire_me": dossier.why_hire_me if dossier else "Strong candidate fit",
        "candidate_summary": dna.experience_summary if dna else "No candidate profile",
        "strengths": ", ".join(dna.strengths or []) if dna else "Unknown",
        "gaps": ", ".join(dna.gaps or []) if dna else "Unknown",
        "career_stage": dna.career_stage if dna else "Unknown",
    }

    return {"session_id": str(session.id), "context": context, "status": "generating"}


async def generate_prep_node(state: InterviewPrepState) -> dict:
    """Generate interview prep content using OpenAI structured output."""
    prep_type = state["prep_type"]
    context = state["context"]

    prompt_template = INTERVIEW_PREP_PROMPTS.get(prep_type)
    schema = INTERVIEW_PREP_SCHEMAS.get(prep_type)
    if not prompt_template or not schema:
        return {"status": "failed", "error": f"Unknown prep_type: {prep_type}"}

    prompt = prompt_template.format(**context)

    try:
        client = get_openai()
        content = await client.parse_structured(prompt, "", schema)
    except Exception as e:
        logger.error("interview_prep_generation_failed", error=str(e))
        return {"status": "failed", "error": f"Generation failed: {e}"}

    return {"content": content}


async def save_and_notify_node(state: InterviewPrepState) -> dict:
    """Save generated content to DB and notify via WebSocket."""
    session_id = uuid.UUID(state["session_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(InterviewPrepSession).where(InterviewPrepSession.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            session.content = state["content"]
            session.status = "completed"
            await db.commit()

    await ws_manager.broadcast(
        state["candidate_id"], "interview_prep_completed",
        {"session_id": state["session_id"], "prep_type": state["prep_type"]},
    )

    return {"status": "completed"}


async def mark_failed_node(state: InterviewPrepState) -> dict:
    """Mark session as failed."""
    session_id = state.get("session_id")
    if session_id:
        async with _db_mod.async_session_factory() as db:
            result = await db.execute(
                select(InterviewPrepSession).where(InterviewPrepSession.id == uuid.UUID(session_id))
            )
            session = result.scalar_one_or_none()
            if session:
                session.status = "failed"
                session.error = state.get("error")
                await db.commit()

    await ws_manager.broadcast(
        state["candidate_id"], "interview_prep_failed",
        {"session_id": session_id, "error": state.get("error")},
    )

    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def _check_error(state: InterviewPrepState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_interview_prep_pipeline() -> StateGraph:
    """Build (but don't compile) the interview prep graph."""
    builder = StateGraph(InterviewPrepState)

    builder.add_node("load_context", load_context_node)
    builder.add_node("generate_prep", generate_prep_node)
    builder.add_node("save_and_notify", save_and_notify_node)
    builder.add_node("mark_failed", mark_failed_node)

    builder.add_edge(START, "load_context")
    builder.add_conditional_edges(
        "load_context", _check_error,
        {"mark_failed": "mark_failed", "continue": "generate_prep"},
    )
    builder.add_conditional_edges(
        "generate_prep", _check_error,
        {"mark_failed": "mark_failed", "continue": "save_and_notify"},
    )
    builder.add_edge("save_and_notify", END)
    builder.add_edge("mark_failed", END)

    return builder


_builder = build_interview_prep_pipeline()


# ---------------------------------------------------------------------------
# Graph accessors
# ---------------------------------------------------------------------------

def get_interview_prep_pipeline(checkpointer=None):
    """Production: compiled graph with PostgreSQL checkpointer."""
    from app.graphs.resume_pipeline import _checkpointer as shared
    return _builder.compile(checkpointer=checkpointer or shared)


def get_interview_prep_pipeline_no_checkpointer():
    """Testing: compiled graph without checkpointer."""
    return _builder.compile()
