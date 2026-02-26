"""LangGraph apply agent pipeline.

6-node StateGraph:
  parse_job -> match_skills -> generate_tips -> generate_cover_letter -> save_and_notify -> END
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
from app.models.candidate import CandidateDNA, Skill
from app.models.company import Company, CompanyDossier
from app.models.job_posting import JobPosting
from app.infrastructure.websocket_manager import ws_manager

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PARSE_JOB_PROMPT = (
    "Parse this job posting and extract structured requirements.\n\n"
    "Job Title: {title}\n"
    "Company: {company_name}\n"
    "Description:\n{raw_text}\n\n"
    "Extract: required skills, preferred skills, years of experience needed, "
    "education requirements, key responsibilities, and ATS-friendly keywords."
)

PARSE_JOB_SCHEMA = {
    "type": "object",
    "properties": {
        "required_skills": {"type": "array", "items": {"type": "string"}},
        "preferred_skills": {"type": "array", "items": {"type": "string"}},
        "experience_years": {"type": "integer"},
        "education": {"type": "string"},
        "responsibilities": {"type": "array", "items": {"type": "string"}},
        "ats_keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["required_skills", "preferred_skills", "experience_years", "education", "responsibilities", "ats_keywords"],
    "additionalProperties": False,
}

RESUME_TIPS_PROMPT = (
    "You are a resume coach. The candidate is applying for this role.\n\n"
    "Job: {title} at {company_name}\n"
    "Required skills: {required_skills}\n"
    "Preferred skills: {preferred_skills}\n"
    "Candidate's skills: {candidate_skills}\n"
    "Candidate's experience: {candidate_summary}\n"
    "Candidate's gaps: {gaps}\n\n"
    "DO NOT rewrite the resume. Instead, provide specific, actionable tips:\n"
    "- What sections to update and how\n"
    "- What keywords to add and where\n"
    "- What experience to highlight\n"
    "- What's missing that should be added\n"
    "Each tip should specify the resume section and priority (high/medium/low)."
)

RESUME_TIPS_SCHEMA = {
    "type": "object",
    "properties": {
        "tips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "tip": {"type": "string"},
                    "priority": {"type": "string"},
                },
                "required": ["section", "tip", "priority"],
                "additionalProperties": False,
            },
        },
        "readiness_score": {"type": "number"},
    },
    "required": ["tips", "readiness_score"],
    "additionalProperties": False,
}

COVER_LETTER_PROMPT = (
    "Write a tailored cover letter for this application.\n\n"
    "Job: {title} at {company_name}\n"
    "Key requirements: {required_skills}\n"
    "Candidate profile: {candidate_summary}\n"
    "Matching skills: {matching_skills}\n"
    "Why hire: {why_hire_me}\n\n"
    "Write a professional, concise cover letter (3-4 paragraphs). "
    "Reference specific company details and explain fit."
)

COVER_LETTER_SCHEMA = {
    "type": "object",
    "properties": {
        "cover_letter": {"type": "string"},
    },
    "required": ["cover_letter"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class ApplyState(TypedDict):
    candidate_id: str
    job_posting_id: str
    parsed_requirements: dict | None
    candidate_skills: list[str] | None
    matching_skills: list[str] | None
    missing_skills: list[str] | None
    resume_tips: list[dict] | None
    readiness_score: float | None
    cover_letter: str | None
    ats_keywords: list[str] | None
    context: dict | None
    status: str
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def parse_job_node(state: ApplyState) -> dict:
    """Parse job posting and extract requirements."""
    job_posting_id = uuid.UUID(state["job_posting_id"])
    candidate_id = uuid.UUID(state["candidate_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(JobPosting).where(JobPosting.id == job_posting_id))
        posting = result.scalar_one_or_none()
        if not posting:
            return {"status": "failed", "error": f"JobPosting {job_posting_id} not found"}

        dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        dna = dna_result.scalar_one_or_none()

        skills_result = await db.execute(select(Skill).where(Skill.candidate_id == candidate_id))
        skills = skills_result.scalars().all()

        company_name = posting.company_name or "Unknown"
        why_hire_me = ""
        if posting.company_id:
            company_result = await db.execute(select(Company).where(Company.id == posting.company_id))
            company = company_result.scalar_one_or_none()
            if company:
                company_name = company.name
                dossier_result = await db.execute(select(CompanyDossier).where(CompanyDossier.company_id == company.id))
                dossier = dossier_result.scalar_one_or_none()
                if dossier:
                    why_hire_me = dossier.why_hire_me or ""

    prompt = PARSE_JOB_PROMPT.format(
        title=posting.title, company_name=company_name, raw_text=posting.raw_text
    )

    try:
        client = get_openai()
        parsed = await client.parse_structured(prompt, "", PARSE_JOB_SCHEMA)
    except Exception as e:
        return {"status": "failed", "error": f"Job parsing failed: {e}"}

    candidate_skill_names = [s.name.lower() for s in skills]
    context = {
        "title": posting.title,
        "company_name": company_name,
        "raw_text": posting.raw_text,
        "candidate_summary": dna.experience_summary if dna else "No profile",
        "gaps": ", ".join(dna.gaps or []) if dna else "",
        "why_hire_me": why_hire_me,
    }

    return {
        "parsed_requirements": parsed,
        "candidate_skills": candidate_skill_names,
        "ats_keywords": parsed.get("ats_keywords", []),
        "context": context,
    }


async def match_skills_node(state: ApplyState) -> dict:
    """Compare candidate skills against job requirements."""
    parsed = state["parsed_requirements"]
    candidate_skills = set(state["candidate_skills"] or [])

    all_required = set(s.lower() for s in parsed.get("required_skills", []))
    all_preferred = set(s.lower() for s in parsed.get("preferred_skills", []))
    all_job_skills = all_required | all_preferred

    matching = sorted(candidate_skills & all_job_skills)
    missing = sorted(all_required - candidate_skills)

    return {"matching_skills": matching, "missing_skills": missing}


async def generate_tips_node(state: ApplyState) -> dict:
    """Generate resume tips (NOT rewrites)."""
    context = state["context"]

    prompt = RESUME_TIPS_PROMPT.format(
        title=context["title"],
        company_name=context["company_name"],
        required_skills=", ".join(state["parsed_requirements"].get("required_skills", [])),
        preferred_skills=", ".join(state["parsed_requirements"].get("preferred_skills", [])),
        candidate_skills=", ".join(state["candidate_skills"] or []),
        candidate_summary=context["candidate_summary"],
        gaps=context["gaps"],
    )

    try:
        client = get_openai()
        result = await client.parse_structured(prompt, "", RESUME_TIPS_SCHEMA)
    except Exception as e:
        return {"status": "failed", "error": f"Tips generation failed: {e}"}

    return {
        "resume_tips": result.get("tips", []),
        "readiness_score": result.get("readiness_score", 0),
    }


async def generate_cover_letter_node(state: ApplyState) -> dict:
    """Generate a tailored cover letter."""
    context = state["context"]

    prompt = COVER_LETTER_PROMPT.format(
        title=context["title"],
        company_name=context["company_name"],
        required_skills=", ".join(state["parsed_requirements"].get("required_skills", [])),
        candidate_summary=context["candidate_summary"],
        matching_skills=", ".join(state["matching_skills"] or []),
        why_hire_me=context.get("why_hire_me") or "Strong candidate fit",
    )

    try:
        client = get_openai()
        result = await client.parse_structured(prompt, "", COVER_LETTER_SCHEMA)
    except Exception as e:
        return {"status": "failed", "error": f"Cover letter generation failed: {e}"}

    return {"cover_letter": result.get("cover_letter", "")}


async def save_and_notify_node(state: ApplyState) -> dict:
    """Save analysis results to DB and notify."""
    job_posting_id = uuid.UUID(state["job_posting_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(JobPosting).where(JobPosting.id == job_posting_id))
        posting = result.scalar_one_or_none()
        if posting:
            posting.parsed_requirements = state["parsed_requirements"]
            posting.ats_keywords = state["ats_keywords"]
            posting.status = "analyzed"
            await db.commit()

    await ws_manager.broadcast(
        state["candidate_id"], "apply_analysis_completed",
        {"job_posting_id": state["job_posting_id"], "readiness_score": state.get("readiness_score", 0)},
    )

    return {"status": "completed"}


async def mark_failed_node(state: ApplyState) -> dict:
    """Mark job posting as failed."""
    job_posting_id = state.get("job_posting_id")
    if job_posting_id:
        async with _db_mod.async_session_factory() as db:
            result = await db.execute(select(JobPosting).where(JobPosting.id == uuid.UUID(job_posting_id)))
            posting = result.scalar_one_or_none()
            if posting:
                posting.status = "failed"
                await db.commit()

    await ws_manager.broadcast(
        state["candidate_id"], "apply_analysis_failed",
        {"job_posting_id": job_posting_id, "error": state.get("error")},
    )

    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def _check_error(state: ApplyState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_apply_pipeline() -> StateGraph:
    """Build (but don't compile) the apply graph."""
    builder = StateGraph(ApplyState)

    builder.add_node("parse_job", parse_job_node)
    builder.add_node("match_skills", match_skills_node)
    builder.add_node("generate_tips", generate_tips_node)
    builder.add_node("generate_cover_letter", generate_cover_letter_node)
    builder.add_node("save_and_notify", save_and_notify_node)
    builder.add_node("mark_failed", mark_failed_node)

    builder.add_edge(START, "parse_job")
    builder.add_conditional_edges(
        "parse_job", _check_error,
        {"mark_failed": "mark_failed", "continue": "match_skills"},
    )
    builder.add_edge("match_skills", "generate_tips")
    builder.add_conditional_edges(
        "generate_tips", _check_error,
        {"mark_failed": "mark_failed", "continue": "generate_cover_letter"},
    )
    builder.add_conditional_edges(
        "generate_cover_letter", _check_error,
        {"mark_failed": "mark_failed", "continue": "save_and_notify"},
    )
    builder.add_edge("save_and_notify", END)
    builder.add_edge("mark_failed", END)

    return builder


_builder = build_apply_pipeline()


# ---------------------------------------------------------------------------
# Graph accessors
# ---------------------------------------------------------------------------

def get_apply_pipeline(checkpointer=None):
    """Production: compiled graph with PostgreSQL checkpointer."""
    from app.graphs.resume_pipeline import _checkpointer as shared
    return _builder.compile(checkpointer=checkpointer or shared)


def get_apply_pipeline_no_checkpointer():
    """Testing: compiled graph without checkpointer."""
    return _builder.compile()
