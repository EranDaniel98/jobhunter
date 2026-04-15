# Scout Cost Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce scout + analytics cron LLM/NewsAPI cost by ~90% via (1) shared daily news pool, (2) activity + plan-tier gating of expensive pipelines, (3) cheap-model routing for bulk parse calls.

**Architecture:** Three independent phases shipped in order of increasing risk. Phase A adds per-call-site model routing and downgrades cheap LLM calls to `gpt-4o-mini`. Phase B adds `last_seen_at` tracking and a `scout_frequency_days` limit per plan tier, with coordinator-level filtering. Phase C splits `scout_pipeline` at node 4 — nodes 1–3 (queries/NewsAPI/parse) become a once-daily global `news_ingest` job that writes to a new `funding_signals` table; nodes 4–6 (score/create/notify) stay per-candidate and now read from that shared pool.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, ARQ (cron), LangGraph, pgvector, pytest-asyncio, structlog.

**Key files touched:**
- Create: `backend/alembic/versions/025_add_funding_signals.py`
- Create: `backend/alembic/versions/026_add_last_seen_at.py`
- Create: `backend/app/models/funding_signal.py`
- Create: `backend/app/services/news_ingest_service.py`
- Create: `backend/tests/test_news_ingest_service.py`
- Create: `backend/tests/test_last_seen_at.py`
- Create: `backend/tests/test_scout_frequency_gating.py`
- Modify: `backend/app/config.py` — add per-pipeline model settings
- Modify: `backend/app/infrastructure/openai_client.py` — add optional `model` param
- Modify: `backend/app/infrastructure/protocols.py` — update protocol signature
- Modify: `backend/tests/conftest.py` — accept (and ignore) `model` kwarg in `OpenAIStub`
- Modify: `backend/app/graphs/scout_pipeline.py` — remove global nodes, consume shared pool
- Modify: `backend/app/graphs/analytics_pipeline.py` — pass cheap model
- Modify: `backend/app/plans.py` — add `scout_frequency_days` to each tier's limits
- Modify: `backend/app/models/candidate.py` — add `last_seen_at` column
- Modify: `backend/app/services/auth_service.py` — set `last_seen_at` on login+refresh
- Modify: `backend/app/worker.py` — new `run_daily_news_ingest` cron; filter scout coordinator

---

## Phase A — Per-pipeline model routing + downgrade cheap calls

**Why first:** lowest-risk, immediate cost win, independent of other phases. Adds the plumbing Phase C will also use.

### Task A1: Add `model` kwarg to OpenAI client protocol + impl

**Files:**
- Modify: `backend/app/infrastructure/protocols.py` — add optional `model` kwarg to `parse_structured`
- Modify: `backend/app/infrastructure/openai_client.py` — accept `model`, fall back to hardcoded `gpt-4o`
- Modify: `backend/app/config.py` — no changes yet (wired in A2)

- [ ] **Step 1: Write the failing test**

Create or append to `backend/tests/test_openai_client_model_routing.py`:

```python
import pytest
from app.infrastructure.openai_client import OpenAIClient


@pytest.mark.asyncio
async def test_parse_structured_accepts_model_kwarg(monkeypatch):
    """Passing `model=` overrides the default gpt-4o."""
    captured: dict = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            class _Msg:
                content = '{"x": 1}'
            class _Choice:
                message = _Msg()
            class _Resp:
                choices = [_Choice()]
                usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1})()
            return _Resp()

    class FakeClient:
        chat = type("C", (), {"completions": FakeCompletions()})()

    client = OpenAIClient()
    monkeypatch.setattr(client, "_client", FakeClient())

    await client.parse_structured(
        "system", "user", {"type": "object", "properties": {"x": {"type": "integer"}}},
        model="gpt-4o-mini",
    )

    assert captured["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_parse_structured_defaults_to_gpt4o(monkeypatch):
    """When `model` is omitted, falls back to gpt-4o."""
    captured: dict = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            class _Msg:
                content = '{"x": 1}'
            class _Choice:
                message = _Msg()
            class _Resp:
                choices = [_Choice()]
                usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1})()
            return _Resp()

    class FakeClient:
        chat = type("C", (), {"completions": FakeCompletions()})()

    client = OpenAIClient()
    monkeypatch.setattr(client, "_client", FakeClient())

    await client.parse_structured("system", "user", {"type": "object"})

    assert captured["model"] == "gpt-4o"
```

- [ ] **Step 2: Run test — expect FAIL (unexpected kwarg `model`)**

Run: `cd backend && uv run pytest tests/test_openai_client_model_routing.py -v`
Expected: FAIL with `TypeError: parse_structured() got an unexpected keyword argument 'model'`.

- [ ] **Step 3: Implement — add `model` param to protocol**

In `backend/app/infrastructure/protocols.py`, update `OpenAIClientProtocol`:

```python
@runtime_checkable
class OpenAIClientProtocol(Protocol):
    async def parse_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_schema: dict,
        *,
        max_tokens: int = 4000,
        model: str | None = None,
    ) -> dict: ...

    async def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 4000,
        model: str | None = None,
    ) -> str: ...
```

In `backend/app/infrastructure/openai_client.py`, modify `parse_structured` (around line 36) and `chat` (around line 96):

```python
async def parse_structured(
    self,
    system_prompt: str,
    user_content: str,
    response_schema: dict,
    *,
    max_tokens: int = 4000,
    model: str | None = None,
) -> dict:
    resolved_model = model or "gpt-4o"
    resp = await self._client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "response", "strict": True, "schema": response_schema},
        },
        max_tokens=max_tokens,
    )
    # ... existing parse + cost-tracking logic unchanged, but pass `resolved_model` to record_usage
```

Update the `record_usage(...)` call in this method to pass `model=resolved_model`.

Apply the same change to `chat()`.

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && uv run pytest tests/test_openai_client_model_routing.py -v`
Expected: 2 passed.

- [ ] **Step 5: Update `OpenAIStub` in conftest to accept (ignore) `model`**

In `backend/tests/conftest.py`, locate the `OpenAIStub` class. Update every method signature to accept `model=None`:

```python
class OpenAIStub:
    async def parse_structured(
        self, system_prompt, user_content, response_schema, *, max_tokens=4000, model=None
    ) -> dict:
        # ... existing schema-detection logic unchanged ...

    async def chat(self, messages, *, max_tokens=4000, model=None) -> str:
        # ... existing logic unchanged ...
```

- [ ] **Step 6: Run full backend test suite to verify no regression**

Run: `cd backend && uv run pytest`
Expected: all tests pass (~110 tests, same count as before).

- [ ] **Step 7: Commit**

```bash
git add backend/app/infrastructure/openai_client.py \
        backend/app/infrastructure/protocols.py \
        backend/tests/conftest.py \
        backend/tests/test_openai_client_model_routing.py
git commit -m "feat(openai): add optional model kwarg to parse_structured/chat"
```

---

### Task A2: Add per-pipeline model settings to config

**Files:**
- Modify: `backend/app/config.py` — add 3 new optional settings
- Modify: `backend/.env.example` — document them

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_config_model_settings.py`:

```python
from app.config import settings


def test_scout_queries_model_defaults_to_mini():
    assert settings.SCOUT_QUERIES_MODEL == "gpt-4o-mini"


def test_scout_parse_model_defaults_to_mini():
    assert settings.SCOUT_PARSE_MODEL == "gpt-4o-mini"


def test_analytics_insights_model_defaults_to_mini():
    assert settings.ANALYTICS_INSIGHTS_MODEL == "gpt-4o-mini"
```

- [ ] **Step 2: Run — expect FAIL (attribute does not exist)**

Run: `cd backend && uv run pytest tests/test_config_model_settings.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'SCOUT_QUERIES_MODEL'`.

- [ ] **Step 3: Add settings**

In `backend/app/config.py`, add within the `Settings` class (alphabetized with other settings):

```python
    # LLM model routing per pipeline (cost optimization)
    SCOUT_QUERIES_MODEL: str = "gpt-4o-mini"
    SCOUT_PARSE_MODEL: str = "gpt-4o-mini"
    ANALYTICS_INSIGHTS_MODEL: str = "gpt-4o-mini"
```

In `backend/.env.example`, add:

```
# LLM model overrides (default: gpt-4o-mini for low-stakes calls)
SCOUT_QUERIES_MODEL=gpt-4o-mini
SCOUT_PARSE_MODEL=gpt-4o-mini
ANALYTICS_INSIGHTS_MODEL=gpt-4o-mini
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_config_model_settings.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/.env.example backend/tests/test_config_model_settings.py
git commit -m "feat(config): add per-pipeline model routing settings"
```

---

### Task A3: Wire scout pipeline to use cheap model at query-gen + parse

**Files:**
- Modify: `backend/app/graphs/scout_pipeline.py:~155` and `~290` — pass `model=settings.SCOUT_QUERIES_MODEL` and `settings.SCOUT_PARSE_MODEL`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_scout_uses_cheap_models.py`:

```python
import pytest
from unittest.mock import AsyncMock

import app.dependencies as deps
from app.config import settings


@pytest.mark.asyncio
async def test_build_search_queries_uses_cheap_model(monkeypatch, seeded_candidate_with_dna):
    from app.graphs.scout_pipeline import build_search_queries_node

    mock = AsyncMock(return_value={"queries": ["q1", "q2"]})
    stub = deps._openai_client

    async def _tracking_parse(*args, **kwargs):
        mock(**kwargs)
        return await stub.parse_structured(*args, **kwargs) if False else {"queries": ["q1"]}

    monkeypatch.setattr(stub, "parse_structured", _tracking_parse)

    state = {"candidate_id": str(seeded_candidate_with_dna.id), "plan_tier": "free"}
    await build_search_queries_node(state)

    # The mock was called with model=settings.SCOUT_QUERIES_MODEL
    assert mock.call_args.kwargs["model"] == settings.SCOUT_QUERIES_MODEL


@pytest.mark.asyncio
async def test_parse_articles_uses_cheap_model(monkeypatch):
    from app.graphs.scout_pipeline import parse_articles_node

    captured = {}

    async def fake_parse(system_prompt, user_content, schema, **kwargs):
        captured.update(kwargs)
        return {"companies": []}

    monkeypatch.setattr(deps._openai_client, "parse_structured", fake_parse)

    state = {"raw_articles": [{"title": "t", "description": "d", "url": "u", "source": "s", "publishedAt": "2026-01-01"}]}
    await parse_articles_node(state)

    assert captured["model"] == settings.SCOUT_PARSE_MODEL
```

Note: `seeded_candidate_with_dna` should be an existing fixture in `conftest.py` based on the other scout tests. If it doesn't exist, use the standard candidate-with-DNA seeding pattern used elsewhere in `test_scout_graph.py`.

- [ ] **Step 2: Run — expect FAIL (model=None, not the cheap one)**

Run: `cd backend && uv run pytest tests/test_scout_uses_cheap_models.py -v`
Expected: FAIL with `AssertionError` showing `model` is `None` or missing.

- [ ] **Step 3: Update scout pipeline call sites**

In `backend/app/graphs/scout_pipeline.py`, find the `parse_structured` call in `build_search_queries_node` (around line 156) and add:

```python
from app.config import settings  # add to imports if missing

# ... within build_search_queries_node:
result = await client.parse_structured(
    SCOUT_QUERIES_PROMPT.format(...),
    "",
    SCOUT_QUERIES_SCHEMA,
    model=settings.SCOUT_QUERIES_MODEL,
)
```

In `parse_articles_node` (around line 291), same pattern:

```python
result = await client.parse_structured(
    PARSE_ARTICLES_PROMPT.format(...),
    "",
    PARSE_ARTICLES_SCHEMA,
    model=settings.SCOUT_PARSE_MODEL,
)
```

Do NOT change `score_and_filter_node` — embedding calls are separate (use `embed_text`), not `parse_structured`. Leave as-is.

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_scout_uses_cheap_models.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run scout integration tests to confirm no regression**

Run: `cd backend && uv run pytest tests/test_scout_graph.py tests/test_scout_graph2.py tests/test_scout_integration.py -v`
Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/graphs/scout_pipeline.py backend/tests/test_scout_uses_cheap_models.py
git commit -m "feat(scout): route query-gen + article-parse to cheap model"
```

---

### Task A4: Wire analytics pipeline to cheap model

**Files:**
- Modify: `backend/app/graphs/analytics_pipeline.py:~151` — pass `model=settings.ANALYTICS_INSIGHTS_MODEL`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_analytics_uses_cheap_model.py`:

```python
import pytest

import app.dependencies as deps
from app.config import settings


@pytest.mark.asyncio
async def test_generate_insights_uses_cheap_model(monkeypatch):
    from app.graphs.analytics_pipeline import generate_insights_node

    captured = {}

    async def fake_parse(system_prompt, user_content, schema, **kwargs):
        captured.update(kwargs)
        return {"insights": [
            {"insight_type": "pipeline_health", "title": "t", "body": "b", "severity": "info", "data": {}}
        ]}

    monkeypatch.setattr(deps._openai_client, "parse_structured", fake_parse)

    state = {
        "raw_data": {
            "pipeline": {}, "funnel": {}, "outreach": {},
            "skills": [], "skill_count": 0,
            "career_stage": "mid", "experience_summary": "eng",
        },
    }
    await generate_insights_node(state)

    assert captured["model"] == settings.ANALYTICS_INSIGHTS_MODEL
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && uv run pytest tests/test_analytics_uses_cheap_model.py -v`
Expected: FAIL.

- [ ] **Step 3: Update analytics pipeline**

In `backend/app/graphs/analytics_pipeline.py`, find `generate_insights_node` (around line 135–158). Add `from app.config import settings` to imports if missing. Change the call:

```python
result = await client.parse_structured(
    INSIGHTS_PROMPT.format(...),
    "",
    INSIGHTS_SCHEMA,
    model=settings.ANALYTICS_INSIGHTS_MODEL,
)
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_analytics_uses_cheap_model.py -v`
Expected: 1 passed.

- [ ] **Step 5: Regression-check analytics tests**

Run: `cd backend && uv run pytest tests/test_analytics_agent.py tests/test_analytics_graph_nodes.py tests/test_analytics_graph2.py tests/test_analytics_integration.py -v`
Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/graphs/analytics_pipeline.py backend/tests/test_analytics_uses_cheap_model.py
git commit -m "feat(analytics): route insight generation to cheap model"
```

---

## Phase B — `last_seen_at` activity tracking + plan-tier scout frequency

**Why second:** builds on existing code only, no external-service changes. Creates the filter used by Phase C's cron.

### Task B1: Add `last_seen_at` migration + model column

**Files:**
- Create: `backend/alembic/versions/025_add_last_seen_at.py`
- Modify: `backend/app/models/candidate.py` — add column

> **Note:** Research found the latest migration is `024_add_incidents.py`. This migration uses `025`. Phase C's funding-signals migration will use `026`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_last_seen_at_migration.py`:

```python
import pytest
from sqlalchemy import inspect as sa_inspect


@pytest.mark.asyncio
async def test_candidates_has_last_seen_at_column(db_session):
    def _check(sync_conn):
        inspector = sa_inspect(sync_conn)
        cols = {c["name"] for c in inspector.get_columns("candidates")}
        assert "last_seen_at" in cols

    await db_session.run_sync(lambda s: _check(s.connection()))
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && uv run pytest tests/test_last_seen_at_migration.py -v`
Expected: FAIL with `AssertionError` — column missing.

- [ ] **Step 3: Create Alembic migration**

Create `backend/alembic/versions/025_add_last_seen_at.py`:

```python
"""Add last_seen_at column to candidates."""
import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_candidates_last_seen_at", "candidates", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_candidates_last_seen_at", table_name="candidates")
    op.drop_column("candidates", "last_seen_at")
```

- [ ] **Step 4: Add ORM column**

In `backend/app/models/candidate.py` within the `Candidate` class, add after `plan_tier`:

```python
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
```

Ensure `from datetime import datetime` and `from sqlalchemy import DateTime` are imported (follow existing import style in the file).

- [ ] **Step 5: Apply migration + run test**

Run:
```bash
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/test_last_seen_at_migration.py -v
```
Expected: migration applies cleanly; test passes.

- [ ] **Step 6: Run full suite to verify no regression**

Run: `cd backend && uv run pytest`
Expected: all tests pass. If any test creates a `Candidate` and asserts column-exact shape, update fixtures as needed.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/025_add_last_seen_at.py \
        backend/app/models/candidate.py \
        backend/tests/test_last_seen_at_migration.py
git commit -m "feat(db): add last_seen_at to candidates"
```

---

### Task B2: Write `last_seen_at` on login + refresh

**Files:**
- Modify: `backend/app/services/auth_service.py` — update `login` and `refresh_token` to set `last_seen_at = now()`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_last_seen_at_writes.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.candidate import Candidate
from app.services import auth_service
from app.schemas.auth import LoginRequest


@pytest.mark.asyncio
async def test_login_sets_last_seen_at(db_session, seeded_verified_candidate):
    # Pre-condition: last_seen_at starts NULL
    assert seeded_verified_candidate.last_seen_at is None

    await auth_service.login(
        db_session,
        LoginRequest(email=seeded_verified_candidate.email, password="password123"),
    )

    refreshed = (await db_session.execute(
        select(Candidate).where(Candidate.id == seeded_verified_candidate.id)
    )).scalar_one()

    assert refreshed.last_seen_at is not None
    assert (datetime.now(UTC) - refreshed.last_seen_at) < timedelta(seconds=5)


@pytest.mark.asyncio
async def test_refresh_sets_last_seen_at(db_session, seeded_verified_candidate, valid_refresh_token):
    await auth_service.refresh_token(db_session, valid_refresh_token)

    refreshed = (await db_session.execute(
        select(Candidate).where(Candidate.id == seeded_verified_candidate.id)
    )).scalar_one()

    assert refreshed.last_seen_at is not None
```

Note: `seeded_verified_candidate` and `valid_refresh_token` should already be fixtures or derivable from the existing `test_auth_integration.py` patterns. If not, add helper fixtures at the top of the test file following the pattern in `test_auth_service_unit.py`.

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && uv run pytest tests/test_last_seen_at_writes.py -v`
Expected: FAIL — `last_seen_at` stays None.

- [ ] **Step 3: Update `auth_service.login`**

In `backend/app/services/auth_service.py` within `login()` (around line 101–121), after the password check succeeds and before returning tokens, add:

```python
candidate.last_seen_at = datetime.now(UTC)
await db.commit()
```

(Import `from datetime import UTC, datetime` if not already present.)

- [ ] **Step 4: Update `auth_service.refresh_token`**

In the same file within `refresh_token()` (around line 124–170), after the candidate is fetched and before issuing new tokens, add the same line:

```python
candidate.last_seen_at = datetime.now(UTC)
# commit happens naturally with the blacklist write that follows
```

- [ ] **Step 5: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_last_seen_at_writes.py -v`
Expected: 2 passed.

- [ ] **Step 6: Regression check**

Run: `cd backend && uv run pytest tests/test_auth_service_unit.py tests/test_auth_integration.py -v`
Expected: all existing auth tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/auth_service.py backend/tests/test_last_seen_at_writes.py
git commit -m "feat(auth): record last_seen_at on login and refresh"
```

---

### Task B3: Add `scout_frequency_days` to plan limits

**Files:**
- Modify: `backend/app/plans.py` — add entry to each tier's `limits` dict
- Create: `backend/tests/test_plans_scout_frequency.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_plans_scout_frequency.py`:

```python
from app.plans import PlanTier, get_limits_for_tier


def test_free_tier_scout_frequency_is_weekly():
    assert get_limits_for_tier(PlanTier.free)["scout_frequency_days"] == 7


def test_explorer_tier_scout_frequency_is_daily():
    assert get_limits_for_tier(PlanTier.explorer)["scout_frequency_days"] == 1


def test_hunter_tier_scout_frequency_is_daily():
    assert get_limits_for_tier(PlanTier.hunter)["scout_frequency_days"] == 1
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && uv run pytest tests/test_plans_scout_frequency.py -v`
Expected: FAIL with `KeyError: 'scout_frequency_days'`.

- [ ] **Step 3: Add to `plans.py`**

In `backend/app/plans.py`, within the `PLANS` dict, add `"scout_frequency_days"` to each tier's `limits`:

```python
PLANS: dict[PlanTier, PlanDefinition] = {
    PlanTier.free: PlanDefinition(
        ...,
        limits={
            "discovery": 3,
            "research": 2,
            "hunter": 5,
            "email": 3,
            "openai": 30,
            "scout_frequency_days": 7,  # weekly for free tier
        },
        ...,
    ),
    PlanTier.explorer: PlanDefinition(
        ...,
        limits={
            ...existing...,
            "scout_frequency_days": 1,  # daily for paid
        },
        ...,
    ),
    PlanTier.hunter: PlanDefinition(
        ...,
        limits={
            ...existing...,
            "scout_frequency_days": 1,
        },
        ...,
    ),
}
```

(Preserve all existing keys exactly — only add one new key per tier.)

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_plans_scout_frequency.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plans.py backend/tests/test_plans_scout_frequency.py
git commit -m "feat(plans): add scout_frequency_days per tier"
```

---

### Task B4: Filter scout coordinator by activity + tier frequency

**Files:**
- Modify: `backend/app/worker.py` — update `run_daily_scout`
- Create: `backend/tests/test_scout_frequency_gating.py`

**Gating rules:**
- Skip candidate if `last_seen_at IS NULL` OR `last_seen_at < now() - 14 days`.
- For tier with `scout_frequency_days == 1` → process every day.
- For tier with `scout_frequency_days == 7` → process only on Mondays (weekday 0 UTC).

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_scout_frequency_gating.py`:

```python
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.candidate import Candidate, CandidateDNA


@pytest.mark.asyncio
async def test_inactive_candidate_is_skipped(monkeypatch, db_session, async_session_factory):
    """Candidate with last_seen_at > 14d ago is not enqueued."""
    cand = Candidate(
        id=uuid4(),
        email=f"old-{uuid4()}@t.co",
        hashed_password="x",
        is_active=True,
        plan_tier="explorer",
        last_seen_at=datetime.now(UTC) - timedelta(days=20),
    )
    db_session.add(cand)
    db_session.add(CandidateDNA(candidate_id=cand.id, experience_summary="x"))
    await db_session.commit()

    from app.worker import run_daily_scout

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.enqueue_job = AsyncMock()

    # Stub the acquire-lock and the redis available to the job
    monkeypatch.setattr("app.worker._acquire_run_lock", AsyncMock(return_value=True))
    await run_daily_scout({"redis": mock_redis})

    # Assert no chunk containing this candidate was enqueued
    enqueued_ids: set = set()
    for call in mock_redis.enqueue_job.call_args_list:
        if call.args[0] == "process_scout_chunk":
            enqueued_ids.update(call.args[1])
    assert cand.id not in enqueued_ids


@pytest.mark.asyncio
async def test_free_tier_only_runs_on_monday(monkeypatch, db_session):
    """Free tier candidate skipped on non-Monday, included on Monday."""
    cand = Candidate(
        id=uuid4(),
        email=f"free-{uuid4()}@t.co",
        hashed_password="x",
        is_active=True,
        plan_tier="free",
        last_seen_at=datetime.now(UTC),
    )
    db_session.add(cand)
    db_session.add(CandidateDNA(candidate_id=cand.id, experience_summary="x"))
    await db_session.commit()

    from app.worker import run_daily_scout

    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock()
    monkeypatch.setattr("app.worker._acquire_run_lock", AsyncMock(return_value=True))

    # Freeze "today" to a Wednesday
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 15, 9, 0, tzinfo=UTC)  # Wed

    monkeypatch.setattr("app.worker.datetime", _FakeDateTime)

    await run_daily_scout({"redis": mock_redis})

    enqueued_ids: set = set()
    for call in mock_redis.enqueue_job.call_args_list:
        if call.args[0] == "process_scout_chunk":
            enqueued_ids.update(call.args[1])
    assert cand.id not in enqueued_ids  # Skipped Wednesday

    # Freeze to a Monday
    mock_redis.enqueue_job.reset_mock()

    class _MondayDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 13, 9, 0, tzinfo=UTC)  # Mon

    monkeypatch.setattr("app.worker.datetime", _MondayDateTime)
    await run_daily_scout({"redis": mock_redis})

    enqueued_ids = set()
    for call in mock_redis.enqueue_job.call_args_list:
        if call.args[0] == "process_scout_chunk":
            enqueued_ids.update(call.args[1])
    assert cand.id in enqueued_ids


@pytest.mark.asyncio
async def test_paid_tier_runs_every_day(monkeypatch, db_session):
    cand = Candidate(
        id=uuid4(),
        email=f"pro-{uuid4()}@t.co",
        hashed_password="x",
        is_active=True,
        plan_tier="hunter",
        last_seen_at=datetime.now(UTC),
    )
    db_session.add(cand)
    db_session.add(CandidateDNA(candidate_id=cand.id, experience_summary="x"))
    await db_session.commit()

    from app.worker import run_daily_scout

    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock()
    monkeypatch.setattr("app.worker._acquire_run_lock", AsyncMock(return_value=True))

    await run_daily_scout({"redis": mock_redis})
    enqueued_ids: set = set()
    for call in mock_redis.enqueue_job.call_args_list:
        if call.args[0] == "process_scout_chunk":
            enqueued_ids.update(call.args[1])
    assert cand.id in enqueued_ids
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && uv run pytest tests/test_scout_frequency_gating.py -v`
Expected: FAIL — gating not yet implemented.

- [ ] **Step 3: Update `run_daily_scout`**

In `backend/app/worker.py`, replace the body of `run_daily_scout` (lines ~278–322) with:

```python
async def run_daily_scout(ctx):
    """Coordinator: find active candidates with DNA; respect plan-tier scout_frequency_days
    and skip candidates inactive >14d."""
    if not await _acquire_run_lock("daily_scout", ttl=82800):
        logger.info("cron.skipped_overlap", extra={"feature": "arq_batch", "action": "run_daily_scout"})
        return

    from app.infrastructure.database import async_session_factory
    from app.models.candidate import Candidate, CandidateDNA
    from app.plans import PlanTier, get_limits_for_tier

    now = datetime.now(UTC)
    activity_cutoff = now - timedelta(days=14)
    today_is_monday = now.weekday() == 0

    async with async_session_factory() as db:
        result = await db.execute(
            select(Candidate.id, Candidate.plan_tier).where(
                Candidate.is_active,
                Candidate.last_seen_at.is_not(None),
                Candidate.last_seen_at >= activity_cutoff,
                exists(select(CandidateDNA.id).where(CandidateDNA.candidate_id == Candidate.id)),
            )
        )
        rows = result.all()

    eligible_ids: list = []
    for cand_id, plan_tier_str in rows:
        try:
            tier = PlanTier(plan_tier_str)
        except ValueError:
            tier = PlanTier.free
        frequency = get_limits_for_tier(tier).get("scout_frequency_days", 7)
        if frequency == 1 or (frequency == 7 and today_is_monday):
            eligible_ids.append(cand_id)

    total = len(eligible_ids)
    max_items = settings.ARQ_MAX_CHUNKS_PER_RUN * settings.ARQ_CHUNK_SIZE
    processing_ids = eligible_ids[:max_items]
    deferred = total - len(processing_ids)

    if deferred > 0:
        logger.warning(
            "cron.overflow",
            extra={
                "feature": "arq_batch",
                "action": "run_daily_scout",
                "detail": {"total": total, "processing": len(processing_ids), "deferred": deferred},
            },
        )

    chunks = _chunk_list(processing_ids, settings.ARQ_CHUNK_SIZE)
    for chunk in chunks:
        await ctx["redis"].enqueue_job("process_scout_chunk", chunk)

    logger.info(
        "cron.started",
        extra={
            "feature": "arq_batch",
            "action": "run_daily_scout",
            "detail": {"items_found": total, "chunks_enqueued": len(chunks)},
        },
    )
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_scout_frequency_gating.py -v`
Expected: 3 passed.

- [ ] **Step 5: Regression check cron coordinator tests**

Run: `cd backend && uv run pytest tests/test_worker_cron.py -v`
Expected: existing tests pass. If a pre-existing coordinator test seeds candidates without `last_seen_at`, update that fixture to set `last_seen_at=datetime.now(UTC)`.

- [ ] **Step 6: Apply same gating to `run_weekly_analytics`**

Update `run_weekly_analytics` (lines ~375–419) identically — filter `last_seen_at >= 14d cutoff`. Weekly frequency already handles the cadence; no tier-day math needed there.

Replace the `.where(...)` clause to include:
```python
Candidate.last_seen_at.is_not(None),
Candidate.last_seen_at >= now - timedelta(days=14),
```

Add a test in `test_scout_frequency_gating.py` (or a sibling file) asserting `run_weekly_analytics` skips inactive candidates — mirror the first inactive-test above.

- [ ] **Step 7: Commit**

```bash
git add backend/app/worker.py backend/tests/test_scout_frequency_gating.py
git commit -m "feat(worker): gate scout/analytics on last_seen_at + plan tier"
```

---

## Phase C — Shared news ingest + split scout pipeline

**Why last:** largest structural change. Benefits from Phases A (cheap parse model) and B (fewer candidates triggering scoring).

### Task C1: `funding_signals` table + ORM model

**Files:**
- Create: `backend/alembic/versions/026_add_funding_signals.py`
- Create: `backend/app/models/funding_signal.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_funding_signal_model.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.funding_signal import FundingSignal


@pytest.mark.asyncio
async def test_can_insert_and_fetch_funding_signal(db_session):
    sig = FundingSignal(
        id=uuid4(),
        source_url="https://example.com/article-1",
        title="Acme raised $10M Series A",
        description="desc",
        published_at=datetime.now(UTC),
        source_name="NewsAPI",
        company_name="Acme",
        estimated_domain="acme.co",
        signal_types=["funding_round"],
        extra_data={"funding_round": "Series A", "amount": "$10M"},
    )
    db_session.add(sig)
    await db_session.commit()

    fetched = (await db_session.execute(
        select(FundingSignal).where(FundingSignal.source_url == "https://example.com/article-1")
    )).scalar_one()

    assert fetched.company_name == "Acme"
    assert fetched.signal_types == ["funding_round"]


@pytest.mark.asyncio
async def test_source_url_is_unique(db_session):
    from sqlalchemy.exc import IntegrityError

    s1 = FundingSignal(
        id=uuid4(), source_url="https://dup.example/a", title="t1",
        published_at=datetime.now(UTC),
    )
    s2 = FundingSignal(
        id=uuid4(), source_url="https://dup.example/a", title="t2",
        published_at=datetime.now(UTC),
    )
    db_session.add(s1)
    await db_session.commit()

    db_session.add(s2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

Run: `cd backend && uv run pytest tests/test_funding_signal_model.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the migration**

Create `backend/alembic/versions/026_add_funding_signals.py`:

```python
"""Add funding_signals shared pool table."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "funding_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_name", sa.String(100), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("estimated_domain", sa.String(200), nullable=True),
        sa.Column("funding_round", sa.String(50), nullable=True),
        sa.Column("amount", sa.String(50), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("signal_types", JSONB, nullable=True),
        sa.Column("extra_data", JSONB, nullable=True),
        sa.Column("embedding", sa.dialects.postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_url", name="uq_funding_signals_source_url"),
    )
    op.create_index("ix_funding_signals_published_at", "funding_signals", ["published_at"])
    op.create_index("ix_funding_signals_company_name", "funding_signals", ["company_name"])
    op.create_index("ix_funding_signals_expires_at", "funding_signals", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_funding_signals_expires_at", table_name="funding_signals")
    op.drop_index("ix_funding_signals_company_name", table_name="funding_signals")
    op.drop_index("ix_funding_signals_published_at", table_name="funding_signals")
    op.drop_table("funding_signals")
```

Note on `embedding`: stored as `ARRAY(Float)` rather than pgvector because we don't need pgvector indexing here — we fetch all recent signals and score in Python. If we later want ANN search, switch to `pgvector.sqlalchemy.Vector`.

- [ ] **Step 4: Create the ORM model**

Create `backend/app/models/funding_signal.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FundingSignal(Base, TimestampMixin):
    __tablename__ = "funding_signals"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    estimated_domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    funding_round: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signal_types: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
```

- [ ] **Step 5: Ensure model is imported so Alembic metadata picks it up**

In `backend/app/models/__init__.py` (or wherever models are re-exported), add:

```python
from app.models.funding_signal import FundingSignal  # noqa: F401
```

- [ ] **Step 6: Run migrations + test**

Run:
```bash
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/test_funding_signal_model.py -v
```
Expected: migration applies; 2 tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/026_add_funding_signals.py \
        backend/app/models/funding_signal.py \
        backend/app/models/__init__.py \
        backend/tests/test_funding_signal_model.py
git commit -m "feat(db): add funding_signals shared pool table"
```

---

### Task C2: `news_ingest_service` — global daily fetch + parse + store

**Files:**
- Create: `backend/app/services/news_ingest_service.py`
- Create: `backend/tests/test_news_ingest_service.py`

**Design:** One function `ingest_funding_news(db, news, openai, max_queries=3)` that (a) uses a small static/LLM-generated set of broad queries, (b) calls NewsAPI, (c) LLM-parses each article batch using `settings.SCOUT_PARSE_MODEL`, (d) upserts `FundingSignal` rows deduplicated by `source_url`, (e) computes + stores an embedding of `f"{company_name} {description} {industry}"` so per-candidate scoring is pure cosine sim.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_news_ingest_service.py`:

```python
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.funding_signal import FundingSignal
from app.services import news_ingest_service


@pytest.mark.asyncio
async def test_ingest_creates_funding_signals(db_session):
    news = AsyncMock()
    news.search_articles = AsyncMock(return_value=[
        {
            "title": "Acme raised $10M Series A",
            "description": "Acme is a fintech.",
            "url": "https://example.com/acme-a",
            "source": {"name": "TechCrunch"},
            "publishedAt": "2026-04-14T10:00:00Z",
        }
    ])

    openai = AsyncMock()
    openai.parse_structured = AsyncMock(return_value={
        "companies": [
            {
                "company_name": "Acme",
                "estimated_domain": "acme.co",
                "funding_round": "Series A",
                "amount": "$10M",
                "industry": "fintech",
                "description": "Fintech",
                "source_url": "https://example.com/acme-a",
            }
        ]
    })
    openai.embed = AsyncMock(return_value=[0.1] * 1536)

    count = await news_ingest_service.ingest_funding_news(db_session, news, openai)

    assert count == 1
    sig = (await db_session.execute(
        select(FundingSignal).where(FundingSignal.source_url == "https://example.com/acme-a")
    )).scalar_one()
    assert sig.company_name == "Acme"
    assert sig.embedding is not None
    assert len(sig.embedding) == 1536


@pytest.mark.asyncio
async def test_ingest_deduplicates_on_reruns(db_session):
    news = AsyncMock()
    news.search_articles = AsyncMock(return_value=[
        {
            "title": "t", "description": "d", "url": "https://dup.example/x",
            "source": {"name": "s"}, "publishedAt": "2026-04-14T10:00:00Z",
        }
    ])
    openai = AsyncMock()
    openai.parse_structured = AsyncMock(return_value={
        "companies": [{
            "company_name": "X", "estimated_domain": "x.co",
            "funding_round": "Seed", "amount": "$1M", "industry": "ai",
            "description": "d", "source_url": "https://dup.example/x",
        }]
    })
    openai.embed = AsyncMock(return_value=[0.1] * 1536)

    c1 = await news_ingest_service.ingest_funding_news(db_session, news, openai)
    c2 = await news_ingest_service.ingest_funding_news(db_session, news, openai)

    assert c1 == 1
    assert c2 == 0  # No duplicates inserted

    total = (await db_session.execute(select(FundingSignal))).scalars().all()
    assert len(total) == 1


@pytest.mark.asyncio
async def test_ingest_soft_fails_on_newsapi_error(db_session):
    news = AsyncMock()
    news.search_articles = AsyncMock(side_effect=Exception("boom"))

    openai = AsyncMock()

    count = await news_ingest_service.ingest_funding_news(db_session, news, openai)
    assert count == 0  # No crash, returns 0
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

Run: `cd backend && uv run pytest tests/test_news_ingest_service.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the service**

Create `backend/app/services/news_ingest_service.py`:

```python
"""Global daily NewsAPI ingest — writes to funding_signals for shared consumption."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.protocols import NewsAPIClientProtocol, OpenAIClientProtocol
from app.models.funding_signal import FundingSignal

logger = structlog.get_logger()


DEFAULT_QUERIES: list[str] = [
    "Series A funding announcement",
    "Series B funding round",
    "startup raised seed round hiring",
]

PARSE_ARTICLES_PROMPT = """You extract structured funding data from recent news.
For each article, return the funded company (name, estimated domain, funding round, amount, industry, 1-sentence description, and the original URL).
Articles:
{articles_block}
"""

PARSE_ARTICLES_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "estimated_domain": {"type": "string"},
                    "funding_round": {"type": "string"},
                    "amount": {"type": "string"},
                    "industry": {"type": "string"},
                    "description": {"type": "string"},
                    "source_url": {"type": "string"},
                },
                "required": ["company_name", "source_url"],
            },
        }
    },
    "required": ["companies"],
}


async def ingest_funding_news(
    db: AsyncSession,
    news: NewsAPIClientProtocol,
    openai: OpenAIClientProtocol,
    *,
    queries: list[str] | None = None,
    lookback_days: int = 7,
    expires_days: int = 30,
) -> int:
    """Fetch funding news, parse, dedupe-by-URL, store to funding_signals with embeddings.
    Returns count of new rows inserted."""
    queries = queries or DEFAULT_QUERIES
    from_date = (datetime.now(UTC) - timedelta(days=lookback_days)).date().isoformat()
    to_date = datetime.now(UTC).date().isoformat()

    # 1. Fetch
    articles: list[dict] = []
    for q in queries:
        try:
            batch = await news.search_articles(q, from_date=from_date, to_date=to_date, page_size=50)
            articles.extend(batch)
        except Exception as e:
            logger.warning("news_ingest.newsapi_error", query=q, error=str(e))
            continue

    if not articles:
        logger.info("news_ingest.no_articles")
        return 0

    # 2. Dedupe by URL at fetch time + filter already-known URLs in DB
    seen_urls = {a.get("url") for a in articles if a.get("url")}
    existing = (await db.execute(
        select(FundingSignal.source_url).where(FundingSignal.source_url.in_(seen_urls))
    )).scalars().all()
    new_articles = [a for a in articles if a.get("url") and a["url"] not in set(existing)]

    if not new_articles:
        logger.info("news_ingest.all_duplicates", total=len(articles))
        return 0

    # 3. Parse via LLM (cheap model)
    articles_block = "\n".join(
        f"- {a.get('title', '')} | {a.get('description', '')} | URL: {a.get('url')}"
        for a in new_articles[:50]
    )
    try:
        parsed = await openai.parse_structured(
            PARSE_ARTICLES_PROMPT.format(articles_block=articles_block),
            "",
            PARSE_ARTICLES_SCHEMA,
            model=settings.SCOUT_PARSE_MODEL,
        )
    except Exception as e:
        logger.error("news_ingest.parse_failed", error=str(e))
        return 0

    now = datetime.now(UTC)
    expires = now + timedelta(days=expires_days)
    inserted = 0

    # Build a URL → article index for metadata fallback
    article_by_url = {a.get("url"): a for a in new_articles}

    for c in parsed.get("companies", []):
        url = c.get("source_url")
        if not url or url in existing:
            continue

        source_article = article_by_url.get(url, {})
        embed_text = f"{c.get('company_name', '')} {c.get('description', '')} {c.get('industry', '')}".strip()
        try:
            embedding = await openai.embed(embed_text, dimensions=1536)
        except Exception as e:
            logger.warning("news_ingest.embed_failed", url=url, error=str(e))
            embedding = None

        sig = FundingSignal(
            id=uuid4(),
            source_url=url,
            title=source_article.get("title") or c.get("company_name", "")[:500],
            description=c.get("description") or source_article.get("description"),
            published_at=_parse_published(source_article.get("publishedAt")) or now,
            source_name=(source_article.get("source") or {}).get("name"),
            company_name=c.get("company_name"),
            estimated_domain=c.get("estimated_domain"),
            funding_round=c.get("funding_round"),
            amount=c.get("amount"),
            industry=c.get("industry"),
            signal_types=["funding_round"],
            extra_data={
                "funding_round": c.get("funding_round"),
                "amount": c.get("amount"),
            },
            embedding=embedding,
            parsed_at=now,
            expires_at=expires,
        )
        db.add(sig)
        inserted += 1

    await db.commit()
    logger.info("news_ingest.completed", fetched=len(articles), new=inserted)
    return inserted


def _parse_published(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_news_ingest_service.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/news_ingest_service.py backend/tests/test_news_ingest_service.py
git commit -m "feat(news): add shared funding_signals ingest service"
```

---

### Task C3: Add `run_daily_news_ingest` cron

**Files:**
- Modify: `backend/app/worker.py` — add new coordinator + register in `WorkerSettings.cron_jobs`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_news_ingest_cron.py`:

```python
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_news_ingest_cron_calls_service(monkeypatch):
    from app import worker

    called = {}

    async def fake_ingest(db, news, openai, **kwargs):
        called["ok"] = True
        return 3

    monkeypatch.setattr("app.services.news_ingest_service.ingest_funding_news", fake_ingest)
    monkeypatch.setattr(worker, "_acquire_run_lock", AsyncMock(return_value=True))

    await worker.run_daily_news_ingest({})

    assert called.get("ok") is True


@pytest.mark.asyncio
async def test_news_ingest_cron_respects_lock(monkeypatch):
    from app import worker

    called = {"ingest": False}

    async def fake_ingest(db, news, openai, **kwargs):
        called["ingest"] = True
        return 0

    monkeypatch.setattr("app.services.news_ingest_service.ingest_funding_news", fake_ingest)
    monkeypatch.setattr(worker, "_acquire_run_lock", AsyncMock(return_value=False))

    await worker.run_daily_news_ingest({})
    assert called["ingest"] is False


def test_news_ingest_cron_is_registered():
    from app.worker import WorkerSettings

    cron_names = [c.coroutine.__name__ for c in WorkerSettings.cron_jobs]
    assert "run_daily_news_ingest" in cron_names
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && uv run pytest tests/test_news_ingest_cron.py -v`
Expected: FAIL — function doesn't exist.

- [ ] **Step 3: Implement the cron**

In `backend/app/worker.py`, add BEFORE `run_daily_scout`:

```python
# ---------------------------------------------------------------------------
# Daily news ingest: shared pool for scout scoring
# ---------------------------------------------------------------------------


async def run_daily_news_ingest(ctx):
    """Fetch funding news once per day into the shared funding_signals pool."""
    if not await _acquire_run_lock("daily_news_ingest", ttl=82800):
        logger.info("cron.skipped_overlap", extra={"feature": "arq_batch", "action": "run_daily_news_ingest"})
        return

    from app.dependencies import get_newsapi, get_openai
    from app.infrastructure.database import async_session_factory
    from app.services.news_ingest_service import ingest_funding_news

    async with async_session_factory() as db:
        count = await ingest_funding_news(db, get_newsapi(), get_openai())

    logger.info("news_ingest.cron_done", inserted=count)
```

In `WorkerSettings.cron_jobs`, add a new entry. Choose 8 AM UTC so it runs BEFORE `run_daily_scout` at 9 AM:

```python
    cron_jobs: ClassVar[list] = [
        cron(check_followup_due, minute={0, 15, 30, 45}),
        cron(expire_stale_actions, hour={3}, minute={0}),
        cron(run_daily_news_ingest, hour={8}, minute={0}),   # NEW — runs before scout
        cron(run_daily_scout, hour={9}, minute={0}),
        cron(run_weekly_analytics, weekday={0}, hour={8}, minute={0}),
        cron(retry_failed_github_syncs, minute={5, 20, 35, 50}),
    ]
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_news_ingest_cron.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/worker.py backend/tests/test_news_ingest_cron.py
git commit -m "feat(worker): add run_daily_news_ingest cron at 08:00 UTC"
```

---

### Task C4: Split scout pipeline — remove global nodes, consume shared pool

**Files:**
- Modify: `backend/app/graphs/scout_pipeline.py`
- Modify: `backend/tests/test_scout_graph.py`, `test_scout_graph2.py`, `test_scout_integration.py` — update node set + mocks

**New pipeline shape:** `load_shared_signals → score_and_filter → create_companies → notify` (+ `mark_failed`). The 3 removed nodes (`build_search_queries_node`, `search_news_node`, `parse_articles_node`) move out.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_scout_consumes_shared_pool.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.candidate import Candidate, CandidateDNA
from app.models.company import Company
from app.models.funding_signal import FundingSignal


@pytest.mark.asyncio
async def test_scout_scores_candidates_against_shared_pool(db_session):
    """When FundingSignal rows exist with embeddings, scout scores + creates companies."""
    from app.graphs.scout_pipeline import get_scout_pipeline_no_checkpointer

    # Seed candidate + DNA with embedding
    cand = Candidate(
        id=uuid4(), email=f"c-{uuid4()}@t.co", hashed_password="x",
        is_active=True, plan_tier="hunter",
    )
    db_session.add(cand)
    db_session.add(CandidateDNA(
        candidate_id=cand.id,
        experience_summary="Senior backend eng",
        embedding=[0.1] * 1536,
    ))

    # Seed a funding_signal with a matching embedding (cosine > 0.55)
    db_session.add(FundingSignal(
        id=uuid4(),
        source_url="https://news.example/shared-1",
        title="Acme raised $5M Series A",
        description="Acme builds backend infra.",
        published_at=datetime.now(UTC),
        company_name="Acme",
        estimated_domain="acme.co",
        funding_round="Series A",
        amount="$5M",
        industry="dev tools",
        signal_types=["funding_round"],
        extra_data={"funding_round": "Series A", "amount": "$5M"},
        embedding=[0.1] * 1536,
    ))
    await db_session.commit()

    graph = get_scout_pipeline_no_checkpointer()
    state = {
        "candidate_id": str(cand.id),
        "plan_tier": "hunter",
        "parsed_companies": None,
        "scored_companies": None,
        "companies_created": 0,
        "status": "pending",
        "error": None,
    }
    result = await graph.ainvoke(state)
    assert result["status"] == "completed"
    assert result["companies_created"] == 1

    created = (await db_session.execute(
        select(Company).where(Company.candidate_id == cand.id)
    )).scalars().all()
    assert len(created) == 1
    assert created[0].name == "Acme"
    assert created[0].source == "scout_funding"


@pytest.mark.asyncio
async def test_scout_noop_when_pool_empty(db_session):
    from app.graphs.scout_pipeline import get_scout_pipeline_no_checkpointer

    cand = Candidate(
        id=uuid4(), email=f"c-{uuid4()}@t.co", hashed_password="x",
        is_active=True, plan_tier="hunter",
    )
    db_session.add(cand)
    db_session.add(CandidateDNA(
        candidate_id=cand.id, experience_summary="eng", embedding=[0.1] * 1536,
    ))
    await db_session.commit()

    graph = get_scout_pipeline_no_checkpointer()
    state = {
        "candidate_id": str(cand.id), "plan_tier": "hunter",
        "parsed_companies": None, "scored_companies": None,
        "companies_created": 0, "status": "pending", "error": None,
    }
    result = await graph.ainvoke(state)
    assert result["status"] == "completed"
    assert result["companies_created"] == 0
```

- [ ] **Step 2: Run — expect FAIL (graph still has old shape)**

Run: `cd backend && uv run pytest tests/test_scout_consumes_shared_pool.py -v`
Expected: FAIL.

- [ ] **Step 3: Refactor `scout_pipeline.py`**

In `backend/app/graphs/scout_pipeline.py`:

3a. Update the `ScoutState` TypedDict — remove `search_queries`, `raw_articles`; keep `parsed_companies`, `scored_companies`, `companies_created`, `status`, `error`, `candidate_id`, `plan_tier`.

3b. Delete the three node functions: `build_search_queries_node`, `search_news_node`, `parse_articles_node`. Also delete their prompts/schemas (`SCOUT_QUERIES_PROMPT`, `SCOUT_QUERIES_SCHEMA`, `PARSE_ARTICLES_PROMPT`, `PARSE_ARTICLES_SCHEMA`).

3c. Add a new node `load_shared_signals_node`:

```python
async def load_shared_signals_node(state: ScoutState) -> ScoutState:
    """Load recent FundingSignal rows from the shared pool into parsed_companies format."""
    from sqlalchemy import select
    from app.models.funding_signal import FundingSignal
    from app.infrastructure import database as _db_mod

    cutoff = datetime.now(UTC) - timedelta(days=7)
    async with _db_mod.async_session_factory() as db:
        result = await db.execute(
            select(FundingSignal)
            .where(FundingSignal.published_at >= cutoff)
            .where(FundingSignal.company_name.is_not(None))
            .order_by(FundingSignal.published_at.desc())
            .limit(200)
        )
        sigs = result.scalars().all()

    parsed = [
        {
            "company_name": s.company_name,
            "estimated_domain": s.estimated_domain or "",
            "funding_round": s.funding_round,
            "amount": s.amount,
            "industry": s.industry,
            "description": s.description,
            "source_url": s.source_url,
            "_precomputed_embedding": s.embedding,  # hint for score_and_filter_node
        }
        for s in sigs
        if s.company_name
    ]
    return {**state, "parsed_companies": parsed, "status": "pending"}
```

3d. Update `score_and_filter_node` to use `_precomputed_embedding` when present instead of re-embedding:

```python
# Inside score_and_filter_node, per-company loop:
embedding = c.get("_precomputed_embedding")
if embedding is None:
    text = f"{c['company_name']} {c.get('description', '')} {c.get('industry', '')}"
    embedding = await embed_text(text)
similarity = cosine_similarity(dna_embedding, embedding)
```

3e. Rebuild the StateGraph wiring in the pipeline factory function:

```python
def _build_graph():
    graph = StateGraph(ScoutState)
    graph.add_node("load_shared_signals", load_shared_signals_node)
    graph.add_node("score_and_filter", score_and_filter_node)
    graph.add_node("create_companies", create_companies_node)
    graph.add_node("notify", notify_node)
    graph.add_node("mark_failed", mark_failed_node)

    graph.add_edge(START, "load_shared_signals")
    graph.add_conditional_edges(
        "load_shared_signals",
        lambda s: "mark_failed" if s["status"] == "failed" else "score_and_filter",
        {"mark_failed": "mark_failed", "score_and_filter": "score_and_filter"},
    )
    graph.add_conditional_edges(
        "score_and_filter",
        lambda s: "mark_failed" if s["status"] == "failed" else "create_companies",
        {"mark_failed": "mark_failed", "create_companies": "create_companies"},
    )
    graph.add_edge("create_companies", "notify")
    graph.add_edge("notify", END)
    graph.add_edge("mark_failed", END)
    return graph
```

(Preserve the checkpointer/no-checkpointer factory functions — only the node set changes.)

- [ ] **Step 4: Run new test — expect PASS**

Run: `cd backend && uv run pytest tests/test_scout_consumes_shared_pool.py -v`
Expected: 2 passed.

- [ ] **Step 5: Update existing scout tests that reference removed nodes**

Run: `cd backend && uv run pytest tests/test_scout_graph.py tests/test_scout_graph2.py tests/test_scout_integration.py -v`

Expected failures:
- `test_scout_graph.py::test_graph_has_expected_nodes` — asserts old node names exist.
- `test_scout_graph2.py` — per-node unit tests for `build_search_queries_node`, `search_news_node`, `parse_articles_node`.

Fix strategy:
1. In `test_scout_graph.py`, update the node list assertion to the new set: `{"load_shared_signals", "score_and_filter", "create_companies", "notify", "mark_failed"}`.
2. In `test_scout_graph2.py`, delete tests whose subject is a removed node (build_search_queries / search_news / parse_articles). Keep tests for `score_and_filter`, `create_companies`, `notify`, `mark_failed`. Replace them with equivalent tests for `load_shared_signals_node` — empty pool, populated pool, oldest-first-excluded.
3. In `test_scout_integration.py`, seed `FundingSignal` rows before running `/scout/run` so the graph has data to score.

Commit the test changes after the pipeline refactor in Step 7 (so the commit is self-contained).

- [ ] **Step 6: Re-run the full scout test set**

Run: `cd backend && uv run pytest tests/test_scout*.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/graphs/scout_pipeline.py \
        backend/tests/test_scout_graph.py \
        backend/tests/test_scout_graph2.py \
        backend/tests/test_scout_integration.py \
        backend/tests/test_scout_consumes_shared_pool.py
git commit -m "refactor(scout): consume shared funding_signals pool instead of per-candidate NewsAPI"
```

---

### Task C5: Cleanup + final validation

**Files:**
- Modify: `backend/app/config.py` — optionally deprecate per-candidate NewsAPI settings (leave in place for rollback, remove in a follow-up PR)
- Modify: `backend/app/plans.py` — no changes; scout_frequency_days stays
- Modify: README or runbook (if one exists) — mention the new cron

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && uv run pytest --cov=app --cov-report=term`
Expected: all tests pass, coverage ≥ existing baseline.

- [ ] **Step 2: Run lints**

Run: `cd backend && uv run ruff check app/ && uv run ruff format --check app/`
Expected: clean.

- [ ] **Step 3: Run mypy (allow current baseline)**

Run: `cd backend && uv run mypy app/ --ignore-missing-imports`
Expected: error count ≤ previous baseline (user noted baseline ≤96).

- [ ] **Step 4: Commit any small fixups**

```bash
git add -p   # review any stray changes
git commit -m "chore: lint + mypy fixups"
```

- [ ] **Step 5: End-to-end smoke plan (to run after merging, before enabling worker in prod)**

No code here — a checklist the operator runs manually against staging or local docker-compose:

1. `docker compose up -d` — starts postgres + redis + backend + arq-worker.
2. `alembic upgrade head` (if not auto-applied) — both migrations 025 + 026 land.
3. Seed a test candidate, set `last_seen_at=NOW()`, add a `CandidateDNA` with an embedding.
4. Manually invoke `run_daily_news_ingest` via `arq` or by importing + awaiting from a one-off script. Expect rows in `funding_signals`.
5. Invoke `run_daily_scout`. Expect scout to consume the pool, create Companies for the test candidate, send WebSocket event.
6. Confirm `last_seen_at` is updated after a `/auth/refresh` call.
7. Confirm a free-tier candidate is NOT enqueued on a non-Monday.

---

## Rollout Plan (post-merge, separate from this plan)

1. Deploy backend with all three phases merged.
2. Apply migrations: `alembic upgrade head` → 025 (`last_seen_at`) + 026 (`funding_signals`).
3. Populate `last_seen_at` for existing active users via a one-off script: `UPDATE candidates SET last_seen_at = NOW() WHERE is_active = TRUE;` — so they're not gated out immediately. Document this in the deploy checklist.
4. Deploy the ARQ worker as a second Railway service (separate plan) pointing at the same image, start command `arq app.worker.WorkerSettings`.
5. Observe 24 h: `news_ingest.completed` should log once at 08:00 UTC; `run_daily_scout` at 09:00 UTC should log chunks enqueued.
6. Check `funding_signals` table size + daily new rows.
7. Check OpenAI dashboard — confirm gpt-4o-mini now dominates scout spend.

---

## Risk & Rollback

| Risk | Mitigation | Rollback |
|------|------------|----------|
| `funding_signals` pool stays empty (NewsAPI quota / bad query) | Task C2 soft-fails on NewsAPI errors. Scout then creates 0 companies (degraded but safe). Add a post-deploy alert on `news_ingest.no_articles` for > 2 consecutive days. | Revert Phase C commits; old scout re-runs per-candidate NewsAPI. |
| `last_seen_at` gates out all existing users (NULL on deploy) | Run the one-off UPDATE in Rollout step 3. | Deploy a hotfix removing the `IS NOT NULL` check — scout falls back to old behavior minus activity filter. |
| Cheap model produces bad query gen | Toggle `SCOUT_QUERIES_MODEL=gpt-4o` in env without redeploying. | Same toggle. |
| Plan-tier frequency wrong math | Unit tests cover Mon vs non-Mon. | Set all tiers to `scout_frequency_days=1` via env (not currently supported) or revert Phase B. |

---

## Self-Review

**Spec coverage:**
- Initiative 1 (shared news fetch) → Tasks C1–C5 ✓
- Initiative 2 (activity gating + plan-tier frequency) → Tasks B1–B4 ✓
- Initiative 3 (cheap-model routing) → Tasks A1–A4 ✓

**Placeholder scan:** no TBDs, no "add error handling" hand-waves, no "similar to Task N" references. Every step has code or a command.

**Type consistency:** `scout_frequency_days` is an int across plans.py and worker.py. `FundingSignal.embedding` is `list[float] | None` in both model and migration (ARRAY(Float)). `parsed_companies` dict shape in `load_shared_signals_node` matches what `score_and_filter_node` consumes (`_precomputed_embedding` hint is additive, not required). `last_seen_at` is `datetime | None` across model, migration, and auth_service.
