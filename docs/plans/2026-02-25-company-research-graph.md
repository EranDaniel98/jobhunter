# Company Research Graph Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the monolithic `research_company()` function with a 6-node LangGraph StateGraph that adds web search enrichment and per-node crash recovery via PostgreSQL checkpointing.

**Architecture:** A LangGraph StateGraph with nodes: enrich_company → web_search → generate_dossier → create_contacts → embed_company → notify, plus a mark_failed error handler. Each node gets its own DB session. The graph reuses the shared PostgreSQL checkpointer from the resume pipeline.

**Tech Stack:** LangGraph, duckduckgo-search, OpenAI structured output, Hunter.io API, PostgreSQL checkpointing

---

### Task 1: Add duckduckgo-search dependency

**Files:**
- Modify: `jobhunter/backend/pyproject.toml:7` (dependencies list)

**Step 1: Add dependency**

In `pyproject.toml`, add `"duckduckgo-search>=7.0.0"` to the dependencies list after `"arq>=0.26.0"` (line 32):

```toml
    "arq>=0.26.0",
    "duckduckgo-search>=7.0.0",
    "langgraph>=0.4.0",
```

**Step 2: Install**

Run: `cd jobhunter/backend && pip install -e ".[dev]"`
Expected: Successfully installed duckduckgo-search

**Step 3: Commit**

```bash
git add jobhunter/backend/pyproject.toml
git commit -m "chore: add duckduckgo-search dependency for company research graph"
```

---

### Task 2: Create the Company Research Graph

**Files:**
- Create: `jobhunter/backend/app/graphs/company_research.py`
- Test: `jobhunter/backend/tests/test_company_research_graph.py`

**Step 1: Write the failing test**

Create `jobhunter/backend/tests/test_company_research_graph.py`:

```python
import uuid

import pytest

from app.graphs.company_research import (
    CompanyResearchState,
    build_company_research_graph,
    get_company_research_pipeline_no_checkpointer,
)


@pytest.mark.asyncio
async def test_graph_builds_and_compiles():
    """The graph should build and compile without errors."""
    graph = build_company_research_graph()
    assert graph is not None
    compiled = graph.compile()
    assert compiled is not None


@pytest.mark.asyncio
async def test_graph_has_expected_nodes():
    """Graph should contain all 7 nodes."""
    graph = build_company_research_graph()
    node_names = set(graph.nodes.keys())
    expected = {
        "enrich_company",
        "web_search",
        "generate_dossier",
        "create_contacts",
        "embed_company",
        "notify",
        "mark_failed",
    }
    assert expected == node_names
```

**Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && .venv/Scripts/python.exe -m pytest tests/test_company_research_graph.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` (module doesn't exist yet)

**Step 3: Create the graph module**

Create `jobhunter/backend/app/graphs/company_research.py`:

```python
"""LangGraph company research pipeline.

Replaces the monolithic research_company() with a 6-node StateGraph:
  enrich_company → web_search → generate_dossier → create_contacts → embed_company → notify

Each node gets its own DB session and is independently checkpointed.
PostgreSQL checkpointing via the shared checkpointer enables crash recovery.
"""

import json
import uuid
from datetime import datetime, timezone

import structlog
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from app.infrastructure import database as _db_mod
from app.dependencies import get_hunter, get_openai
from app.models.candidate import CandidateDNA
from app.models.company import Company, CompanyDossier
from app.models.contact import Contact
from app.services.company_service import (
    DOSSIER_PROMPT,
    DOSSIER_SCHEMA,
    _create_contacts_from_hunter,
)
from app.services.embedding_service import embed_text
from app.infrastructure.websocket_manager import ws_manager

from sqlalchemy import select

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class CompanyResearchState(TypedDict):
    company_id: str
    candidate_id: str
    plan_tier: str
    # Node outputs
    hunter_data: dict | None
    web_context: str | None
    dossier_data: dict | None
    contacts_created: int
    embedding_set: bool
    # Control
    status: str        # "pending" | "completed" | "failed"
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def enrich_company_node(state: CompanyResearchState) -> dict:
    """Call Hunter API to enrich company data."""
    company_id = uuid.UUID(state["company_id"])
    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"status": "failed", "error": f"Company {company_id} not found"}

        company.research_status = "in_progress"
        await db.commit()

        try:
            hunter = get_hunter()
            hunter_data = await hunter.domain_search(company.domain)

            # Update company fields from Hunter enrichment
            if hunter_data.get("industry") and not company.industry:
                company.industry = hunter_data["industry"]
            if hunter_data.get("size") and not company.size_range:
                company.size_range = hunter_data["size"]
            if hunter_data.get("location") and not company.location_hq:
                company.location_hq = hunter_data["location"]
            if hunter_data.get("description") and not company.description:
                company.description = hunter_data["description"]
            if hunter_data.get("technologies") and not company.tech_stack:
                company.tech_stack = hunter_data["technologies"]

            await db.commit()
        except Exception as e:
            logger.error("graph_enrich_company_failed", company_id=str(company_id), error=str(e))
            return {"status": "failed", "error": f"Hunter enrichment failed: {e}"}

    logger.info("graph_enrich_company_done", company_id=str(company_id))
    return {"hunter_data": hunter_data}


async def web_search_node(state: CompanyResearchState) -> dict:
    """Search the web for recent news, reviews, and funding info.

    Graceful degradation: if search fails, returns empty context
    rather than failing the pipeline.
    """
    company_id = uuid.UUID(state["company_id"])
    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"web_context": ""}

        company_name = company.name
        industry = company.industry or ""

    try:
        from duckduckgo_search import AsyncDDGS

        queries = [
            f"{company_name} glassdoor reviews culture",
            f"{company_name} recent news 2026",
            f"{company_name} {industry} funding hiring",
        ]

        snippets = []
        async with AsyncDDGS() as ddgs:
            for query in queries:
                try:
                    results = await ddgs.atext(query, max_results=3)
                    for r in results:
                        title = r.get("title", "")
                        body = r.get("body", "")
                        snippets.append(f"- {title}: {body}")
                except Exception:
                    # Individual query failure is fine
                    continue

        web_context = "\n".join(snippets)[:2000]  # Cap at ~2000 chars
    except Exception as e:
        logger.warning("graph_web_search_failed", company_id=str(company_id), error=str(e))
        web_context = ""

    logger.info("graph_web_search_done", company_id=str(company_id), context_len=len(web_context))
    return {"web_context": web_context}


async def generate_dossier_node(state: CompanyResearchState) -> dict:
    """Generate AI dossier using OpenAI structured output, enriched with web data."""
    company_id = uuid.UUID(state["company_id"])
    candidate_id = uuid.UUID(state["candidate_id"])
    web_context = state.get("web_context") or ""
    hunter_data = state.get("hunter_data") or {}

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"status": "failed", "error": f"Company {company_id} not found"}

        # Get candidate DNA for personalization
        dna_result = await db.execute(
            select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id)
        )
        dna = dna_result.scalar_one_or_none()
        candidate_summary = dna.experience_summary if dna else "No candidate DNA available"

        try:
            client = get_openai()

            # Build enriched prompt with web context
            web_section = ""
            if web_context:
                web_section = f"\n\nAdditional web research findings:\n{web_context}"

            prompt_filled = DOSSIER_PROMPT.format(
                company_name=company.name,
                domain=company.domain,
                industry=company.industry or "Unknown",
                size=company.size_range or "Unknown",
                location=company.location_hq or "Unknown",
                description=company.description or "No description available",
                tech_stack=", ".join(company.tech_stack or []),
                candidate_summary=candidate_summary,
            ) + web_section

            dossier_data = await client.parse_structured(
                prompt_filled, json.dumps(hunter_data), DOSSIER_SCHEMA
            )

            # Create or update dossier
            existing = await db.execute(
                select(CompanyDossier).where(CompanyDossier.company_id == company_id)
            )
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
    """Create contact records from Hunter API data."""
    company_id = uuid.UUID(state["company_id"])
    candidate_id = uuid.UUID(state["candidate_id"])
    hunter_data = state.get("hunter_data") or {}

    async with _db_mod.async_session_factory() as db:
        try:
            contacts = await _create_contacts_from_hunter(
                db, candidate_id, company_id, hunter_data
            )
            await db.commit()
        except Exception as e:
            logger.error("graph_create_contacts_failed", company_id=str(company_id), error=str(e))
            return {"status": "failed", "error": f"Contact creation failed: {e}"}

    count = len(contacts)
    logger.info("graph_create_contacts_done", company_id=str(company_id), count=count)
    return {"contacts_created": count}


async def embed_company_node(state: CompanyResearchState) -> dict:
    """Generate company embedding for vector search."""
    company_id = uuid.UUID(state["company_id"])

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"status": "failed", "error": f"Company {company_id} not found"}

        try:
            embed_text_content = f"{company.name} {company.description or ''} {company.industry or ''}"
            company.embedding = await embed_text(embed_text_content)
            company.last_enriched = datetime.now(timezone.utc)
            await db.commit()
        except Exception as e:
            logger.error("graph_embed_company_failed", company_id=str(company_id), error=str(e))
            return {"status": "failed", "error": f"Embedding failed: {e}"}

    logger.info("graph_embed_company_done", company_id=str(company_id))
    return {"embedding_set": True}


async def notify_node(state: CompanyResearchState) -> dict:
    """Mark research completed and broadcast via WebSocket."""
    company_id = uuid.UUID(state["company_id"])
    candidate_id = state["candidate_id"]
    contacts_created = state.get("contacts_created", 0)

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if company:
            company.research_status = "completed"
            await db.commit()
            company_name = company.name
        else:
            company_name = "Unknown"

    await ws_manager.broadcast(
        str(candidate_id), "research_completed",
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
    """Mark research as failed and broadcast failure notification."""
    company_id = uuid.UUID(state["company_id"])
    candidate_id = state["candidate_id"]
    error = state.get("error", "unknown error")

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if company:
            company.research_status = "failed"
            await db.commit()

    await ws_manager.broadcast(
        str(candidate_id), "research_completed",
        {"company_id": str(company_id), "status": "failed", "error": error},
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

    # Wire edges with conditional error routing
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
# Compiled graph accessors
# ---------------------------------------------------------------------------

def get_company_research_pipeline(checkpointer=None):
    """Production: compiled graph with checkpointer."""
    from app.graphs.resume_pipeline import _checkpointer as shared_checkpointer
    cp = checkpointer or shared_checkpointer
    return _builder.compile(checkpointer=cp)


def get_company_research_pipeline_no_checkpointer():
    """Testing: compiled graph without checkpointer."""
    return _builder.compile()
```

**Step 4: Run test to verify it passes**

Run: `cd jobhunter/backend && .venv/Scripts/python.exe -m pytest tests/test_company_research_graph.py -v`
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add jobhunter/backend/app/graphs/company_research.py tests/test_company_research_graph.py
git commit -m "feat: add company research LangGraph with 6 nodes and web search"
```

---

### Task 3: Write integration test for the full graph pipeline

**Files:**
- Modify: `jobhunter/backend/tests/test_company_research_graph.py`

**Step 1: Write the end-to-end graph test**

Add to `tests/test_company_research_graph.py`:

```python
from unittest.mock import AsyncMock, patch

from app.graphs.company_research import (
    CompanyResearchState,
    get_company_research_pipeline_no_checkpointer,
)


@pytest.mark.asyncio
async def test_full_pipeline_with_stubs(client, auth_headers, db_session):
    """Full graph run: enrich → web_search → dossier → contacts → embed → notify."""
    from app.config import settings

    # Get candidate ID
    resp = await client.get(f"{settings.API_V1_PREFIX}/auth/me", headers=auth_headers)
    candidate_id = resp.json()["id"]

    # Seed DNA
    from tests.conftest import seed_candidate_dna
    await seed_candidate_dna(db_session, client, auth_headers)

    # Add a company manually (uses HunterStub)
    resp = await client.post(
        f"{settings.API_V1_PREFIX}/companies/add",
        headers=auth_headers,
        json={"domain": "graphtest.com"},
    )
    assert resp.status_code == 201
    company_id = resp.json()["id"]

    # Wait briefly for background task to not interfere
    import asyncio
    await asyncio.sleep(0.5)

    # Mock web search to avoid real HTTP calls
    mock_ddgs = AsyncMock()
    mock_ddgs.atext = AsyncMock(return_value=[
        {"title": "GraphTest raises $50M", "body": "Series B funding round."},
        {"title": "GraphTest Glassdoor", "body": "Great culture, fast-paced."},
    ])
    mock_ddgs.__aenter__ = AsyncMock(return_value=mock_ddgs)
    mock_ddgs.__aexit__ = AsyncMock(return_value=False)

    with patch("app.graphs.company_research.AsyncDDGS", return_value=mock_ddgs):
        pipeline = get_company_research_pipeline_no_checkpointer()
        initial_state: CompanyResearchState = {
            "company_id": company_id,
            "candidate_id": candidate_id,
            "plan_tier": "free",
            "hunter_data": None,
            "web_context": None,
            "dossier_data": None,
            "contacts_created": 0,
            "embedding_set": False,
            "status": "pending",
            "error": None,
        }

        result = await pipeline.ainvoke(initial_state)

    assert result["status"] == "completed"
    assert result["hunter_data"] is not None
    assert result["web_context"] != ""
    assert result["dossier_data"] is not None
    assert result["contacts_created"] >= 0
    assert result["embedding_set"] is True


@pytest.mark.asyncio
async def test_pipeline_handles_missing_company():
    """Graph should fail gracefully when company doesn't exist."""
    pipeline = get_company_research_pipeline_no_checkpointer()
    initial_state: CompanyResearchState = {
        "company_id": str(uuid.uuid4()),
        "candidate_id": str(uuid.uuid4()),
        "plan_tier": "free",
        "hunter_data": None,
        "web_context": None,
        "dossier_data": None,
        "contacts_created": 0,
        "embedding_set": False,
        "status": "pending",
        "error": None,
    }

    result = await pipeline.ainvoke(initial_state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]
```

**Step 2: Run tests**

Run: `cd jobhunter/backend && .venv/Scripts/python.exe -m pytest tests/test_company_research_graph.py -v`
Expected: 4 PASSED

**Step 3: Commit**

```bash
git add tests/test_company_research_graph.py
git commit -m "test: add integration tests for company research graph pipeline"
```

---

### Task 4: Wire graph into the API endpoint

**Files:**
- Modify: `jobhunter/backend/app/api/companies.py:237-279` (`_research_background`)

**Step 1: Rewrite `_research_background` to use the graph**

Replace `_research_background` (lines 237-279) in `companies.py`:

```python
async def _research_background(company_id):
    from app.infrastructure.database import async_session_factory

    async with async_session_factory() as db:
        try:
            # Look up company and candidate info for quota + graph input
            result = await db.execute(select(Company).where(Company.id == company_id))
            company = result.scalar_one_or_none()
            if not company:
                logger.error("background_research_company_not_found", company_id=str(company_id))
                return

            cid = str(company.candidate_id)
            candidate_id = str(company.candidate_id)

            # Fetch candidate to get plan_tier
            from app.models.candidate import Candidate as _Candidate
            cand_result = await db.execute(
                select(_Candidate).where(_Candidate.id == company.candidate_id)
            )
            cand = cand_result.scalar_one_or_none()
            tier = cand.plan_tier if cand else "free"

            # Check quotas before running graph
            await check_and_increment(cid, "research", tier)
            await check_and_increment(cid, "openai", tier)
        except Exception as e:
            logger.error("background_research_quota_failed", error=str(e), company_id=str(company_id))
            try:
                result = await db.execute(select(Company).where(Company.id == company_id))
                c = result.scalar_one_or_none()
                if c:
                    c.research_status = "failed"
                    await db.commit()
            except Exception:
                pass
            return

    # Run the LangGraph pipeline
    try:
        from app.graphs.company_research import (
            CompanyResearchState,
            get_company_research_pipeline,
        )

        pipeline = get_company_research_pipeline()
        initial_state: CompanyResearchState = {
            "company_id": str(company_id),
            "candidate_id": candidate_id,
            "plan_tier": tier,
            "hunter_data": None,
            "web_context": None,
            "dossier_data": None,
            "contacts_created": 0,
            "embedding_set": False,
            "status": "pending",
            "error": None,
        }

        await pipeline.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": f"company-research-{company_id}"}},
        )
    except Exception as e:
        logger.error("background_research_graph_failed", error=str(e), company_id=str(company_id))
        # Mark as failed if the graph itself crashes
        from app.infrastructure.database import async_session_factory
        async with async_session_factory() as db:
            try:
                result = await db.execute(select(Company).where(Company.id == company_id))
                company = result.scalar_one_or_none()
                if company and company.research_status != "failed":
                    company.research_status = "failed"
                    await db.commit()
            except Exception:
                pass
```

**Step 2: Run the full test suite**

Run: `cd jobhunter/backend && .venv/Scripts/python.exe -m pytest tests/ -v`
Expected: All tests pass (existing company tests + new graph tests)

**Step 3: Commit**

```bash
git add jobhunter/backend/app/api/companies.py
git commit -m "feat: wire company research graph into API endpoint"
```

---

### Task 5: Remove dead code from company_service.py

**Files:**
- Modify: `jobhunter/backend/app/services/company_service.py:371-449`

**Step 1: Remove `research_company` function**

The `research_company()` function at lines 371-449 in `company_service.py` is now dead code - the graph handles all research. Delete lines 371-449 entirely.

Also remove the unused imports that were only needed by `research_company()`: `json` (line 1) and `datetime, timezone` (line 3) - but check if they're used elsewhere in the file first.

Keep `json` since it's used in `discover_companies`. Keep `datetime, timezone` only if used elsewhere.

**Step 2: Run tests**

Run: `cd jobhunter/backend && .venv/Scripts/python.exe -m pytest tests/ -v`
Expected: All tests still pass

**Step 3: Commit**

```bash
git add jobhunter/backend/app/services/company_service.py
git commit -m "refactor: remove dead research_company function (replaced by graph)"
```

---

### Task 6: Update project-report.html

**Files:**
- Modify: `project-report.html`

**Step 1: Update the Company Research Graph chip**

In `project-report.html`, find the Phase 2 section and update the "Company Research Graph" chip to include the `done` class, matching the pattern of other completed chips.

Find the chip that says "Company Research Graph" and add the `done` CSS class to it.

**Step 2: Commit**

```bash
git add project-report.html
git commit -m "docs: mark Company Research Graph as done in project report"
```

---

## Verification Checklist

1. `pip install duckduckgo-search` succeeds
2. `pytest tests/test_company_research_graph.py -v` - 4 tests pass
3. `pytest tests/ -v` - full suite passes (no regressions)
4. Graph has 7 nodes: enrich_company, web_search, generate_dossier, create_contacts, embed_company, notify, mark_failed
5. `_research_background` in companies.py now calls the graph instead of `company_service.research_company`
6. `research_company()` is removed from company_service.py
7. Web search node gracefully degrades (returns empty string on failure)
8. Project report HTML updated with Company Research Graph marked done
