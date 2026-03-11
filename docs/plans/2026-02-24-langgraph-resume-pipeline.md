# LangGraph Resume Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the monolithic `_run_async_background()` in `candidates.py` with a LangGraph StateGraph that processes resumes through independently checkpointed nodes with PostgreSQL persistence.

**Architecture:** A 5-node StateGraph (parse_resume → extract_skills → generate_dna → recalculate_fits → notify) with conditional error routing to a mark_failed node. Each node reads/writes to a shared TypedDict state. PostgreSQL checkpointing via `langgraph-checkpoint-postgres` enables crash recovery and per-node retry. The graph is invoked from the same BackgroundTasks entry point — no API or frontend changes.

**Tech Stack:** LangGraph 0.4+, langgraph-checkpoint-postgres 2.0+, FastAPI BackgroundTasks, SQLAlchemy async, OpenAI structured output, pgvector embeddings.

---

## Context

The resume processing pipeline currently lives in `jobhunter/backend/app/api/candidates.py:52-87` as a single async function `_run_async_background()`. It calls `resume_service.parse_resume()`, `resume_service.generate_candidate_dna()`, `company_service.recalculate_fit_scores()`, and sends a WebSocket notification — all in one try/except. Any failure means the entire pipeline must restart from scratch.

The existing service functions in `resume_service.py` contain the actual logic we're preserving:
- `parse_resume()` (lines 191-209): OpenAI structured output to parse resume text
- `generate_candidate_dna()` (lines 212-296): Skills extraction + DNA summary + embeddings + DB writes

We'll decompose `generate_candidate_dna()` into separate graph nodes (extract_skills, generate_dna) and add recalculate_fits + notify as their own nodes.

**Key files to understand before starting:**
- `app/api/candidates.py` — current background task entry point
- `app/services/resume_service.py` — resume parsing + DNA generation logic
- `app/services/company_service.py:151-191` — fit score recalculation
- `app/services/embedding_service.py` — embed_text, batch_embed, cosine_similarity
- `app/infrastructure/database.py` — async_session_factory
- `app/infrastructure/websocket_manager.py` — ws_manager.broadcast()
- `app/config.py` — settings.DATABASE_URL
- `app/main.py` — lifespan startup/shutdown
- `tests/conftest.py` — OpenAIStub, test fixtures

**Test stub note:** The `OpenAIStub` in `tests/conftest.py` returns a flat dict that satisfies multiple schemas. For the graph tests, we'll need to update it to also return proper `skills` data when the skills extraction schema is detected.

---

## Files Summary

| # | Task | Action | Files |
|---|------|--------|-------|
| 1 | Add dependencies | MODIFY | `backend/pyproject.toml` |
| 2 | Update OpenAI stub | MODIFY | `backend/tests/conftest.py` |
| 3 | Create graph module | CREATE | `backend/app/graphs/__init__.py` |
| | | CREATE | `backend/app/graphs/resume_pipeline.py` |
| 4 | Write graph tests | CREATE | `backend/tests/test_resume_graph.py` |
| 5 | Wire into candidates API | MODIFY | `backend/app/api/candidates.py` |
| | | MODIFY | `backend/app/main.py` |
| 6 | Run full test suite | — | verify all 147+ tests still pass |

**3 new files, 4 modified files.**

---

## Task 1: Add LangGraph Dependencies

**Files:**
- Modify: `jobhunter/backend/pyproject.toml`

**Step 1: Add langgraph and checkpoint-postgres to dependencies**

In `pyproject.toml`, add these two lines to the `dependencies` array (after the `arq` line):

```toml
    "langgraph>=0.4.0",
    "langgraph-checkpoint-postgres>=2.0.0",
```

**Step 2: Install dependencies**

Run: `cd jobhunter/backend && uv sync`
Expected: Dependencies resolve and install successfully.

**Step 3: Verify import works**

Run: `cd jobhunter/backend && uv run python -c "from langgraph.graph import StateGraph, START, END; from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver; print('OK')"`
Expected: Prints `OK`

**Step 4: Commit**

```bash
git add jobhunter/backend/pyproject.toml jobhunter/backend/uv.lock
git commit -m "chore: add langgraph and checkpoint-postgres dependencies"
```

---

## Task 2: Update OpenAI Test Stub for Skills Schema

**Files:**
- Modify: `jobhunter/backend/tests/conftest.py`

The graph nodes call `parse_structured` with different schemas. The existing stub detects the company discovery schema but returns a flat dict for everything else. We need it to also detect the skills extraction schema (has `"skills"` key with items containing `"category"` and `"proficiency"`) and return proper skills data.

**Step 1: Update OpenAIStub.parse_structured to detect skills schema**

In `tests/conftest.py`, replace the `parse_structured` method of `OpenAIStub` with:

```python
async def parse_structured(self, system_prompt: str, user_content: str, response_schema: dict) -> dict:
    schema_keys = set(response_schema.get("properties", {}).keys())

    # Company discovery schema
    if "companies" in schema_keys and len(schema_keys) == 1:
        return {
            "companies": [
                {"domain": "stripe.com", "name": "Stripe", "reason": "Strong fintech fit",
                 "industry": "Financial Technology", "size": "1001-5000",
                 "tech_stack": ["Ruby", "Go", "React"]},
                {"domain": "plaid.com", "name": "Plaid", "reason": "API-focused fintech",
                 "industry": "Financial Technology", "size": "501-1000",
                 "tech_stack": ["Python", "TypeScript", "Kubernetes"]},
                {"domain": "vercel.com", "name": "Vercel", "reason": "Developer tools",
                 "industry": "Developer Tools", "size": "201-500",
                 "tech_stack": ["Next.js", "Go", "Rust"]},
            ]
        }

    # Skills extraction schema (has "skills" key with items containing category/proficiency)
    skills_props = response_schema.get("properties", {}).get("skills", {})
    items_props = skills_props.get("items", {}).get("properties", {})
    if "skills" in schema_keys and "category" in items_props and "proficiency" in items_props:
        return {
            "skills": [
                {"name": "Python", "category": "explicit", "proficiency": "expert",
                 "years_experience": 5.0, "evidence": "5 years professional Python development"},
                {"name": "FastAPI", "category": "explicit", "proficiency": "advanced",
                 "years_experience": 3.0, "evidence": "Built REST APIs with FastAPI"},
                {"name": "Leadership", "category": "transferable", "proficiency": "intermediate",
                 "years_experience": 2.0, "evidence": "Led team of 5 engineers"},
            ]
        }

    # Default: satisfies resume parsing, DNA summary, outreach, and dossier schemas
    return {
        "name": "Test User",
        "headline": "Software Engineer",
        "experiences": [{"company": "TestCo", "title": "Engineer", "dates": "2020-2024",
                         "description": "Backend development", "achievements": ["Built API"]}],
        "skills": ["Python", "FastAPI"],
        "education": [{"institution": "MIT", "degree": "BS CS", "year": "2020"}],
        "certifications": [],
        "summary": "Experienced engineer.",
        "strengths": ["Python", "APIs", "Databases", "Testing", "Architecture"],
        "gaps": ["Frontend", "Mobile"],
        "career_stage": "mid",
        "experience_summary": "Mid-level engineer with backend focus.",
        "subject": "Quick question about your team",
        "body": "Hi, I noticed your team is doing great work. I'd love to connect.",
        "personalization_points": ["team growth", "tech stack alignment"],
        "culture_summary": "Innovative and collaborative engineering culture.",
        "culture_score": 8,
        "red_flags": [],
        "interview_format": "Phone screen, technical, system design, onsite",
        "interview_questions": ["Tell me about yourself"],
        "compensation_data": {"range": "150k-250k", "equity": "0.1%", "benefits": ["health"]},
        "key_people": [{"name": "Jane Doe", "title": "CTO"}],
        "why_hire_me": "Strong backend experience aligns with team needs.",
        "resume_bullets": ["Highlight your Python and API development experience"],
        "fit_score_tips": ["Consider learning TypeScript to broaden your frontend skills"],
        "recent_news": [{"title": "Series B", "date": "2025-01-01"}],
    }
```

**Step 2: Run existing tests to make sure nothing breaks**

Run: `cd jobhunter/backend && uv run pytest tests/ -x -q`
Expected: All tests pass (147+).

**Step 3: Commit**

```bash
git add jobhunter/backend/tests/conftest.py
git commit -m "test: update OpenAI stub to detect skills extraction schema"
```

---

## Task 3: Create the LangGraph Resume Pipeline

**Files:**
- Create: `jobhunter/backend/app/graphs/__init__.py`
- Create: `jobhunter/backend/app/graphs/resume_pipeline.py`

**Step 1: Create the graphs package**

Create `jobhunter/backend/app/graphs/__init__.py` as an empty file.

**Step 2: Create the resume pipeline graph**

Create `jobhunter/backend/app/graphs/resume_pipeline.py`:

```python
"""LangGraph resume processing pipeline.

Replaces the monolithic _run_async_background() with a checkpointed graph:
START → parse_resume → extract_skills → generate_dna → recalculate_fits → notify → END
"""
import json
import uuid
from typing import Literal

import structlog
from langgraph.graph import START, END, StateGraph
from sqlalchemy import select
from typing_extensions import TypedDict

from app.infrastructure.database import async_session_factory
from app.dependencies import get_openai
from app.models.candidate import CandidateDNA, Resume, Skill
from app.services.embedding_service import batch_embed, embed_text
from app.services.resume_service import (
    RESUME_PARSE_PROMPT, RESUME_PARSE_SCHEMA,
    SKILLS_EXTRACTION_PROMPT, SKILLS_SCHEMA,
    DNA_SUMMARY_PROMPT, DNA_SCHEMA,
)

logger = structlog.get_logger()


class ResumeProcessingState(TypedDict):
    """State flowing through the resume pipeline graph."""
    # Input
    resume_id: str
    candidate_id: str
    # Intermediate
    parsed_data: dict | None
    raw_text: str | None
    skills_data: dict | None
    dna_data: dict | None
    embedding: list[float] | None
    skills_vector: list[float] | None
    # Output
    fit_scores_updated: int
    status: str  # "pending" | "completed" | "failed"
    error: str | None


async def parse_resume_node(state: ResumeProcessingState) -> dict:
    """Load resume from DB, call OpenAI structured parse, save parsed_data."""
    resume_id = uuid.UUID(state["resume_id"])

    async with async_session_factory() as db:
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if not resume:
            return {"status": "failed", "error": "Resume not found"}
        if not resume.raw_text:
            return {"status": "failed", "error": "Resume has no extracted text"}

        client = get_openai()
        parsed = await client.parse_structured(
            RESUME_PARSE_PROMPT, resume.raw_text, RESUME_PARSE_SCHEMA
        )

        resume.parsed_data = parsed
        await db.commit()

    logger.info("graph_parse_resume_done", resume_id=state["resume_id"])
    return {"parsed_data": parsed, "raw_text": resume.raw_text}


async def extract_skills_node(state: ResumeProcessingState) -> dict:
    """Extract categorized skills from resume text."""
    raw_text = state["raw_text"]
    if not raw_text:
        return {"status": "failed", "error": "No raw_text available for skills extraction"}

    client = get_openai()
    skills_data = await client.parse_structured(
        SKILLS_EXTRACTION_PROMPT, raw_text, SKILLS_SCHEMA
    )

    logger.info("graph_extract_skills_done", resume_id=state["resume_id"],
                skill_count=len(skills_data.get("skills", [])))
    return {"skills_data": skills_data}


async def generate_dna_node(state: ResumeProcessingState) -> dict:
    """Generate DNA summary, embeddings, and persist CandidateDNA + Skill records."""
    candidate_id = uuid.UUID(state["candidate_id"])
    parsed_data = state["parsed_data"]
    skills_data = state["skills_data"]
    raw_text = state["raw_text"]

    if not parsed_data or not skills_data:
        return {"status": "failed", "error": "Missing parsed_data or skills_data"}

    client = get_openai()
    resume_text = raw_text or json.dumps(parsed_data)

    # Generate embedding for the full resume
    embedding = await embed_text(resume_text)

    # Generate DNA summary
    dna_data = await client.parse_structured(
        DNA_SUMMARY_PROMPT, json.dumps(parsed_data), DNA_SCHEMA
    )

    # Generate skills vector
    skill_names = [s["name"] for s in skills_data.get("skills", [])]
    skills_vector = await embed_text(" ".join(skill_names)) if skill_names else embedding

    async with async_session_factory() as db:
        # Delete existing DNA and skills
        existing = await db.execute(
            select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id)
        )
        old_dna = existing.scalar_one_or_none()
        if old_dna:
            await db.delete(old_dna)

        existing_skills = await db.execute(
            select(Skill).where(Skill.candidate_id == candidate_id)
        )
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

        # Create skill records with batched embeddings
        skills_list = skills_data.get("skills", [])
        skill_names = [s["name"] for s in skills_list]
        skill_embeddings = await batch_embed(skill_names) if skill_names else []

        for skill_data_item, skill_embedding in zip(skills_list, skill_embeddings):
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

    logger.info("graph_generate_dna_done", candidate_id=state["candidate_id"])
    return {
        "dna_data": dna_data,
        "embedding": embedding,
        "skills_vector": skills_vector,
    }


async def recalculate_fits_node(state: ResumeProcessingState) -> dict:
    """Recalculate fit scores for existing companies with the new DNA."""
    candidate_id = uuid.UUID(state["candidate_id"])

    async with async_session_factory() as db:
        from app.services.company_service import recalculate_fit_scores
        updated = await recalculate_fit_scores(db, candidate_id)

    logger.info("graph_recalculate_fits_done", candidate_id=state["candidate_id"], updated=updated)
    return {"fit_scores_updated": updated}


async def notify_node(state: ResumeProcessingState) -> dict:
    """Mark resume as completed and send WebSocket notification."""
    resume_id = uuid.UUID(state["resume_id"])
    candidate_id = state["candidate_id"]

    async with async_session_factory() as db:
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if resume:
            resume.parse_status = "completed"
            await db.commit()

    from app.infrastructure.websocket_manager import ws_manager
    await ws_manager.broadcast(
        candidate_id, "resume_parsed",
        {
            "resume_id": state["resume_id"],
            "status": "completed",
            "fit_scores_updated": state.get("fit_scores_updated", 0),
        },
    )

    logger.info("graph_notify_done", resume_id=state["resume_id"])
    return {"status": "completed"}


async def mark_failed_node(state: ResumeProcessingState) -> dict:
    """Mark resume as failed and send error notification."""
    resume_id = uuid.UUID(state["resume_id"])
    candidate_id = state["candidate_id"]

    async with async_session_factory() as db:
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if resume:
            resume.parse_status = "failed"
            await db.commit()

    from app.infrastructure.websocket_manager import ws_manager
    await ws_manager.broadcast(
        candidate_id, "resume_parsed",
        {"resume_id": state["resume_id"], "status": "failed", "error": state.get("error")},
    )

    logger.info("graph_mark_failed_done", resume_id=state["resume_id"], error=state.get("error"))
    return {}


def _check_error(state: ResumeProcessingState) -> Literal["continue", "mark_failed"]:
    """Route to mark_failed if status is 'failed', otherwise continue."""
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


def build_resume_pipeline() -> StateGraph:
    """Build and return the (uncompiled) resume processing graph."""
    builder = StateGraph(ResumeProcessingState)

    # Add nodes
    builder.add_node("parse_resume", parse_resume_node)
    builder.add_node("extract_skills", extract_skills_node)
    builder.add_node("generate_dna", generate_dna_node)
    builder.add_node("recalculate_fits", recalculate_fits_node)
    builder.add_node("notify", notify_node)
    builder.add_node("mark_failed", mark_failed_node)

    # Edges: START → parse_resume
    builder.add_edge(START, "parse_resume")

    # After parse_resume, check for errors
    builder.add_conditional_edges(
        "parse_resume", _check_error,
        {"continue": "extract_skills", "mark_failed": "mark_failed"},
    )

    # After extract_skills, check for errors
    builder.add_conditional_edges(
        "extract_skills", _check_error,
        {"continue": "generate_dna", "mark_failed": "mark_failed"},
    )

    # After generate_dna, check for errors
    builder.add_conditional_edges(
        "generate_dna", _check_error,
        {"continue": "recalculate_fits", "mark_failed": "mark_failed"},
    )

    # recalculate_fits → notify → END
    builder.add_edge("recalculate_fits", "notify")
    builder.add_edge("notify", END)
    builder.add_edge("mark_failed", END)

    return builder


# Module-level graph instance (compiled without checkpointer for testing).
# In production, compile with PostgreSQL checkpointer via get_resume_pipeline().
_builder = build_resume_pipeline()

# Checkpointer is set at runtime. This reference is populated by init_checkpointer().
_checkpointer = None


async def init_checkpointer(db_url: str) -> None:
    """Initialize the PostgreSQL checkpointer. Call once at app startup."""
    global _checkpointer
    # langgraph-checkpoint-postgres needs a raw postgres:// URL, not postgresql+asyncpg://
    raw_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    _checkpointer = AsyncPostgresSaver.from_conn_string(raw_url)
    await _checkpointer.setup()
    logger.info("langgraph_checkpointer_initialized")


def get_resume_pipeline():
    """Return the compiled graph with checkpointer (for production use)."""
    return _builder.compile(checkpointer=_checkpointer)


def get_resume_pipeline_no_checkpointer():
    """Return the compiled graph without checkpointer (for testing)."""
    return _builder.compile()
```

**Step 3: Verify the module imports**

Run: `cd jobhunter/backend && uv run python -c "from app.graphs.resume_pipeline import build_resume_pipeline, ResumeProcessingState; print('OK')"`
Expected: Prints `OK`

**Step 4: Commit**

```bash
git add jobhunter/backend/app/graphs/__init__.py jobhunter/backend/app/graphs/resume_pipeline.py
git commit -m "feat: create LangGraph resume processing pipeline"
```

---

## Task 4: Write Graph Tests

**Files:**
- Create: `jobhunter/backend/tests/test_resume_graph.py`

**Step 1: Write tests for the resume pipeline graph**

Create `jobhunter/backend/tests/test_resume_graph.py`:

```python
"""Tests for the LangGraph resume processing pipeline."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate, CandidateDNA, Resume, Skill
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


@pytest_asyncio.fixture
async def candidate_with_resume(db_session: AsyncSession):
    """Create a candidate with an uploaded resume (raw_text populated)."""
    candidate = Candidate(
        id=uuid.uuid4(),
        email=f"graph-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Graph Test User",
    )
    db_session.add(candidate)
    await db_session.flush()

    resume = Resume(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        file_path="resumes/test/abc123.pdf",
        file_hash="abc123",
        raw_text="John Doe, Software Engineer. 5 years Python, FastAPI, PostgreSQL. MIT BS CS 2020.",
        is_primary=True,
        parse_status="pending",
    )
    db_session.add(resume)
    await db_session.flush()

    return candidate, resume


@pytest.mark.asyncio
async def test_graph_full_pipeline(db_session, candidate_with_resume):
    """Test the full resume pipeline graph runs from parse to notify."""
    from app.graphs.resume_pipeline import get_resume_pipeline_no_checkpointer, ResumeProcessingState

    candidate, resume = candidate_with_resume
    graph = get_resume_pipeline_no_checkpointer()

    initial_state: ResumeProcessingState = {
        "resume_id": str(resume.id),
        "candidate_id": str(candidate.id),
        "parsed_data": None,
        "raw_text": None,
        "skills_data": None,
        "dna_data": None,
        "embedding": None,
        "skills_vector": None,
        "fit_scores_updated": 0,
        "status": "pending",
        "error": None,
    }

    result = await graph.ainvoke(initial_state)

    # Pipeline should complete successfully
    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["parsed_data"] is not None
    assert result["skills_data"] is not None
    assert result["dna_data"] is not None
    assert result["embedding"] is not None

    # Verify DB state: resume should be marked completed
    db_resume = await db_session.execute(select(Resume).where(Resume.id == resume.id))
    updated_resume = db_resume.scalar_one()
    assert updated_resume.parse_status == "completed"
    assert updated_resume.parsed_data is not None

    # Verify DNA was created
    dna_result = await db_session.execute(
        select(CandidateDNA).where(CandidateDNA.candidate_id == candidate.id)
    )
    dna = dna_result.scalar_one_or_none()
    assert dna is not None
    assert dna.experience_summary is not None
    assert dna.career_stage is not None

    # Verify skills were created
    skills_result = await db_session.execute(
        select(Skill).where(Skill.candidate_id == candidate.id)
    )
    skills = skills_result.scalars().all()
    assert len(skills) >= 1


@pytest.mark.asyncio
async def test_graph_missing_resume(db_session):
    """Test that graph handles missing resume gracefully."""
    from app.graphs.resume_pipeline import get_resume_pipeline_no_checkpointer, ResumeProcessingState

    graph = get_resume_pipeline_no_checkpointer()

    initial_state: ResumeProcessingState = {
        "resume_id": str(uuid.uuid4()),  # Non-existent
        "candidate_id": str(uuid.uuid4()),
        "parsed_data": None,
        "raw_text": None,
        "skills_data": None,
        "dna_data": None,
        "embedding": None,
        "skills_vector": None,
        "fit_scores_updated": 0,
        "status": "pending",
        "error": None,
    }

    result = await graph.ainvoke(initial_state)

    assert result["status"] == "failed"
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_graph_no_raw_text(db_session):
    """Test that graph handles resume with no raw_text."""
    from app.graphs.resume_pipeline import get_resume_pipeline_no_checkpointer, ResumeProcessingState

    candidate = Candidate(
        id=uuid.uuid4(),
        email=f"graph-notext-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="No Text User",
    )
    db_session.add(candidate)
    await db_session.flush()

    resume = Resume(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        file_path="resumes/test/empty.pdf",
        file_hash="empty",
        raw_text=None,  # No text extracted
        is_primary=True,
        parse_status="pending",
    )
    db_session.add(resume)
    await db_session.flush()

    graph = get_resume_pipeline_no_checkpointer()

    initial_state: ResumeProcessingState = {
        "resume_id": str(resume.id),
        "candidate_id": str(candidate.id),
        "parsed_data": None,
        "raw_text": None,
        "skills_data": None,
        "dna_data": None,
        "embedding": None,
        "skills_vector": None,
        "fit_scores_updated": 0,
        "status": "pending",
        "error": None,
    }

    result = await graph.ainvoke(initial_state)

    assert result["status"] == "failed"
    assert "no extracted text" in result["error"].lower()

    # Resume should be marked failed in DB
    db_resume = await db_session.execute(select(Resume).where(Resume.id == resume.id))
    updated_resume = db_resume.scalar_one()
    assert updated_resume.parse_status == "failed"


@pytest.mark.asyncio
async def test_graph_state_has_skills(db_session, candidate_with_resume):
    """Test that skills_data in state contains categorized skills."""
    from app.graphs.resume_pipeline import get_resume_pipeline_no_checkpointer, ResumeProcessingState

    candidate, resume = candidate_with_resume
    graph = get_resume_pipeline_no_checkpointer()

    initial_state: ResumeProcessingState = {
        "resume_id": str(resume.id),
        "candidate_id": str(candidate.id),
        "parsed_data": None,
        "raw_text": None,
        "skills_data": None,
        "dna_data": None,
        "embedding": None,
        "skills_vector": None,
        "fit_scores_updated": 0,
        "status": "pending",
        "error": None,
    }

    result = await graph.ainvoke(initial_state)

    # Verify skills_data has the expected structure
    skills = result["skills_data"]["skills"]
    assert len(skills) >= 1
    for skill in skills:
        assert "name" in skill
        assert "category" in skill
        assert skill["category"] in ("explicit", "transferable", "adjacent")
```

**Step 2: Run only the graph tests**

Run: `cd jobhunter/backend && uv run pytest tests/test_resume_graph.py -x -v`
Expected: All 4 tests pass.

**Step 3: Run the full test suite to check for regressions**

Run: `cd jobhunter/backend && uv run pytest tests/ -x -q`
Expected: All tests pass (147+ including the 4 new ones).

**Step 4: Commit**

```bash
git add jobhunter/backend/tests/test_resume_graph.py
git commit -m "test: add comprehensive tests for LangGraph resume pipeline"
```

---

## Task 5: Wire Graph into Candidates API and App Startup

**Files:**
- Modify: `jobhunter/backend/app/api/candidates.py`
- Modify: `jobhunter/backend/app/main.py`

**Step 1: Update main.py lifespan to initialize the checkpointer**

In `app/main.py`, add the checkpointer init to the lifespan function. After the `await init_redis()` line (line 36), add:

```python
    # Initialize LangGraph checkpointer
    from app.graphs.resume_pipeline import init_checkpointer
    await init_checkpointer(settings.DATABASE_URL)
```

**Step 2: Replace _run_async_background in candidates.py**

Replace the entire `_run_async_background` function (lines 52-87 in `app/api/candidates.py`) with:

```python
async def _run_async_background(resume_id, candidate_id):
    """Run the LangGraph resume processing pipeline."""
    from app.graphs.resume_pipeline import get_resume_pipeline

    graph = get_resume_pipeline()
    config = {"configurable": {"thread_id": f"resume:{resume_id}"}}

    try:
        result = await graph.ainvoke(
            {
                "resume_id": str(resume_id),
                "candidate_id": str(candidate_id),
                "parsed_data": None,
                "raw_text": None,
                "skills_data": None,
                "dna_data": None,
                "embedding": None,
                "skills_vector": None,
                "fit_scores_updated": 0,
                "status": "pending",
                "error": None,
            },
            config,
        )
        if result.get("status") == "failed":
            logger.error(
                "resume_pipeline_failed",
                resume_id=str(resume_id),
                error=result.get("error"),
            )
        else:
            logger.info("resume_pipeline_completed", resume_id=str(resume_id))
    except Exception as e:
        logger.error("resume_pipeline_exception", resume_id=str(resume_id), error=str(e))
        # Fallback: mark resume as failed
        from app.infrastructure.database import async_session_factory
        async with async_session_factory() as db:
            try:
                result = await db.execute(select(Resume).where(Resume.id == resume_id))
                resume = result.scalar_one_or_none()
                if resume:
                    resume.parse_status = "failed"
                    await db.commit()
            except Exception:
                pass
```

Also clean up imports that are no longer needed in candidates.py. The `resume_service` import stays (used in upload_resume), but remove the import of `recalculate_fit_scores` and `ws_manager` from within the old function body since those are now handled by graph nodes.

**Step 3: Run the full test suite**

Run: `cd jobhunter/backend && uv run pytest tests/ -x -q`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add jobhunter/backend/app/api/candidates.py jobhunter/backend/app/main.py
git commit -m "feat: wire LangGraph resume pipeline into candidates API"
```

---

## Task 6: Final Verification

**Step 1: Run the full test suite one more time**

Run: `cd jobhunter/backend && uv run pytest tests/ -x -q`
Expected: All tests pass (151+).

**Step 2: Verify the frontend still builds**

Run: `cd jobhunter/frontend && npm run build`
Expected: Build succeeds (no frontend changes were made).

**Step 3: Check imports and module structure**

Run: `cd jobhunter/backend && uv run python -c "from app.graphs.resume_pipeline import get_resume_pipeline, get_resume_pipeline_no_checkpointer, init_checkpointer, ResumeProcessingState; print('All imports OK')"`
Expected: Prints `All imports OK`

---

## Summary

After completing all 6 tasks:
- The monolithic `_run_async_background()` is replaced by a 5-node LangGraph StateGraph
- Each node is independently testable and checkpointed
- PostgreSQL persists intermediate state for crash recovery
- 4 new graph-specific tests verify the pipeline
- All existing tests continue to pass (no API changes)
- No frontend changes required
