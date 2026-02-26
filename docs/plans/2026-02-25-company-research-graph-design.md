# Company Research Graph — Design

## Context

Company research currently runs as a monolithic function (`company_service.research_company()`) that calls Hunter API, generates an AI dossier via OpenAI, creates contacts, and generates embeddings — all in one big try/except. If it crashes halfway through, the entire process must restart from scratch.

**Goal**: Convert to a LangGraph StateGraph with per-node checkpointing (crash recovery), add a web search node for grounded dossier generation, and follow the same pattern as the existing resume pipeline.

## Architecture

6-node StateGraph with conditional error routing:

```
START
  ↓
enrich_company (Hunter API domain_search → populate company fields)
  ↓ [check error] → mark_failed → END
  ↓
web_search (DuckDuckGo search for news, glassdoor, funding)  ← NEW
  ↓ [check error] → mark_failed → END
  ↓
generate_dossier (OpenAI structured output → CompanyDossier, enriched with web data)
  ↓ [check error] → mark_failed → END
  ↓
create_contacts (parse Hunter emails → Contact records)
  ↓ [check error] → mark_failed → END
  ↓
embed_company (generate embedding → vector search)
  ↓
notify (mark completed, WebSocket broadcast)
  ↓
END
```

## State Schema

```python
class CompanyResearchState(TypedDict):
    company_id: str
    candidate_id: str
    plan_tier: str
    hunter_data: dict | None
    web_context: str | None
    dossier_data: dict | None
    contacts_created: int
    embedding_set: bool
    status: str        # "pending" | "completed" | "failed"
    error: str | None
```

## Node Details

### 1. enrich_company
- Loads Company from DB by `company_id`
- Calls `hunter.domain_search(company.domain)`
- Saves Hunter enrichment data (industry, size, description) to Company record
- Returns `hunter_data` for downstream nodes

### 2. web_search (NEW)
- Uses `duckduckgo-search` library (free, no API key)
- Searches: `"{name} glassdoor reviews"`, `"{name} recent news 2026"`, `"{name} {industry} funding"`
- Concatenates top results into `web_context` string (max ~2000 chars)
- Graceful degradation: if search fails, sets `web_context = ""` (doesn't fail the pipeline)

### 3. generate_dossier
- Loads candidate DNA for personalization
- Builds prompt from `DOSSIER_PROMPT` + `web_context` from previous node
- Calls `client.parse_structured()` with `DOSSIER_SCHEMA`
- Creates/updates `CompanyDossier` record in DB

### 4. create_contacts
- Parses Hunter domain_search emails from `hunter_data`
- Creates `Contact` records linked to company
- Returns `contacts_created` count

### 5. embed_company
- Generates embedding from `company.description + company.industry`
- Sets `company.embedding` for vector similarity search
- Sets `company.last_enriched` timestamp

### 6. notify
- Sets `company.research_status = "completed"`
- Broadcasts WebSocket: `"research_completed"` with company_id, status, contacts_created

### mark_failed (error handler)
- Sets `company.research_status = "failed"`
- Broadcasts WebSocket: `"research_completed"` with status="failed" and error message

## Integration

- Quota checks remain in `_research_background()` before graph invocation
- Reuses shared PostgreSQL checkpointer from resume pipeline (`init_checkpointer`)
- New file: `backend/app/graphs/company_research.py`
- Modify: `backend/app/api/companies.py` to call graph instead of `company_service.research_company()`
- New dependency: `duckduckgo-search` in `pyproject.toml`

## Error Handling

Same pattern as resume pipeline: each node wraps in try/except, sets `status="failed"` + `error`, conditional edges route to `mark_failed` → END.
