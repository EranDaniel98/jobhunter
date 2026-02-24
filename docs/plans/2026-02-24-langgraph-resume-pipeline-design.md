# LangGraph Resume Pipeline — Design Document

**Date:** 2026-02-24
**Status:** Approved
**Issue:** #3 (LangGraph orchestration)

## Goal

Replace the monolithic `_run_async_background()` function in `candidates.py` with a LangGraph StateGraph that processes resumes through independently checkpointed nodes. This enables crash recovery, per-node retries, and a clear separation of processing stages.

## Architecture

The resume processing pipeline becomes a directed graph of 5 processing nodes + 1 error-handling node, orchestrated by LangGraph's StateGraph. PostgreSQL-backed checkpointing (via `langgraph-checkpoint-postgres`) persists intermediate state between nodes, so a server crash or transient OpenAI failure doesn't require re-running the entire pipeline.

**Current flow** (monolithic):
```
_run_async_background() → parse → generate_dna → mark_complete → recalculate_fits → notify
```

**New flow** (graph):
```
START → parse_resume → extract_skills → generate_dna → recalculate_fits → notify → END
                \              \              \               \
                 → → → → → → mark_failed ← ← ← ← ← ← ← ← ←  (on error)
```

## State Schema

```python
class ResumeProcessingState(TypedDict):
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
    status: str              # "completed" | "failed"
    error: str | None
```

All fields are JSON-serializable for checkpointing.

## Graph Nodes

1. **parse_resume** — Load resume from DB, call OpenAI structured parse, save `parsed_data` to Resume table and state.
2. **extract_skills** — Read `raw_text` from state, call OpenAI skills extraction, write `skills_data` to state.
3. **generate_dna** — Read `parsed_data` + `skills_data`, generate DNA summary + embeddings, create CandidateDNA and Skill records in DB.
4. **recalculate_fits** — Recompute cosine similarity fit scores for all suggested/approved companies.
5. **notify** — Mark resume as completed, send WebSocket notification.
6. **mark_failed** — Error handler: mark resume as failed, send error notification.

## Checkpointing

- **Library:** `langgraph-checkpoint-postgres` (async, uses existing asyncpg driver)
- **Thread ID:** `resume:{resume_id}` — enables status queries and resume-from-failure
- **Setup:** `checkpointer.setup()` called in FastAPI lifespan (creates tables automatically)
- **Retention:** ARQ cron job cleans up checkpoints older than 7 days

## Integration

- `candidates.py` `_run_async_background()` → calls `graph.ainvoke()` instead of sequential functions
- `resume_service.py` → existing logic refactored into node functions
- `company_service.py` → `recalculate_fit_scores()` unchanged, called from graph node
- New file: `app/graphs/resume_pipeline.py`
- New deps: `langgraph>=0.4.0`, `langgraph-checkpoint-postgres>=2.0.0`
- No API changes, no frontend changes, no ARQ changes

## Error Handling

- Each node catches exceptions and writes to `state["error"]`
- Conditional edges route to `mark_failed` on error
- Retry = re-invoke graph with same thread_id → resumes from last checkpoint
- No duplicate OpenAI calls for already-completed nodes

## New Dependencies

```
langgraph>=0.4.0
langgraph-checkpoint-postgres>=2.0.0
```

Transitive: `langchain-core` (lightweight, no full LangChain required).
