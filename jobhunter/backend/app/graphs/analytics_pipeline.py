"""LangGraph analytics pipeline - AI-powered job search insights.

5-node StateGraph + mark_failed:
  gather_data → generate_insights → save_insights → notify
                                                       ↗
  mark_failed ───────────────────────────────────→ END

Aggregates pipeline, outreach, and skill data, generates AI insights via
OpenAI structured output, persists them as AnalyticsInsight records, and
optionally emails a weekly digest.
"""

import json
import uuid

import structlog
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from typing_extensions import TypedDict

from app.dependencies import get_email_client, get_openai
from app.infrastructure import database as _db_mod
from app.infrastructure.websocket_manager import ws_manager

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class AnalyticsState(TypedDict):
    candidate_id: str
    include_email: bool
    raw_data: dict | None  # Aggregated pipeline/outreach/skill data
    insights: list[dict] | None  # AI-generated insights
    insights_saved: int
    status: str  # "pending" | "completed" | "failed"
    error: str | None


# ---------------------------------------------------------------------------
# Prompts & schemas
# ---------------------------------------------------------------------------

INSIGHTS_PROMPT = (
    "You are a job search analytics advisor. "
    "Analyze this candidate's job search data and generate actionable insights.\n\n"
    "Pipeline: {pipeline}\n"
    "Outreach funnel: {funnel}\n"
    "Outreach stats: {outreach}\n"
    "Skills ({skill_count}): {skills}\n"
    "Career stage: {career_stage}\n"
    "Experience: {experience_summary}\n\n"
    "Generate 3-5 specific, actionable insights. Each insight should have:\n"
    "- insight_type: one of 'pipeline_health', 'outreach_effectiveness',"
    " 'skill_gap', 'market_positioning', 'recommendation'\n"
    "- title: short descriptive title (under 100 chars)\n"
    "- body: detailed explanation with specific numbers and recommendations"
    " (2-3 sentences)\n"
    "- severity: one of 'info', 'warning', 'success', 'action_needed'\n"
    "- data: optional dict with supporting numbers\n\n"
    "Focus on what's actionable. If data is empty/zero, suggest getting started steps."
)

INSIGHTS_SCHEMA = {
    "type": "object",
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "insight_type": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "severity": {"type": "string"},
                    "data": {"type": "object"},
                },
                "required": ["insight_type", "title", "body", "severity", "data"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["insights"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


async def gather_data_node(state: AnalyticsState) -> dict:
    """Load pipeline, outreach, and funnel stats from DB."""
    candidate_id = uuid.UUID(state["candidate_id"])

    try:
        async with _db_mod.async_session_factory() as db:
            from app.services import analytics_service

            funnel = await analytics_service.get_funnel(db, candidate_id)
            outreach = await analytics_service.get_outreach_stats(db, candidate_id)
            pipeline = await analytics_service.get_pipeline_stats(db, candidate_id)

            # Also count skills and interview prep sessions
            from app.models.candidate import CandidateDNA, Skill

            skills_result = await db.execute(select(Skill).where(Skill.candidate_id == candidate_id))
            skills = skills_result.scalars().all()
            skill_names = [s.name for s in skills]

            dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
            dna = dna_result.scalar_one_or_none()
    except Exception as e:
        logger.error("analytics_gather_data_failed", error=str(e))
        return {"status": "failed", "error": f"Data gathering failed: {e}"}

    raw_data = {
        "funnel": funnel,
        "outreach": outreach,
        "pipeline": pipeline,
        "skill_count": len(skill_names),
        "skills": skill_names[:20],  # Top 20 for prompt
        "career_stage": dna.career_stage if dna else "unknown",
        "experience_summary": dna.experience_summary if dna else "No profile",
    }

    logger.info("analytics_data_gathered", candidate_id=str(candidate_id))
    return {"raw_data": raw_data}


async def generate_insights_node(state: AnalyticsState) -> dict:
    """Call OpenAI structured output to generate AI insights."""
    raw_data = state.get("raw_data") or {}

    prompt = INSIGHTS_PROMPT.format(
        pipeline=json.dumps(raw_data.get("pipeline", {})),
        funnel=json.dumps(raw_data.get("funnel", {})),
        outreach=json.dumps(raw_data.get("outreach", {})),
        skill_count=raw_data.get("skill_count", 0),
        skills=", ".join(raw_data.get("skills", [])),
        career_stage=raw_data.get("career_stage", "unknown"),
        experience_summary=raw_data.get("experience_summary", "No profile"),
    )

    try:
        client = get_openai()
        result = await client.parse_structured(prompt, "", INSIGHTS_SCHEMA)
        insights = result.get("insights", [])
    except Exception as e:
        logger.error("analytics_generate_insights_failed", error=str(e))
        return {"status": "failed", "error": f"Insight generation failed: {e}"}

    logger.info("analytics_insights_generated", count=len(insights))
    return {"insights": insights}


async def save_insights_node(state: AnalyticsState) -> dict:
    """Save AI-generated insights to DB."""
    from app.models.insight import AnalyticsInsight

    candidate_id = uuid.UUID(state["candidate_id"])
    insights = state["insights"] or []
    saved = 0

    try:
        async with _db_mod.async_session_factory() as db:
            for insight_data in insights:
                insight = AnalyticsInsight(
                    id=uuid.uuid4(),
                    candidate_id=candidate_id,
                    insight_type=insight_data.get("insight_type", "recommendation"),
                    title=insight_data.get("title", ""),
                    body=insight_data.get("body", ""),
                    severity=insight_data.get("severity", "info"),
                    data=insight_data.get("data"),
                )
                db.add(insight)
                saved += 1
            await db.commit()
    except Exception as e:
        logger.error("analytics_save_insights_failed", error=str(e))
        return {"status": "failed", "error": f"Failed to save insights: {e}"}

    logger.info("analytics_insights_saved", count=saved)
    return {"insights_saved": saved}


async def notify_node(state: AnalyticsState) -> dict:
    """Notify via WebSocket and optionally send email digest."""
    try:
        await ws_manager.broadcast(
            state["candidate_id"],
            "analytics_completed",
            {"insights_count": state.get("insights_saved", 0)},
        )
    except Exception as e:
        logger.warning("analytics_notify_broadcast_failed", error=str(e))

    if state.get("include_email"):
        try:
            email_client = get_email_client()
            # Build simple text digest from insights
            insights = state.get("insights") or []
            lines = ["Weekly Job Search Analytics Digest\n"]
            for i, insight in enumerate(insights, 1):
                lines.append(f"{i}. [{insight.get('severity', 'info').upper()}] {insight.get('title', '')}")
                lines.append(f"   {insight.get('body', '')}\n")

            body = "\n".join(lines)

            # Get candidate email
            async with _db_mod.async_session_factory() as db:
                from app.models.candidate import Candidate

                result = await db.execute(select(Candidate).where(Candidate.id == uuid.UUID(state["candidate_id"])))
                candidate = result.scalar_one_or_none()
                if candidate:
                    from app.config import settings

                    await email_client.send(
                        to=candidate.email,
                        from_email=settings.SENDER_EMAIL,
                        subject="Your Weekly Job Search Analytics",
                        body=body,
                    )
        except Exception as e:
            logger.warning("analytics_email_failed", error=str(e))

    logger.info("analytics_notify_done", candidate_id=state["candidate_id"])
    return {"status": "completed"}


async def mark_failed_node(state: AnalyticsState) -> dict:
    """Log failure and notify."""
    try:
        await ws_manager.broadcast(
            state["candidate_id"],
            "analytics_failed",
            {"error": state.get("error")},
        )
    except Exception as e:
        logger.warning("analytics_mark_failed_broadcast_failed", error=str(e))

    logger.error(
        "analytics_mark_failed",
        candidate_id=state["candidate_id"],
        error=state.get("error"),
    )
    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def _check_error(state: AnalyticsState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_analytics_pipeline() -> StateGraph:
    """Build (but don't compile) the analytics graph."""
    builder = StateGraph(AnalyticsState)

    builder.add_node("gather_data", gather_data_node)
    builder.add_node("generate_insights", generate_insights_node)
    builder.add_node("save_insights", save_insights_node)
    builder.add_node("notify", notify_node)
    builder.add_node("mark_failed", mark_failed_node)

    # START -> gather_data
    builder.add_edge(START, "gather_data")

    # gather_data -> generate_insights | mark_failed
    builder.add_conditional_edges(
        "gather_data",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "generate_insights"},
    )

    # generate_insights -> save_insights | mark_failed
    builder.add_conditional_edges(
        "generate_insights",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "save_insights"},
    )

    # save_insights -> notify | mark_failed
    builder.add_conditional_edges(
        "save_insights",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "notify"},
    )

    # notify -> END
    builder.add_edge("notify", END)

    # mark_failed -> END
    builder.add_edge("mark_failed", END)

    return builder


# Module-level builder (reusable)
_builder = build_analytics_pipeline()


# ---------------------------------------------------------------------------
# Graph accessors
# ---------------------------------------------------------------------------


def get_analytics_pipeline(checkpointer=None):
    """Production: compiled graph with PostgreSQL checkpointer."""
    from app.graphs.resume_pipeline import _checkpointer as shared

    return _builder.compile(checkpointer=checkpointer or shared)


def get_analytics_pipeline_no_checkpointer():
    """Testing: compiled graph without checkpointer."""
    return _builder.compile()
