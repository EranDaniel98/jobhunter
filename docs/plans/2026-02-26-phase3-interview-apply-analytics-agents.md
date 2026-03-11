# Phase 3: Interview Prep + Apply + Analytics Agents

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the Phase 3 multi-agent system by adding Interview Prep, Apply, and Analytics agents with full backend (models, LangGraph pipelines, API routes, tests) and frontend (pages, components, hooks).

**Architecture:** Three LangGraph StateGraph pipelines sharing the existing PostgreSQL checkpointer from `resume_pipeline.py`. Each agent has its own models, schemas, API router, and dedicated frontend page. Build order: Interview → Apply → Analytics.

**Tech Stack:** FastAPI, SQLAlchemy async, LangGraph, pgvector, ARQ cron, Next.js App Router, React Query, shadcn/ui, Recharts

**Prerequisites:** Scout Agent PR #21 must be merged first (adds migration 013 + CompanySignal model).

---

## Agent 1: Interview Prep Agent

### Task 1: InterviewPrepSession + MockInterviewMessage models + migration 014

**Files:**
- Create: `backend/app/models/interview.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/014_interview_prep.py`

**Step 1: Create the interview model file**

Create `backend/app/models/interview.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InterviewPrepSession(TimestampMixin, Base):
    __tablename__ = "interview_prep_sessions"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prep_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "company_qa" | "behavioral" | "technical" | "culture_fit" | "salary_negotiation" | "mock_interview"
    content: Mapped[dict | None] = mapped_column(JSONB)
    # For company_qa: {questions: [{q, a, category}], tips: [str]}
    # For behavioral: {stories: [{situation, task, action, result, question}]}
    # For technical: {topics: [{name, questions: [{q, a, difficulty}]}]}
    # For culture_fit: {values: [str], alignment_tips: [str], questions: [{q, suggested_answer}]}
    # For salary_negotiation: {range: {min, max, median}, talking_points: [str], counter_strategies: [str]}
    # For mock_interview: {interview_type: str, status: "in_progress"|"completed", score: float|null}
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # "pending" | "generating" | "completed" | "failed"
    error: Mapped[str | None] = mapped_column(Text)

    # Relationships
    messages: Mapped[list["MockInterviewMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="MockInterviewMessage.turn_number"
    )


class MockInterviewMessage(TimestampMixin, Base):
    __tablename__ = "mock_interview_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_prep_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "interviewer" | "candidate" | "feedback"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback: Mapped[dict | None] = mapped_column(JSONB)
    # For feedback role: {score: float, strengths: [str], improvements: [str]}

    # Relationships
    session: Mapped["InterviewPrepSession"] = relationship(back_populates="messages")
```

**Step 2: Register models in `__init__.py`**

Add to `backend/app/models/__init__.py`:
```python
from app.models.interview import InterviewPrepSession, MockInterviewMessage
```
And add both to `__all__`.

**Step 3: Create migration 014**

Create `backend/alembic/versions/014_interview_prep.py`:
- Create `interview_prep_sessions` table with indexes on `(candidate_id, company_id)` and `status`
- Create `mock_interview_messages` table with index on `session_id`

**Step 4: Run migration and verify**

```bash
cd jobhunter/backend && alembic upgrade head
```

**Step 5: Commit**

```bash
git add backend/app/models/interview.py backend/app/models/__init__.py backend/alembic/versions/014_interview_prep.py
git commit -m "feat(interview): add InterviewPrepSession + MockInterviewMessage models"
```

---

### Task 2: Interview Prep schemas

**Files:**
- Create: `backend/app/schemas/interview.py`

**Step 1: Create schemas**

Create `backend/app/schemas/interview.py`:

```python
from pydantic import BaseModel


class InterviewPrepRequest(BaseModel):
    company_id: str
    prep_type: str  # "company_qa" | "behavioral" | "technical" | "culture_fit" | "salary_negotiation"


class MockInterviewStartRequest(BaseModel):
    company_id: str
    interview_type: str  # "behavioral" | "technical" | "mixed"


class MockInterviewReplyRequest(BaseModel):
    session_id: str
    answer: str


class MockInterviewEndRequest(BaseModel):
    session_id: str


class MockMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    turn_number: int
    feedback: dict | None = None

    model_config = {"from_attributes": True}


class InterviewPrepSessionResponse(BaseModel):
    id: str
    company_id: str
    prep_type: str
    content: dict | None = None
    status: str
    error: str | None = None
    messages: list[MockMessageResponse] = []

    model_config = {"from_attributes": True}


class InterviewPrepListResponse(BaseModel):
    sessions: list[InterviewPrepSessionResponse]
    total: int
```

**Step 2: Commit**

```bash
git add backend/app/schemas/interview.py
git commit -m "feat(interview): add Pydantic schemas"
```

---

### Task 3: Interview Prep LangGraph pipeline

**Files:**
- Create: `backend/app/graphs/interview_prep.py`

**Step 1: Create the pipeline**

Create `backend/app/graphs/interview_prep.py`:

```python
"""LangGraph interview prep pipeline.

5-node StateGraph:
  load_context -> generate_prep -> validate -> notify -> END
  (mark_failed on any error)
"""

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

# --- Prompts ---

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
        "Generate culture-fit preparation: company values alignment, questions to expect about culture fit, "
        "and suggested answers that demonstrate genuine alignment."
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
                        "suggested_answer": {"type": "string"},
                        "category": {"type": "string"},
                    },
                    "required": ["question", "suggested_answer", "category"],
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
                        "name": {"type": "string"},
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
                    "required": ["name", "questions"],
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
            "values": {"type": "array", "items": {"type": "string"}},
            "alignment_tips": {"type": "array", "items": {"type": "string"}},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "suggested_answer": {"type": "string"},
                    },
                    "required": ["question", "suggested_answer"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["values", "alignment_tips", "questions"],
        "additionalProperties": False,
    },
    "salary_negotiation": {
        "type": "object",
        "properties": {
            "range": {
                "type": "object",
                "properties": {
                    "min": {"type": "string"},
                    "max": {"type": "string"},
                    "median": {"type": "string"},
                },
                "required": ["min", "max", "median"],
                "additionalProperties": False,
            },
            "talking_points": {"type": "array", "items": {"type": "string"}},
            "counter_strategies": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["range", "talking_points", "counter_strategies"],
        "additionalProperties": False,
    },
}


# --- State ---

class InterviewPrepState(TypedDict):
    candidate_id: str
    company_id: str
    prep_type: str
    session_id: str | None
    context: dict | None
    content: dict | None
    status: str  # "pending" | "generating" | "completed" | "failed"
    error: str | None


# --- Nodes ---

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

    import json
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


# --- Routing ---

def _check_error(state: InterviewPrepState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


# --- Graph ---

def build_interview_prep_pipeline() -> StateGraph:
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


def get_interview_prep_pipeline(checkpointer=None):
    from app.graphs.resume_pipeline import _checkpointer as shared
    return _builder.compile(checkpointer=checkpointer or shared)


def get_interview_prep_pipeline_no_checkpointer():
    return _builder.compile()
```

**Step 2: Commit**

```bash
git add backend/app/graphs/interview_prep.py
git commit -m "feat(interview): add LangGraph interview prep pipeline"
```

---

### Task 4: Interview Prep API router

**Files:**
- Create: `backend/app/api/interview.py`
- Modify: `backend/app/main.py`

**Step 1: Create the API router**

Create `backend/app/api/interview.py`:

```python
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_current_candidate, get_db, get_openai
from app.models.candidate import Candidate, CandidateDNA
from app.models.company import Company
from app.models.interview import InterviewPrepSession, MockInterviewMessage
from app.schemas.interview import (
    InterviewPrepListResponse,
    InterviewPrepRequest,
    InterviewPrepSessionResponse,
    MockInterviewEndRequest,
    MockInterviewReplyRequest,
    MockInterviewStartRequest,
    MockMessageResponse,
)
from app.rate_limit import check_rate_limit

logger = structlog.get_logger()

router = APIRouter(prefix="/interview-prep", tags=["interview-prep"])

VALID_PREP_TYPES = {"company_qa", "behavioral", "technical", "culture_fit", "salary_negotiation"}
VALID_INTERVIEW_TYPES = {"behavioral", "technical", "mixed"}

MOCK_SYSTEM_PROMPT = (
    "You are a professional interviewer conducting a {interview_type} interview for {company_name} ({industry}). "
    "The candidate's background: {candidate_summary}. "
    "Ask one question at a time. After the candidate answers, provide brief feedback, then ask the next question. "
    "Be realistic but encouraging. Adapt difficulty based on responses."
)

MOCK_FEEDBACK_PROMPT = (
    "You are an interview coach. Review this mock interview transcript and provide final feedback.\n\n"
    "Transcript:\n{transcript}\n\n"
    "Provide a JSON response with: overall_score (0-10), strengths (list), improvements (list), summary (string)."
)

MOCK_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {"type": "number"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["overall_score", "strengths", "improvements", "summary"],
    "additionalProperties": False,
}


async def _run_interview_prep(candidate_id: str, company_id: str, prep_type: str):
    """Background task to run the interview prep pipeline."""
    from app.graphs.interview_prep import get_interview_prep_pipeline

    thread_id = f"interview-prep-{uuid.uuid4()}"
    state = {
        "candidate_id": candidate_id,
        "company_id": company_id,
        "prep_type": prep_type,
        "session_id": None,
        "context": None,
        "content": None,
        "status": "pending",
        "error": None,
    }

    try:
        graph = get_interview_prep_pipeline()
        await graph.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
    except Exception as e:
        logger.error("interview_prep_bg_failed", error=str(e))


@router.post("/generate", response_model=InterviewPrepSessionResponse)
async def generate_prep(
    req: InterviewPrepRequest,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Generate interview prep material for a company."""
    await check_rate_limit(str(candidate.id), "interview_prep", 20)

    if req.prep_type not in VALID_PREP_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid prep_type. Must be one of: {VALID_PREP_TYPES}")

    # Verify company belongs to candidate
    result = await db.execute(
        select(Company).where(Company.id == uuid.UUID(req.company_id), Company.candidate_id == candidate.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Company not found")

    background_tasks.add_task(_run_interview_prep, str(candidate.id), req.company_id, req.prep_type)

    return InterviewPrepSessionResponse(
        id="pending", company_id=req.company_id, prep_type=req.prep_type, status="pending"
    )


@router.get("/sessions", response_model=InterviewPrepListResponse)
async def list_sessions(
    company_id: str | None = None,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """List interview prep sessions for the authenticated candidate."""
    query = (
        select(InterviewPrepSession)
        .where(InterviewPrepSession.candidate_id == candidate.id)
        .options(selectinload(InterviewPrepSession.messages))
        .order_by(InterviewPrepSession.created_at.desc())
    )
    if company_id:
        query = query.where(InterviewPrepSession.company_id == uuid.UUID(company_id))

    result = await db.execute(query)
    sessions = result.scalars().all()

    count_result = await db.execute(
        select(func.count(InterviewPrepSession.id)).where(InterviewPrepSession.candidate_id == candidate.id)
    )
    total = count_result.scalar() or 0

    return InterviewPrepListResponse(
        sessions=[InterviewPrepSessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.get("/sessions/{session_id}", response_model=InterviewPrepSessionResponse)
async def get_session(
    session_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific interview prep session with messages."""
    result = await db.execute(
        select(InterviewPrepSession)
        .where(
            InterviewPrepSession.id == uuid.UUID(session_id),
            InterviewPrepSession.candidate_id == candidate.id,
        )
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return InterviewPrepSessionResponse.model_validate(session)


@router.post("/mock/start", response_model=InterviewPrepSessionResponse)
async def start_mock_interview(
    req: MockInterviewStartRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Start a mock interview session."""
    await check_rate_limit(str(candidate.id), "mock_interview", 10)

    if req.interview_type not in VALID_INTERVIEW_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid interview_type. Must be one of: {VALID_INTERVIEW_TYPES}")

    # Verify company
    result = await db.execute(
        select(Company).where(Company.id == uuid.UUID(req.company_id), Company.candidate_id == candidate.id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Load DNA
    dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate.id))
    dna = dna_result.scalar_one_or_none()

    # Create session
    session = InterviewPrepSession(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        company_id=company.id,
        prep_type="mock_interview",
        content={"interview_type": req.interview_type, "status": "in_progress", "score": None},
        status="completed",  # Session is "live" — no background generation needed
    )
    db.add(session)

    # Generate first interviewer question
    system_prompt = MOCK_SYSTEM_PROMPT.format(
        interview_type=req.interview_type,
        company_name=company.name,
        industry=company.industry or "Technology",
        candidate_summary=dna.experience_summary if dna else "Software engineer",
    )

    client = get_openai()
    first_question = await client.chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Begin the interview. Ask your first question."},
    ])

    msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="interviewer",
        content=first_question,
        turn_number=1,
    )
    db.add(msg)
    await db.commit()

    # Reload with messages
    result = await db.execute(
        select(InterviewPrepSession)
        .where(InterviewPrepSession.id == session.id)
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one()

    return InterviewPrepSessionResponse.model_validate(session)


@router.post("/mock/reply", response_model=MockMessageResponse)
async def reply_mock_interview(
    req: MockInterviewReplyRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Reply to a mock interview question. Returns interviewer's next response."""
    result = await db.execute(
        select(InterviewPrepSession)
        .where(
            InterviewPrepSession.id == uuid.UUID(req.session_id),
            InterviewPrepSession.candidate_id == candidate.id,
            InterviewPrepSession.prep_type == "mock_interview",
        )
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Mock interview session not found")

    content_data = session.content or {}
    if content_data.get("status") == "completed":
        raise HTTPException(status_code=400, detail="This mock interview is already completed")

    # Save candidate's answer
    max_turn = max((m.turn_number for m in session.messages), default=0)
    candidate_msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="candidate",
        content=req.answer,
        turn_number=max_turn + 1,
    )
    db.add(candidate_msg)

    # Build chat history for context
    dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate.id))
    dna = dna_result.scalar_one_or_none()

    company_result = await db.execute(select(Company).where(Company.id == session.company_id))
    company = company_result.scalar_one()

    system_prompt = MOCK_SYSTEM_PROMPT.format(
        interview_type=content_data.get("interview_type", "mixed"),
        company_name=company.name,
        industry=company.industry or "Technology",
        candidate_summary=dna.experience_summary if dna else "Software engineer",
    )

    messages = [{"role": "system", "content": system_prompt}]
    for m in session.messages:
        role = "assistant" if m.role == "interviewer" else "user"
        messages.append({"role": role, "content": m.content})
    messages.append({"role": "user", "content": req.answer})

    client = get_openai()
    response = await client.chat(messages)

    interviewer_msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="interviewer",
        content=response,
        turn_number=max_turn + 2,
    )
    db.add(interviewer_msg)
    await db.commit()

    return MockMessageResponse.model_validate(interviewer_msg)


@router.post("/mock/end", response_model=InterviewPrepSessionResponse)
async def end_mock_interview(
    req: MockInterviewEndRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """End a mock interview and get final feedback."""
    result = await db.execute(
        select(InterviewPrepSession)
        .where(
            InterviewPrepSession.id == uuid.UUID(req.session_id),
            InterviewPrepSession.candidate_id == candidate.id,
            InterviewPrepSession.prep_type == "mock_interview",
        )
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Mock interview session not found")

    # Build transcript
    transcript = "\n".join(
        f"{'Interviewer' if m.role == 'interviewer' else 'Candidate'}: {m.content}"
        for m in session.messages
    )

    prompt = MOCK_FEEDBACK_PROMPT.format(transcript=transcript)
    client = get_openai()
    feedback = await client.parse_structured(prompt, "", MOCK_FEEDBACK_SCHEMA)

    # Save feedback as final message
    max_turn = max((m.turn_number for m in session.messages), default=0)
    feedback_msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="feedback",
        content=feedback.get("summary", "Interview complete."),
        turn_number=max_turn + 1,
        feedback=feedback,
    )
    db.add(feedback_msg)

    # Update session
    content_data = session.content or {}
    content_data["status"] = "completed"
    content_data["score"] = feedback.get("overall_score")
    session.content = content_data
    await db.commit()

    # Reload
    result = await db.execute(
        select(InterviewPrepSession)
        .where(InterviewPrepSession.id == session.id)
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one()

    return InterviewPrepSessionResponse.model_validate(session)
```

**Step 2: Register router in main.py**

Add to `backend/app/main.py` after the existing router imports:
```python
from app.api.interview import router as interview_router  # noqa: E402
```
And:
```python
app.include_router(interview_router, prefix=settings.API_V1_PREFIX)
```

**Step 3: Commit**

```bash
git add backend/app/api/interview.py backend/app/main.py
git commit -m "feat(interview): add API router with prep generation + mock interviews"
```

---

### Task 5: Interview Prep auto-triggers

**Files:**
- Modify: `backend/app/services/company_service.py` (after company approve)
- Modify: `backend/app/graphs/outreach.py` (after reply detection — handled via webhook already)

**Step 1: Auto-trigger on company approval**

In `backend/app/services/company_service.py`, find the `approve_company` function. After the company status is set to "approved" and committed, add:

```python
# Auto-trigger interview prep generation
from app.graphs.interview_prep import get_interview_prep_pipeline
import uuid as _uuid

for prep_type in ("company_qa", "behavioral", "technical"):
    try:
        thread_id = f"interview-auto-{_uuid.uuid4()}"
        graph = get_interview_prep_pipeline()
        await graph.ainvoke(
            {
                "candidate_id": str(company.candidate_id),
                "company_id": str(company.id),
                "prep_type": prep_type,
                "session_id": None,
                "context": None,
                "content": None,
                "status": "pending",
                "error": None,
            },
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as e:
        logger.warning("auto_interview_prep_failed", prep_type=prep_type, error=str(e))
```

**Note:** This should be wrapped in a BackgroundTasks call at the API layer rather than blocking the approve response. Modify `backend/app/api/companies.py` approve endpoint to pass BackgroundTasks and call an async helper.

**Step 2: Commit**

```bash
git add backend/app/services/company_service.py backend/app/api/companies.py
git commit -m "feat(interview): auto-trigger prep on company approval"
```

---

### Task 6: Interview Prep tests

**Files:**
- Create: `backend/tests/test_interview_prep.py`
- Modify: `backend/tests/conftest.py`

**Step 1: Add interview prep schema detection to OpenAIStub**

In `backend/tests/conftest.py`, add to `OpenAIStub.parse_structured()`:

```python
# Interview prep schemas
if "questions" in schema_keys and "tips" in schema_keys:
    return {
        "questions": [
            {"question": "Tell me about your experience", "suggested_answer": "I have 5 years...", "category": "behavioral"},
        ],
        "tips": ["Research the company culture", "Prepare STAR stories"],
    }
if "stories" in schema_keys:
    return {
        "stories": [
            {"question": "Tell me about a challenge", "situation": "At TestCo...", "task": "I needed to...",
             "action": "I decided to...", "result": "This led to..."},
        ],
    }
if "topics" in schema_keys:
    return {
        "topics": [
            {"name": "System Design", "questions": [
                {"question": "Design a URL shortener", "answer": "I would use...", "difficulty": "medium"},
            ]},
        ],
    }
if "values" in schema_keys and "alignment_tips" in schema_keys:
    return {
        "values": ["Innovation", "Collaboration"],
        "alignment_tips": ["Show passion for learning"],
        "questions": [{"question": "How do you handle conflict?", "suggested_answer": "I approach..."}],
    }
if "range" in schema_keys and "talking_points" in schema_keys:
    return {
        "range": {"min": "120k", "max": "180k", "median": "150k"},
        "talking_points": ["Market data supports this range"],
        "counter_strategies": ["Emphasize total compensation"],
    }
# Mock interview feedback
if "overall_score" in schema_keys and "strengths" in schema_keys:
    return {
        "overall_score": 7.5,
        "strengths": ["Clear communication"],
        "improvements": ["More specific examples"],
        "summary": "Good performance overall.",
    }
```

**Step 2: Create test file**

Create `backend/tests/test_interview_prep.py`:

```python
import pytest
import uuid

from app.config import settings
from app.graphs.interview_prep import build_interview_prep_pipeline


class TestInterviewPrepGraph:
    def test_graph_builds(self):
        builder = build_interview_prep_pipeline()
        graph = builder.compile()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        builder = build_interview_prep_pipeline()
        graph = builder.compile()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {"load_context", "generate_prep", "save_and_notify", "mark_failed"}
        assert expected.issubset(node_names)


class TestInterviewPrepAPI:
    @pytest.mark.asyncio
    async def test_generate_prep_endpoint(self, client, auth_headers, db_session):
        # First seed DNA and a company
        from tests.conftest import seed_candidate_dna
        await seed_candidate_dna(db_session, client, auth_headers)

        # Get candidate ID
        me = await client.get(f"{settings.API_V1_PREFIX}/auth/me", headers=auth_headers)
        candidate_id = me.json()["id"]

        # Create a company
        from app.models.company import Company
        company = Company(
            id=uuid.uuid4(), candidate_id=uuid.UUID(candidate_id),
            name="TestCo", domain="testco.com", status="approved", research_status="completed",
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.post(
            f"{settings.API_V1_PREFIX}/interview-prep/generate",
            json={"company_id": str(company.id), "prep_type": "company_qa"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prep_type"] == "company_qa"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, client, auth_headers):
        resp = await client.get(
            f"{settings.API_V1_PREFIX}/interview-prep/sessions",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_mock_start_endpoint(self, client, auth_headers, db_session):
        from tests.conftest import seed_candidate_dna
        await seed_candidate_dna(db_session, client, auth_headers)

        me = await client.get(f"{settings.API_V1_PREFIX}/auth/me", headers=auth_headers)
        candidate_id = me.json()["id"]

        from app.models.company import Company
        company = Company(
            id=uuid.uuid4(), candidate_id=uuid.UUID(candidate_id),
            name="MockCo", domain="mockco.com", status="approved", research_status="completed",
        )
        db_session.add(company)
        await db_session.commit()

        resp = await client.post(
            f"{settings.API_V1_PREFIX}/interview-prep/mock/start",
            json={"company_id": str(company.id), "interview_type": "behavioral"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prep_type"] == "mock_interview"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "interviewer"

    @pytest.mark.asyncio
    async def test_invalid_prep_type(self, client, auth_headers):
        resp = await client.post(
            f"{settings.API_V1_PREFIX}/interview-prep/generate",
            json={"company_id": str(uuid.uuid4()), "prep_type": "invalid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
```

**Step 3: Run tests**

```bash
cd jobhunter/backend && python -m pytest tests/test_interview_prep.py -v
```

**Step 4: Commit**

```bash
git add backend/tests/test_interview_prep.py backend/tests/conftest.py
git commit -m "feat(interview): add tests for interview prep pipeline and API"
```

---

### Task 7: Interview Prep frontend page

**Files:**
- Create: `frontend/src/app/(dashboard)/interview-prep/page.tsx`
- Create: `frontend/src/lib/api/interview.ts`
- Create: `frontend/src/lib/hooks/use-interview.ts`
- Modify: `frontend/src/components/layout/sidebar.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/hooks/use-websocket.ts`

**Step 1: Add TypeScript types**

Add to `frontend/src/lib/types.ts`:

```typescript
// Interview Prep
export interface MockMessageResponse {
  id: string;
  role: string;
  content: string;
  turn_number: number;
  feedback: Record<string, unknown> | null;
}

export interface InterviewPrepSessionResponse {
  id: string;
  company_id: string;
  prep_type: string;
  content: Record<string, unknown> | null;
  status: string;
  error: string | null;
  messages: MockMessageResponse[];
}

export interface InterviewPrepListResponse {
  sessions: InterviewPrepSessionResponse[];
  total: number;
}
```

**Step 2: Create API module**

Create `frontend/src/lib/api/interview.ts`:

```typescript
import { api } from "./client";
import type { InterviewPrepSessionResponse, InterviewPrepListResponse } from "@/lib/types";

export async function generatePrep(companyId: string, prepType: string) {
  const { data } = await api.post<InterviewPrepSessionResponse>("/interview-prep/generate", {
    company_id: companyId,
    prep_type: prepType,
  });
  return data;
}

export async function listSessions(companyId?: string) {
  const params = companyId ? { company_id: companyId } : {};
  const { data } = await api.get<InterviewPrepListResponse>("/interview-prep/sessions", { params });
  return data;
}

export async function getSession(sessionId: string) {
  const { data } = await api.get<InterviewPrepSessionResponse>(`/interview-prep/sessions/${sessionId}`);
  return data;
}

export async function startMockInterview(companyId: string, interviewType: string) {
  const { data } = await api.post<InterviewPrepSessionResponse>("/interview-prep/mock/start", {
    company_id: companyId,
    interview_type: interviewType,
  });
  return data;
}

export async function replyMockInterview(sessionId: string, answer: string) {
  const { data } = await api.post<{ id: string; role: string; content: string; turn_number: number; feedback: unknown }>("/interview-prep/mock/reply", {
    session_id: sessionId,
    answer,
  });
  return data;
}

export async function endMockInterview(sessionId: string) {
  const { data } = await api.post<InterviewPrepSessionResponse>("/interview-prep/mock/end", {
    session_id: sessionId,
  });
  return data;
}
```

**Step 3: Create React Query hooks**

Create `frontend/src/lib/hooks/use-interview.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as interviewApi from "@/lib/api/interview";
import { toastError } from "@/lib/api/error-utils";
import { toast } from "sonner";

export function useInterviewSessions(companyId?: string) {
  return useQuery({
    queryKey: ["interview-sessions", companyId],
    queryFn: () => interviewApi.listSessions(companyId),
  });
}

export function useInterviewSession(sessionId: string | null) {
  return useQuery({
    queryKey: ["interview-session", sessionId],
    queryFn: () => interviewApi.getSession(sessionId!),
    enabled: !!sessionId,
  });
}

export function useGeneratePrep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ companyId, prepType }: { companyId: string; prepType: string }) =>
      interviewApi.generatePrep(companyId, prepType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interview-sessions"] });
      toast.success("Generating interview prep...");
    },
    onError: (err) => toastError(err, "Failed to generate prep"),
  });
}

export function useStartMockInterview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ companyId, interviewType }: { companyId: string; interviewType: string }) =>
      interviewApi.startMockInterview(companyId, interviewType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interview-sessions"] });
    },
    onError: (err) => toastError(err, "Failed to start mock interview"),
  });
}

export function useReplyMockInterview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, answer }: { sessionId: string; answer: string }) =>
      interviewApi.replyMockInterview(sessionId, answer),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["interview-session", vars.sessionId] });
    },
    onError: (err) => toastError(err, "Failed to send reply"),
  });
}

export function useEndMockInterview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => interviewApi.endMockInterview(sessionId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["interview-sessions"] });
      qc.invalidateQueries({ queryKey: ["interview-session", data.id] });
      toast.success("Mock interview completed!");
    },
    onError: (err) => toastError(err, "Failed to end interview"),
  });
}
```

**Step 4: Add sidebar nav item**

In `frontend/src/components/layout/sidebar.tsx`, add `GraduationCap` to the lucide-react imports and add to `navItems` after "Outreach":

```typescript
{ href: "/interview-prep", label: "Interview Prep", icon: GraduationCap },
```

**Step 5: Add WebSocket event handler**

In `frontend/src/lib/hooks/use-websocket.ts`, add to the event handler:
```typescript
case "interview_prep_completed":
case "interview_prep_failed":
  queryClient.invalidateQueries({ queryKey: ["interview-sessions"] });
  break;
```

**Step 6: Create the page**

Create `frontend/src/app/(dashboard)/interview-prep/page.tsx`:
- Company selector dropdown (from approved companies)
- Prep type tabs: Company Q&A, Behavioral, Technical, Culture Fit, Salary
- Generate button per prep type
- Session list showing generated content (cards)
- Mock Interview tab with start button, chat-like UI, end + get feedback button
- Polling for sessions in "generating" status (refetchInterval: 3000)

This is a substantial React component. Implementation should follow the exact same patterns as the existing companies page (useQuery hooks, shadcn Card/Tabs/Button, loading skeletons, toast notifications).

**Step 7: Commit**

```bash
git add frontend/src/app/\(dashboard\)/interview-prep/page.tsx frontend/src/lib/api/interview.ts frontend/src/lib/hooks/use-interview.ts frontend/src/components/layout/sidebar.tsx frontend/src/lib/types.ts frontend/src/lib/hooks/use-websocket.ts
git commit -m "feat(interview): add frontend interview prep page with mock interviews"
```

---

### Interview Prep Agent — Verification

1. `pytest tests/test_interview_prep.py -v` — all tests pass
2. `pytest tests/ -v` — full suite passes (no regressions)
3. Graph has 4 nodes: load_context, generate_prep, save_and_notify, mark_failed
4. `POST /interview-prep/generate` triggers pipeline, creates InterviewPrepSession
5. `GET /interview-prep/sessions` lists sessions for candidate
6. `POST /interview-prep/mock/start` creates mock session with first question
7. `POST /interview-prep/mock/reply` saves answer, returns interviewer response
8. `POST /interview-prep/mock/end` generates feedback with score
9. Sidebar shows "Interview Prep" nav item
10. Frontend page loads, generates prep, runs mock interviews

---

## Agent 2: Apply Agent

### Task 8: JobPosting model + migration 015

**Files:**
- Create: `backend/app/models/job_posting.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/015_job_postings.py`

**Step 1: Create the model**

Create `backend/app/models/job_posting.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class JobPosting(TimestampMixin, Base):
    __tablename__ = "job_postings"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(1000))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_requirements: Mapped[dict | None] = mapped_column(JSONB)
    # {required_skills: [str], preferred_skills: [str], experience_years: int,
    #  education: str, responsibilities: [str], benefits: [str]}
    ats_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # "pending" | "analyzed" | "applied" | "failed"
```

**Step 2: Register in `__init__.py`**

Add `from app.models.job_posting import JobPosting` and add to `__all__`.

**Step 3: Create migration 015**

Create `backend/alembic/versions/015_job_postings.py`:
- Create `job_postings` table with indexes on `candidate_id`, `company_id`, `status`

**Step 4: Commit**

```bash
git add backend/app/models/job_posting.py backend/app/models/__init__.py backend/alembic/versions/015_job_postings.py
git commit -m "feat(apply): add JobPosting model + migration"
```

---

### Task 9: Apply Agent schemas

**Files:**
- Create: `backend/app/schemas/apply.py`

**Step 1: Create schemas**

Create `backend/app/schemas/apply.py`:

```python
from pydantic import BaseModel


class JobPostingCreateRequest(BaseModel):
    title: str
    company_name: str | None = None
    company_id: str | None = None
    url: str | None = None
    raw_text: str  # Pasted job description


class ApplyAnalysisResponse(BaseModel):
    id: str
    job_posting_id: str
    readiness_score: float  # 0-100
    resume_tips: list[dict]  # [{section, tip, priority}]
    cover_letter: str
    ats_keywords: list[str]
    missing_skills: list[str]
    matching_skills: list[str]
    status: str

    model_config = {"from_attributes": True}


class JobPostingResponse(BaseModel):
    id: str
    title: str
    company_name: str | None = None
    company_id: str | None = None
    url: str | None = None
    status: str
    ats_keywords: list[str] | None = None
    parsed_requirements: dict | None = None
    created_at: str

    model_config = {"from_attributes": True}


class JobPostingListResponse(BaseModel):
    postings: list[JobPostingResponse]
    total: int
```

**Step 2: Commit**

```bash
git add backend/app/schemas/apply.py
git commit -m "feat(apply): add Pydantic schemas"
```

---

### Task 10: Apply LangGraph pipeline

**Files:**
- Create: `backend/app/graphs/apply_pipeline.py`

**Step 1: Create the pipeline**

Create `backend/app/graphs/apply_pipeline.py`:

```python
"""LangGraph apply agent pipeline.

6-node StateGraph:
  parse_job -> match_skills -> generate_tips -> generate_cover_letter -> save_and_notify -> END
"""

import uuid
from typing_extensions import TypedDict

import structlog
from langgraph.graph import StateGraph, START, END
from sqlalchemy import select

from app.infrastructure import database as _db_mod
from app.dependencies import get_openai
from app.models.candidate import CandidateDNA, Skill
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.infrastructure.websocket_manager import ws_manager

logger = structlog.get_logger()

# --- Prompts ---

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


# --- State ---

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
    context: dict | None  # Company/candidate data for prompts
    status: str
    error: str | None


# --- Nodes ---

async def parse_job_node(state: ApplyState) -> dict:
    """Parse job posting and extract requirements."""
    job_posting_id = uuid.UUID(state["job_posting_id"])
    candidate_id = uuid.UUID(state["candidate_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(JobPosting).where(JobPosting.id == job_posting_id))
        posting = result.scalar_one_or_none()
        if not posting:
            return {"status": "failed", "error": f"JobPosting {job_posting_id} not found"}

        # Load candidate data
        dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        dna = dna_result.scalar_one_or_none()

        skills_result = await db.execute(select(Skill).where(Skill.candidate_id == candidate_id))
        skills = skills_result.scalars().all()

        # Load company if linked
        company_name = posting.company_name or "Unknown"
        why_hire_me = ""
        if posting.company_id:
            company_result = await db.execute(select(Company).where(Company.id == posting.company_id))
            company = company_result.scalar_one_or_none()
            if company:
                company_name = company.name
                from app.models.company import CompanyDossier
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

    matching = list(candidate_skills & all_job_skills)
    missing = list(all_required - candidate_skills)

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
        why_hire_me=context.get("why_hire_me", "Strong candidate fit"),
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


# --- Routing ---

def _check_error(state: ApplyState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


# --- Graph ---

def build_apply_pipeline() -> StateGraph:
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


def get_apply_pipeline(checkpointer=None):
    from app.graphs.resume_pipeline import _checkpointer as shared
    return _builder.compile(checkpointer=checkpointer or shared)


def get_apply_pipeline_no_checkpointer():
    return _builder.compile()
```

**Step 2: Commit**

```bash
git add backend/app/graphs/apply_pipeline.py
git commit -m "feat(apply): add LangGraph apply pipeline with tips + cover letter"
```

---

### Task 11: Apply Agent API router

**Files:**
- Create: `backend/app/api/apply.py`
- Modify: `backend/app/main.py`

**Step 1: Create router**

Create `backend/app/api/apply.py`:

```python
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.models.job_posting import JobPosting
from app.schemas.apply import (
    ApplyAnalysisResponse,
    JobPostingCreateRequest,
    JobPostingListResponse,
    JobPostingResponse,
)
from app.rate_limit import check_rate_limit

logger = structlog.get_logger()

router = APIRouter(prefix="/apply", tags=["apply"])


async def _run_apply_pipeline(candidate_id: str, job_posting_id: str):
    from app.graphs.apply_pipeline import get_apply_pipeline

    thread_id = f"apply-{uuid.uuid4()}"
    state = {
        "candidate_id": candidate_id,
        "job_posting_id": job_posting_id,
        "parsed_requirements": None,
        "candidate_skills": None,
        "matching_skills": None,
        "missing_skills": None,
        "resume_tips": None,
        "readiness_score": None,
        "cover_letter": None,
        "ats_keywords": None,
        "context": None,
        "status": "pending",
        "error": None,
    }

    try:
        graph = get_apply_pipeline()
        result = await graph.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
        # Store analysis results in a way the API can retrieve them
        # The pipeline already saves parsed_requirements and ats_keywords to the JobPosting
        # We store the full analysis in Redis for retrieval
        from app.infrastructure.redis_client import get_redis
        import json
        redis = get_redis()
        analysis = {
            "job_posting_id": job_posting_id,
            "readiness_score": result.get("readiness_score", 0),
            "resume_tips": result.get("resume_tips", []),
            "cover_letter": result.get("cover_letter", ""),
            "ats_keywords": result.get("ats_keywords", []),
            "missing_skills": result.get("missing_skills", []),
            "matching_skills": result.get("matching_skills", []),
            "status": result.get("status", "completed"),
        }
        await redis.set(f"apply:analysis:{job_posting_id}", json.dumps(analysis), ex=86400 * 7)
    except Exception as e:
        logger.error("apply_pipeline_bg_failed", error=str(e))


@router.post("/analyze", response_model=JobPostingResponse)
async def analyze_job_posting(
    req: JobPostingCreateRequest,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Submit a job posting for analysis."""
    await check_rate_limit(str(candidate.id), "apply_analysis", 20)

    company_id = uuid.UUID(req.company_id) if req.company_id else None

    posting = JobPosting(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        company_id=company_id,
        title=req.title,
        company_name=req.company_name,
        url=req.url,
        raw_text=req.raw_text,
        status="pending",
    )
    db.add(posting)
    await db.commit()

    background_tasks.add_task(_run_apply_pipeline, str(candidate.id), str(posting.id))

    return JobPostingResponse.model_validate(posting)


@router.get("/postings", response_model=JobPostingListResponse)
async def list_postings(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """List job postings for the authenticated candidate."""
    result = await db.execute(
        select(JobPosting)
        .where(JobPosting.candidate_id == candidate.id)
        .order_by(JobPosting.created_at.desc())
    )
    postings = result.scalars().all()

    count_result = await db.execute(
        select(func.count(JobPosting.id)).where(JobPosting.candidate_id == candidate.id)
    )
    total = count_result.scalar() or 0

    return JobPostingListResponse(
        postings=[JobPostingResponse.model_validate(p) for p in postings],
        total=total,
    )


@router.get("/postings/{posting_id}/analysis", response_model=ApplyAnalysisResponse)
async def get_analysis(
    posting_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Get the analysis results for a job posting."""
    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == uuid.UUID(posting_id),
            JobPosting.candidate_id == candidate.id,
        )
    )
    posting = result.scalar_one_or_none()
    if not posting:
        raise HTTPException(status_code=404, detail="Job posting not found")

    if posting.status == "pending":
        raise HTTPException(status_code=202, detail="Analysis still in progress")

    # Retrieve from Redis
    from app.infrastructure.redis_client import get_redis
    import json
    redis = get_redis()
    cached = await redis.get(f"apply:analysis:{posting_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Analysis not found — may have expired")

    analysis = json.loads(cached)
    return ApplyAnalysisResponse(
        id=posting_id,
        job_posting_id=posting_id,
        readiness_score=analysis.get("readiness_score", 0),
        resume_tips=analysis.get("resume_tips", []),
        cover_letter=analysis.get("cover_letter", ""),
        ats_keywords=analysis.get("ats_keywords", []),
        missing_skills=analysis.get("missing_skills", []),
        matching_skills=analysis.get("matching_skills", []),
        status=analysis.get("status", "completed"),
    )
```

**Step 2: Register in main.py**

Add import and `app.include_router(apply_router, prefix=settings.API_V1_PREFIX)`.

**Step 3: Commit**

```bash
git add backend/app/api/apply.py backend/app/main.py
git commit -m "feat(apply): add API router with job posting analysis"
```

---

### Task 12: Apply Agent tests

**Files:**
- Create: `backend/tests/test_apply.py`
- Modify: `backend/tests/conftest.py`

**Step 1: Add apply schema detection to OpenAIStub**

In conftest.py `parse_structured()`, add:

```python
# Apply pipeline schemas
if "required_skills" in schema_keys and "ats_keywords" in schema_keys:
    return {
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "preferred_skills": ["Docker", "Kubernetes"],
        "experience_years": 3,
        "education": "BS Computer Science",
        "responsibilities": ["Build APIs", "Write tests"],
        "ats_keywords": ["Python", "REST API", "microservices", "PostgreSQL"],
    }
if "tips" in schema_keys and "readiness_score" in schema_keys:
    return {
        "tips": [
            {"section": "Skills", "tip": "Add PostgreSQL to your skills section", "priority": "high"},
            {"section": "Experience", "tip": "Highlight API development projects", "priority": "medium"},
        ],
        "readiness_score": 72.5,
    }
if "cover_letter" in schema_keys and len(schema_keys) == 1:
    return {"cover_letter": "Dear Hiring Manager,\n\nI am excited to apply..."}
```

**Step 2: Create test file**

Create `backend/tests/test_apply.py` with tests:
1. `test_graph_builds` — graph compiles
2. `test_graph_has_expected_nodes` — 6 nodes present
3. `test_analyze_endpoint` — POST /apply/analyze returns 200
4. `test_list_postings_empty` — GET /apply/postings returns empty list
5. `test_invalid_posting_not_found` — GET /apply/postings/{bad_id}/analysis returns 404

**Step 3: Run and commit**

```bash
cd jobhunter/backend && python -m pytest tests/test_apply.py -v
git add backend/tests/test_apply.py backend/tests/conftest.py
git commit -m "feat(apply): add tests for apply pipeline and API"
```

---

### Task 13: Apply Agent frontend page

**Files:**
- Create: `frontend/src/app/(dashboard)/apply/page.tsx`
- Create: `frontend/src/lib/api/apply.ts`
- Create: `frontend/src/lib/hooks/use-apply.ts`
- Modify: `frontend/src/components/layout/sidebar.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/hooks/use-websocket.ts`

**Step 1: Add types to `types.ts`**

```typescript
// Apply
export interface JobPostingResponse {
  id: string;
  title: string;
  company_name: string | null;
  company_id: string | null;
  url: string | null;
  status: string;
  ats_keywords: string[] | null;
  parsed_requirements: Record<string, unknown> | null;
  created_at: string;
}

export interface JobPostingListResponse {
  postings: JobPostingResponse[];
  total: number;
}

export interface ApplyAnalysisResponse {
  id: string;
  job_posting_id: string;
  readiness_score: number;
  resume_tips: { section: string; tip: string; priority: string }[];
  cover_letter: string;
  ats_keywords: string[];
  missing_skills: string[];
  matching_skills: string[];
  status: string;
}
```

**Step 2: Create API module** (`frontend/src/lib/api/apply.ts`)

Endpoints:
- `analyzeJobPosting(title, companyName, companyId, url, rawText)` → POST `/apply/analyze`
- `listPostings()` → GET `/apply/postings`
- `getAnalysis(postingId)` → GET `/apply/postings/{id}/analysis`

**Step 3: Create hooks** (`frontend/src/lib/hooks/use-apply.ts`)

- `useJobPostings()` — queryKey: `["job-postings"]`
- `useApplyAnalysis(postingId)` — queryKey: `["apply-analysis", postingId]`, polling while status=pending
- `useAnalyzeJob()` — mutation, invalidates `["job-postings"]`

**Step 4: Add sidebar nav item**

Add `FileCheck` from lucide-react, add to navItems after "Interview Prep":
```typescript
{ href: "/apply", label: "Apply", icon: FileCheck },
```

**Step 5: Add WebSocket handlers**

```typescript
case "apply_analysis_completed":
case "apply_analysis_failed":
  queryClient.invalidateQueries({ queryKey: ["job-postings"] });
  queryClient.invalidateQueries({ queryKey: ["apply-analysis"] });
  break;
```

**Step 6: Create the page**

Create `frontend/src/app/(dashboard)/apply/page.tsx`:
- Job posting input form (title, company name, URL, paste description textarea)
- Submit button → runs analysis in background
- Postings list with status badges
- Analysis view (when clicked):
  - Readiness score gauge/progress bar
  - Resume tips list (grouped by priority: high → medium → low)
  - ATS keywords badges (matching = green, missing = red)
  - Cover letter with copy button
  - Matching vs missing skills comparison

**Step 7: Commit**

```bash
git add frontend/src/app/\(dashboard\)/apply/page.tsx frontend/src/lib/api/apply.ts frontend/src/lib/hooks/use-apply.ts frontend/src/components/layout/sidebar.tsx frontend/src/lib/types.ts frontend/src/lib/hooks/use-websocket.ts
git commit -m "feat(apply): add frontend apply page with job analysis"
```

---

### Apply Agent — Verification

1. `pytest tests/test_apply.py -v` — all tests pass
2. `pytest tests/ -v` — full suite passes
3. Graph has 6 nodes: parse_job, match_skills, generate_tips, generate_cover_letter, save_and_notify, mark_failed
4. `POST /apply/analyze` creates JobPosting and triggers pipeline
5. `GET /apply/postings` lists postings
6. `GET /apply/postings/{id}/analysis` returns tips, cover letter, scores
7. Frontend page allows pasting job descriptions and viewing analysis

---

## Agent 3: Analytics Agent

### Task 14: AnalyticsInsight model + migration 016

**Files:**
- Create: `backend/app/models/insight.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/016_analytics_insights.py`

**Step 1: Create model**

Create `backend/app/models/insight.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AnalyticsInsight(TimestampMixin, Base):
    __tablename__ = "analytics_insights"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "pipeline_health" | "outreach_effectiveness" | "skill_gap" | "market_positioning" | "recommendation"
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    # "info" | "warning" | "success" | "action_needed"
    data: Mapped[dict | None] = mapped_column(JSONB)
    # Structured data backing this insight (charts, numbers, etc.)
    is_read: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

**Step 2: Register and create migration**

Same pattern as previous models. Add to `__init__.py` and create migration 016.

**Step 3: Commit**

```bash
git add backend/app/models/insight.py backend/app/models/__init__.py backend/alembic/versions/016_analytics_insights.py
git commit -m "feat(analytics): add AnalyticsInsight model + migration"
```

---

### Task 15: Analytics LangGraph pipeline

**Files:**
- Create: `backend/app/graphs/analytics_pipeline.py`

**Step 1: Create the pipeline**

Create `backend/app/graphs/analytics_pipeline.py`:

5-node pipeline:
1. `gather_data` — Load all pipeline stats, outreach stats, funnel, skill data from existing `analytics_service.py` functions
2. `generate_insights` — Call OpenAI with all the data to produce AI-generated insights (structured output)
3. `save_insights` — Save `AnalyticsInsight` records to DB
4. `notify` — WebSocket broadcast + optional email digest
5. `mark_failed` — Error handler

State schema:
```python
class AnalyticsState(TypedDict):
    candidate_id: str
    include_email: bool
    raw_data: dict | None      # Aggregated pipeline/outreach/skill data
    insights: list[dict] | None  # AI-generated insights
    insights_saved: int
    status: str
    error: str | None
```

The `notify` node should check `include_email` flag. If true, use `get_email_client()` to send a weekly digest email with the generated insights.

Graph edges: Same pattern as other pipelines with `_check_error` conditional routing.

**Step 2: Commit**

```bash
git add backend/app/graphs/analytics_pipeline.py
git commit -m "feat(analytics): add LangGraph analytics pipeline"
```

---

### Task 16: Extend analytics API + schemas

**Files:**
- Modify: `backend/app/schemas/analytics.py`
- Modify: `backend/app/api/analytics.py`

**Step 1: Add new schemas**

Add to `backend/app/schemas/analytics.py`:

```python
class AnalyticsInsightResponse(BaseModel):
    id: str
    insight_type: str
    title: str
    body: str
    severity: str
    data: dict | None = None
    is_read: bool = False
    created_at: str

    model_config = {"from_attributes": True}


class AnalyticsInsightListResponse(BaseModel):
    insights: list[AnalyticsInsightResponse]
    total: int


class AnalyticsDashboardResponse(BaseModel):
    funnel: FunnelResponse
    outreach: OutreachStatsResponse
    pipeline: PipelineStatsResponse
    insights: list[AnalyticsInsightResponse]
```

**Step 2: Add new endpoints to analytics router**

Add to `backend/app/api/analytics.py`:

- `GET /analytics/insights` — List AnalyticsInsight records, ordered by created_at desc, supports `?unread_only=true`
- `POST /analytics/insights/refresh` — Trigger analytics pipeline via BackgroundTasks (rate limited 5/day)
- `PATCH /analytics/insights/{id}/read` — Mark insight as read
- `GET /analytics/dashboard` — Combined endpoint returning funnel + outreach + pipeline + latest insights in one call

**Step 3: Register the analytics cron in worker.py**

Add to `backend/app/worker.py`:

```python
async def run_weekly_analytics(ctx):
    """Generate weekly analytics insights for all active candidates."""
    from app.infrastructure.database import async_session_factory
    from app.models.candidate import Candidate, CandidateDNA
    from sqlalchemy import select

    logger.info("weekly_analytics_started")

    async with async_session_factory() as db:
        result = await db.execute(
            select(Candidate).where(Candidate.is_active == True)
        )
        candidates = result.scalars().all()

    for cand in candidates:
        try:
            from app.graphs.analytics_pipeline import get_analytics_pipeline
            import uuid

            thread_id = f"analytics-weekly-{uuid.uuid4()}"
            graph = get_analytics_pipeline()
            await graph.ainvoke(
                {
                    "candidate_id": str(cand.id),
                    "include_email": True,
                    "raw_data": None,
                    "insights": None,
                    "insights_saved": 0,
                    "status": "pending",
                    "error": None,
                },
                config={"configurable": {"thread_id": thread_id}},
            )
        except Exception as e:
            logger.error("weekly_analytics_failed", candidate_id=str(cand.id), error=str(e))

    logger.info("weekly_analytics_completed")
```

Register: `cron(run_weekly_analytics, weekday={0}, hour={8}, minute={0})` — Mondays 8 AM UTC.

**Step 4: Commit**

```bash
git add backend/app/schemas/analytics.py backend/app/api/analytics.py backend/app/worker.py
git commit -m "feat(analytics): extend API with insights endpoints + weekly cron"
```

---

### Task 17: Analytics Agent tests

**Files:**
- Create: `backend/tests/test_analytics_agent.py`
- Modify: `backend/tests/conftest.py`

**Step 1: Add analytics schema detection to OpenAIStub**

Add to conftest.py `parse_structured()`:

```python
# Analytics insights schema
if "insights" in schema_keys:
    return {
        "insights": [
            {"insight_type": "pipeline_health", "title": "Pipeline Growing",
             "body": "You have 5 companies in your pipeline, up from 3 last week.",
             "severity": "success", "data": {"current": 5, "previous": 3}},
            {"insight_type": "recommendation", "title": "Follow Up Needed",
             "body": "3 companies haven't received follow-ups in over a week.",
             "severity": "action_needed", "data": {"company_count": 3}},
        ],
    }
```

**Step 2: Create tests**

Tests:
1. `test_graph_builds`
2. `test_graph_has_expected_nodes`
3. `test_insights_endpoint_empty`
4. `test_refresh_endpoint`
5. `test_dashboard_endpoint`
6. `test_mark_read`

**Step 3: Commit**

```bash
git add backend/tests/test_analytics_agent.py backend/tests/conftest.py
git commit -m "feat(analytics): add tests for analytics pipeline and API"
```

---

### Task 18: Analytics frontend — enhanced dashboard + insights

**Files:**
- Create: `frontend/src/app/(dashboard)/analytics/page.tsx`
- Create: `frontend/src/lib/api/analytics-insights.ts`
- Create: `frontend/src/lib/hooks/use-analytics-insights.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/hooks/use-websocket.ts`

**Step 1: Add types**

```typescript
// Analytics Insights
export interface AnalyticsInsightResponse {
  id: string;
  insight_type: string;
  title: string;
  body: string;
  severity: string;
  data: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string;
}

export interface AnalyticsInsightListResponse {
  insights: AnalyticsInsightResponse[];
  total: number;
}

export interface AnalyticsDashboardResponse {
  funnel: FunnelResponse;
  outreach: OutreachStatsResponse;
  pipeline: PipelineStatsResponse;
  insights: AnalyticsInsightResponse[];
}
```

**Step 2: Create API + hooks**

API endpoints:
- `getDashboard()` → GET `/analytics/dashboard`
- `getInsights(unreadOnly?)` → GET `/analytics/insights`
- `refreshInsights()` → POST `/analytics/insights/refresh`
- `markInsightRead(id)` → PATCH `/analytics/insights/{id}/read`

Hooks:
- `useAnalyticsDashboard()` — queryKey: `["analytics-dashboard"]`
- `useAnalyticsInsights(unreadOnly?)` — queryKey: `["analytics-insights"]`
- `useRefreshInsights()` — mutation
- `useMarkInsightRead()` — mutation

**Step 3: Create analytics page**

Create `frontend/src/app/(dashboard)/analytics/page.tsx`:

Top section — Charts (Recharts):
- Funnel chart (bar chart: drafted → sent → delivered → opened → replied)
- Pipeline chart (pie chart: suggested, approved, researched, contacted)
- Outreach performance (open rate, reply rate as radial progress)

Bottom section — Insights Feed:
- Scrollable list of AI-generated insight cards
- Color-coded by severity (info=blue, success=green, warning=yellow, action_needed=red)
- Mark as read on click/expand
- Refresh button to trigger new analysis
- Unread count badge

**Step 4: Add WebSocket handlers**

```typescript
case "analytics_completed":
case "analytics_failed":
  queryClient.invalidateQueries({ queryKey: ["analytics-dashboard"] });
  queryClient.invalidateQueries({ queryKey: ["analytics-insights"] });
  break;
```

**Step 5: Commit**

```bash
git add frontend/src/app/\(dashboard\)/analytics/page.tsx frontend/src/lib/api/analytics-insights.ts frontend/src/lib/hooks/use-analytics-insights.ts frontend/src/lib/types.ts frontend/src/lib/hooks/use-websocket.ts
git commit -m "feat(analytics): add analytics dashboard with charts and insights feed"
```

---

### Analytics Agent — Verification

1. `pytest tests/test_analytics_agent.py -v` — all tests pass
2. `pytest tests/ -v` — full suite passes
3. Pipeline has 5 nodes: gather_data, generate_insights, save_insights, notify, mark_failed
4. `GET /analytics/dashboard` returns combined data
5. `GET /analytics/insights` lists AI-generated insights
6. `POST /analytics/insights/refresh` triggers pipeline
7. Weekly cron generates insights every Monday 8 AM UTC
8. Frontend shows charts + insights feed

---

## Task 19: Update project-report.html

**Files:**
- Modify: `project-report.html`

Update:
- Phase 3 agents: mark Interview Prep, Apply, Analytics as complete
- Update total LOC, files, tests, models, migrations, endpoints counts
- Update overall score and sub-scores
- Phase 3 → complete, Phase 4 → active
- Update dates and progress bars

**Commit:**

```bash
git add project-report.html
git commit -m "docs: update project report with Phase 3 completion"
```

---

## Final Verification

1. `cd jobhunter/backend && python -m pytest tests/ -v` — ALL tests pass
2. All 3 new sidebar nav items visible: Interview Prep, Apply, Analytics
3. All new migrations applied: 014, 015, 016
4. All new models registered in `__init__.py`: InterviewPrepSession, MockInterviewMessage, JobPosting, AnalyticsInsight
5. All new routers registered in `main.py`: interview_router, apply_router (analytics already exists, extended)
6. Worker cron jobs include: check_followup_due, expire_stale_actions, run_daily_scout, run_weekly_analytics
7. WebSocket events handled: interview_prep_completed/failed, apply_analysis_completed/failed, analytics_completed/failed

---

## File Summary

| # | File | Action | Agent |
|---|------|--------|-------|
| 1 | `backend/app/models/interview.py` | CREATE | Interview |
| 2 | `backend/app/models/__init__.py` | MODIFY | Interview |
| 3 | `backend/alembic/versions/014_interview_prep.py` | CREATE | Interview |
| 4 | `backend/app/schemas/interview.py` | CREATE | Interview |
| 5 | `backend/app/graphs/interview_prep.py` | CREATE | Interview |
| 6 | `backend/app/api/interview.py` | CREATE | Interview |
| 7 | `backend/app/main.py` | MODIFY | Interview+Apply |
| 8 | `backend/app/services/company_service.py` | MODIFY | Interview |
| 9 | `backend/app/api/companies.py` | MODIFY | Interview |
| 10 | `backend/tests/test_interview_prep.py` | CREATE | Interview |
| 11 | `frontend/src/app/(dashboard)/interview-prep/page.tsx` | CREATE | Interview |
| 12 | `frontend/src/lib/api/interview.ts` | CREATE | Interview |
| 13 | `frontend/src/lib/hooks/use-interview.ts` | CREATE | Interview |
| 14 | `frontend/src/components/layout/sidebar.tsx` | MODIFY | Interview+Apply |
| 15 | `frontend/src/lib/types.ts` | MODIFY | All 3 |
| 16 | `frontend/src/lib/hooks/use-websocket.ts` | MODIFY | All 3 |
| 17 | `backend/app/models/job_posting.py` | CREATE | Apply |
| 18 | `backend/alembic/versions/015_job_postings.py` | CREATE | Apply |
| 19 | `backend/app/schemas/apply.py` | CREATE | Apply |
| 20 | `backend/app/graphs/apply_pipeline.py` | CREATE | Apply |
| 21 | `backend/app/api/apply.py` | CREATE | Apply |
| 22 | `backend/tests/test_apply.py` | CREATE | Apply |
| 23 | `frontend/src/app/(dashboard)/apply/page.tsx` | CREATE | Apply |
| 24 | `frontend/src/lib/api/apply.ts` | CREATE | Apply |
| 25 | `frontend/src/lib/hooks/use-apply.ts` | CREATE | Apply |
| 26 | `backend/app/models/insight.py` | CREATE | Analytics |
| 27 | `backend/alembic/versions/016_analytics_insights.py` | CREATE | Analytics |
| 28 | `backend/app/schemas/analytics.py` | MODIFY | Analytics |
| 29 | `backend/app/api/analytics.py` | MODIFY | Analytics |
| 30 | `backend/app/graphs/analytics_pipeline.py` | CREATE | Analytics |
| 31 | `backend/app/worker.py` | MODIFY | Analytics |
| 32 | `backend/tests/test_analytics_agent.py` | CREATE | Analytics |
| 33 | `frontend/src/app/(dashboard)/analytics/page.tsx` | CREATE | Analytics |
| 34 | `frontend/src/lib/api/analytics-insights.ts` | CREATE | Analytics |
| 35 | `frontend/src/lib/hooks/use-analytics-insights.ts` | CREATE | Analytics |
| 36 | `backend/tests/conftest.py` | MODIFY | All 3 |
| 37 | `project-report.html` | MODIFY | All 3 |

**Total: 37 files (22 create, 15 modify)**
