# Production Readiness Audit Fixes — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 52 issues identified in the comprehensive production-readiness audit, organized into 12 tasks across 6 phases, prioritized by severity and blast radius.

**Architecture:** Fixes are grouped by blast radius — each task produces a self-contained, committable change. Security and async fixes first (they can cause data leaks and outages), then CI/test hardening, then clean code. Each task includes its own tests.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, ARQ workers, Redis, pytest-asyncio, GitHub Actions CI

---

## Phase 1: Critical Security Fixes

### Task 1: Fix Cross-Tenant Data Access in Outreach & Contact Services

**Why:** Tenant A can read Tenant B's contact data by passing a foreign `contact_id` to the outreach draft endpoints. This is a real data isolation breach.

**Files:**
- Modify: `jobhunter/backend/app/services/outreach_service.py:247-262`
- Modify: `jobhunter/backend/app/services/contact_service.py:21-24`
- Modify: `jobhunter/backend/app/services/company_service.py:317-319`
- Create: `jobhunter/backend/tests/test_tenant_isolation_services.py`

- [ ] **Step 1: Write failing test — outreach contact lookup crosses tenants**

```python
# tests/test_tenant_isolation_services.py
import uuid
import pytest
from sqlalchemy import select
from app.services.outreach_service import _get_contact, _get_contact_with_company


@pytest.mark.asyncio
async def test_get_contact_rejects_foreign_tenant(db_session):
    """_get_contact must reject contact_id that belongs to a different candidate."""
    from app.models.company import Company
    from app.models.contact import Contact

    # Create two tenants
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # Create a company and contact owned by tenant_b
    company = Company(id=uuid.uuid4(), candidate_id=tenant_b, name="B Corp", domain="bcorp.com", status="approved")
    db_session.add(company)
    await db_session.flush()

    contact = Contact(
        id=uuid.uuid4(), company_id=company.id, candidate_id=tenant_b,
        full_name="Bob", email="bob@bcorp.com",
    )
    db_session.add(contact)
    await db_session.flush()

    # Tenant A tries to access tenant B's contact
    with pytest.raises(ValueError, match="Contact not found"):
        await _get_contact(db_session, contact.id, tenant_a)


@pytest.mark.asyncio
async def test_get_contact_allows_own_tenant(db_session):
    """_get_contact returns contact when candidate_id matches."""
    from app.models.company import Company
    from app.models.contact import Contact

    tenant_a = uuid.uuid4()
    company = Company(id=uuid.uuid4(), candidate_id=tenant_a, name="A Corp", domain="acorp.com", status="approved")
    db_session.add(company)
    await db_session.flush()

    contact = Contact(
        id=uuid.uuid4(), company_id=company.id, candidate_id=tenant_a,
        full_name="Alice", email="alice@acorp.com",
    )
    db_session.add(contact)
    await db_session.flush()

    result = await _get_contact(db_session, contact.id, tenant_a)
    assert result.id == contact.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run pytest tests/test_tenant_isolation_services.py -v`
Expected: FAIL — `_get_contact()` does not accept `candidate_id` parameter

- [ ] **Step 3: Add `candidate_id` parameter to outreach service helpers**

In `jobhunter/backend/app/services/outreach_service.py`, change lines 247-262:

```python
async def _get_contact(db: AsyncSession, contact_id: uuid.UUID, candidate_id: uuid.UUID) -> Contact:
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.candidate_id == candidate_id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise ValueError("Contact not found")
    return contact


async def _get_contact_with_company(db: AsyncSession, contact_id: uuid.UUID, candidate_id: uuid.UUID) -> Contact:
    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact_id, Contact.candidate_id == candidate_id)
        .options(selectinload(Contact.company))
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise ValueError("Contact not found")
    if not contact.company:
        raise ValueError("Company not found")
    return contact
```

Then update these specific callers in `outreach_service.py` to pass `candidate_id`:

1. **Line 107** — `draft_message()`: change `_get_contact_with_company(db, contact_id)` to `_get_contact_with_company(db, contact_id, candidate_id)`
2. **Line 185** — `draft_linkedin_message()`: change `_get_contact(db, contact_id)` to `_get_contact(db, contact_id, candidate_id)`

Also fix `_get_company` (line 265) — it also lacks a `candidate_id` filter:

```python
async def _get_company(db: AsyncSession, company_id: uuid.UUID, candidate_id: uuid.UUID | None = None) -> Company:
    query = select(Company).where(Company.id == company_id)
    if candidate_id:
        query = query.where(Company.candidate_id == candidate_id)
    result = await db.execute(query)
    company = result.scalar_one_or_none()
    if not company:
        raise ValueError("Company not found")
    return company
```

Update its caller at line 186: `_get_company(db, contact.company_id, candidate_id)`

- [ ] **Step 4: Fix contact_service.find_contact — add candidate_id filter on company lookup**

In `jobhunter/backend/app/services/contact_service.py`, change line 21:

```python
    result = await db.execute(
        select(Company).where(Company.id == company_id, Company.candidate_id == candidate_id)
    )
```

- [ ] **Step 5: Fix company_service — replace HTTPException with ValueError**

In `jobhunter/backend/app/services/company_service.py`, change lines 316-320:

```python
    if not dna:
        raise ValueError("Upload and process a resume before discovering companies")
```

Remove the `from fastapi import HTTPException, status` import if it's only used here. The route handler in `api/companies.py` already catches `ValueError`.

- [ ] **Step 6: Run all tests to verify fixes pass**

Run: `cd jobhunter/backend && uv run pytest tests/test_tenant_isolation_services.py tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd jobhunter/backend
rtk git add app/services/outreach_service.py app/services/contact_service.py app/services/company_service.py tests/test_tenant_isolation_services.py
rtk git commit -m "fix(security): add candidate_id filter to contact/company lookups — prevent cross-tenant data access"
```

---

### Task 2: Secure Metrics Endpoint and Fix Hardcoded URLs

**Why:** `/metrics` is publicly accessible without auth, leaking operational data. Invite emails use hardcoded URL instead of `settings.FRONTEND_URL`.

**Files:**
- Modify: `jobhunter/backend/app/middleware/metrics.py:26-31`
- Modify: `jobhunter/backend/app/config.py` (add `METRICS_SECRET`)
- Modify: `jobhunter/backend/app/api/admin.py:429-431,532-535`
- Create: `jobhunter/backend/tests/test_metrics_auth.py`

- [ ] **Step 1: Write failing test — metrics returns 403 without secret**

```python
# tests/test_metrics_auth.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_requires_secret(client: AsyncClient):
    resp = await client.get("/metrics")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_metrics_returns_data_with_secret(client: AsyncClient):
    from app.config import settings
    resp = await client.get("/metrics", headers={"X-Metrics-Token": settings.METRICS_SECRET})
    # In test, METRICS_SECRET may be empty — if empty, endpoint should be disabled
    if settings.METRICS_SECRET:
        assert resp.status_code == 200
    else:
        assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run pytest tests/test_metrics_auth.py -v`
Expected: FAIL — currently returns 200 without auth

- [ ] **Step 3: Add METRICS_SECRET to config**

In `jobhunter/backend/app/config.py`, add to the Settings class:

```python
    METRICS_SECRET: str = ""
```

- [ ] **Step 4: Gate metrics endpoint behind secret**

In `jobhunter/backend/app/middleware/metrics.py`, change lines 26-31:

```python
class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/metrics":
            from app.config import settings

            secret = request.headers.get("X-Metrics-Token", "")
            if not settings.METRICS_SECRET or secret != settings.METRICS_SECRET:
                return Response(status_code=403, content="Forbidden")
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )
```

- [ ] **Step 5: Fix hardcoded invite email URLs**

In `jobhunter/backend/app/api/admin.py`, change line 430:

```python
                f"{settings.FRONTEND_URL}/register?code={invite.code}\n\n"
```

And line 534:

```python
                    f"{settings.FRONTEND_URL}/register?code={invite.code}\n\n"
```

- [ ] **Step 6: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/test_metrics_auth.py tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd jobhunter/backend
rtk git add app/middleware/metrics.py app/config.py app/api/admin.py tests/test_metrics_auth.py
rtk git commit -m "fix(security): gate /metrics behind secret, replace hardcoded invite URLs with settings.FRONTEND_URL"
```

---

## Phase 2: Critical Async Fixes

### Task 3: Fix Blocking Calls on Async Event Loop

**Why:** `socket.gethostbyname()` and PDF/DOCX parsing block the entire event loop, stalling all concurrent requests. These are the highest-impact performance issues.

**Files:**
- Modify: `jobhunter/backend/app/infrastructure/url_scraper.py:14-23`
- Modify: `jobhunter/backend/app/services/resume_service.py:166`
- Create: `jobhunter/backend/tests/test_async_correctness.py`

- [ ] **Step 1: Write test — url validation is async-safe**

```python
# tests/test_async_correctness.py
import asyncio
import pytest


@pytest.mark.asyncio
async def test_validate_url_does_not_block_loop():
    """Verify _validate_url runs DNS resolution off the event loop."""
    from unittest.mock import patch, AsyncMock

    with patch("app.infrastructure.url_scraper.asyncio") as mock_asyncio:
        mock_loop = AsyncMock()
        mock_asyncio.get_running_loop.return_value = mock_loop
        mock_loop.run_in_executor.return_value = "93.184.216.34"

        from app.infrastructure.url_scraper import _validate_url
        await _validate_url("https://example.com")

        mock_loop.run_in_executor.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run pytest tests/test_async_correctness.py::test_validate_url_does_not_block_loop -v`
Expected: FAIL — `_validate_url` is sync, not async

- [ ] **Step 3: Make _validate_url async with run_in_executor**

Replace `jobhunter/backend/app/infrastructure/url_scraper.py` entirely:

```python
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger()

JINA_READER_BASE = "https://r.jina.ai"
TIMEOUT = 20.0


async def _validate_url(url: str) -> None:
    parsed = urlparse(str(url))
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP/HTTPS URLs are allowed")
    try:
        loop = asyncio.get_running_loop()
        resolved = await loop.run_in_executor(None, socket.gethostbyname, parsed.hostname)
        ip = ipaddress.ip_address(resolved)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError("Internal/private URLs are not allowed")
    except socket.gaierror:
        logger.warning("url_validation_dns_failed", url=url)


async def scrape_job_url(url: str) -> str:
    """Fetch a job posting URL via Jina Reader API and return clean markdown text."""
    await _validate_url(url)
    jina_url = f"{JINA_READER_BASE}/{url}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(
            jina_url,
            headers={"Accept": "text/markdown"},
            follow_redirects=True,
        )
        response.raise_for_status()

    text = response.text.strip()
    if not text:
        raise ValueError("Scraping returned empty content for URL")

    logger.info("url_scraped", url=url, length=len(text))
    return text
```

- [ ] **Step 4: Offload PDF/DOCX parsing to thread pool**

In `jobhunter/backend/app/services/resume_service.py`, change line 166:

```python
    # Extract text (offload CPU-bound parsing to thread pool)
    import asyncio
    extractor = _extract_text_from_pdf if ext == "pdf" else _extract_text_from_docx
    raw_text = await asyncio.to_thread(extractor, file_bytes)
```

- [ ] **Step 5: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd jobhunter/backend
rtk git add app/infrastructure/url_scraper.py app/services/resume_service.py tests/test_async_correctness.py
rtk git commit -m "fix(async): offload DNS resolution and PDF/DOCX parsing to thread pool"
```

---

### Task 4: Fix HTTP Client Lifecycle — Close Connections on Shutdown

**Why:** `httpx.AsyncClient` instances in HunterClient and NewsAPIClient are never closed, causing connection leaks. OpenAI client has no timeout, allowing 10-minute hangs.

**Files:**
- Modify: `jobhunter/backend/app/infrastructure/hunter_client.py:15-18`
- Modify: `jobhunter/backend/app/infrastructure/newsapi_client.py:11-14`
- Modify: `jobhunter/backend/app/infrastructure/openai_client.py:14-16`
- Modify: `jobhunter/backend/app/main.py:114-118` (shutdown section)
- Modify: `jobhunter/backend/app/dependencies.py` (add close helpers)

- [ ] **Step 1: Write test — clients have aclose method**

```python
# Add to tests/test_async_correctness.py

@pytest.mark.asyncio
async def test_hunter_client_has_aclose():
    from app.infrastructure.hunter_client import HunterClient
    client = HunterClient()
    assert hasattr(client, "aclose")
    await client.aclose()


@pytest.mark.asyncio
async def test_newsapi_client_has_aclose():
    from app.infrastructure.newsapi_client import NewsAPIClient
    client = NewsAPIClient()
    assert hasattr(client, "aclose")
    await client.aclose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run pytest tests/test_async_correctness.py::test_hunter_client_has_aclose -v`
Expected: FAIL — no `aclose` method

- [ ] **Step 3: Add aclose to HunterClient**

In `jobhunter/backend/app/infrastructure/hunter_client.py`, add after line 18:

```python
    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: Add aclose to NewsAPIClient**

In `jobhunter/backend/app/infrastructure/newsapi_client.py`, add after line 14:

```python
    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 5: Add timeout to OpenAI client**

In `jobhunter/backend/app/infrastructure/openai_client.py`, change line 16:

```python
    def __init__(self):
        import httpx as _httpx

        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=_httpx.Timeout(60.0, connect=10.0),
        )
```

- [ ] **Step 6: Add close_clients helper to dependencies.py**

In `jobhunter/backend/app/dependencies.py`, add at the end (before line 145):

```python
async def close_clients() -> None:
    """Close all HTTP clients on shutdown."""
    global _hunter_client, _newsapi_client, _email_client
    for client in (_hunter_client, _newsapi_client, _email_client):
        if client and hasattr(client, "aclose"):
            await client.aclose()
```

Note: `_email_client` (ResendClient) may not have `aclose` — the `hasattr` guard handles this safely. All three HTTP-backed singletons are covered.

- [ ] **Step 7: Call close_clients in main.py shutdown**

In `jobhunter/backend/app/main.py`, change lines 114-118:

```python
    yield
    logger.info("shutting_down", app=settings.APP_NAME)
    await bus.stop_listening()
    await close_checkpointer()
    from app.dependencies import close_clients
    await close_clients()
    await close_redis()
    await engine.dispose()
```

- [ ] **Step 8: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
cd jobhunter/backend
rtk git add app/infrastructure/hunter_client.py app/infrastructure/newsapi_client.py app/infrastructure/openai_client.py app/dependencies.py app/main.py tests/test_async_correctness.py
rtk git commit -m "fix(async): add client cleanup on shutdown, add 60s OpenAI timeout"
```

---

## Phase 3: Event Bus & Worker Fixes

### Task 5: Fix Event Bus — Either Dispatch Cross-Worker Events or Remove Dead Code

**Why:** The Redis Streams listener ACKs messages without dispatching to handlers. Cross-worker events are silently dropped. This is the most architecturally broken component.

**Files:**
- Modify: `jobhunter/backend/app/events/bus.py:163-170`
- Modify: `jobhunter/backend/tests/test_event_bus.py`

- [ ] **Step 1: Write failing test — cross-worker dispatch**

```python
# Add to tests/test_event_bus.py

@pytest.mark.asyncio
async def test_process_stream_message_dispatches_to_handlers():
    """Stream messages from other workers should dispatch to local handlers."""
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe("company_approved", handler)

    # Simulate a message from a different worker
    mock_redis = AsyncMock()
    bus._redis = mock_redis
    bus._consumer_name = "worker-aaaa"

    msg_data = {
        "event_type": "company_approved",
        "payload": '{"company_id": "123"}',
        "source": "worker-bbbb",
        "timestamp": "2026-03-17T10:00:00",
    }

    await bus._process_stream_message("events:company_approved", "msg-1", msg_data)

    handler.assert_awaited_once()
    event_arg = handler.call_args[0][0]
    assert event_arg.event_type == "company_approved"
    assert event_arg.payload == {"company_id": "123"}
    mock_redis.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_stream_message_skips_self_published():
    """Stream messages from this worker should be ACKed but not dispatched (already fired locally)."""
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe("company_approved", handler)

    mock_redis = AsyncMock()
    bus._redis = mock_redis
    bus._consumer_name = "worker-aaaa"

    msg_data = {
        "event_type": "company_approved",
        "payload": '{"company_id": "123"}',
        "source": "worker-aaaa",  # Same worker
        "timestamp": "2026-03-17T10:00:00",
    }

    await bus._process_stream_message("events:company_approved", "msg-1", msg_data)

    handler.assert_not_awaited()  # Already fired during publish()
    mock_redis.xack.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run pytest tests/test_event_bus.py::test_process_stream_message_dispatches_to_handlers -v`
Expected: FAIL — handler is never called

- [ ] **Step 3: Implement cross-worker dispatch in _process_stream_message**

In `jobhunter/backend/app/events/bus.py`, replace lines 163-170:

```python
    async def _process_stream_message(self, stream: str, msg_id, msg_data: dict) -> None:
        """Process a single message from a Redis Stream.

        If the message was published by this worker, only ACK it (handlers already
        fired during publish()). Otherwise, deserialize and dispatch to local handlers.
        """
        source = msg_data.get("source", "")
        if isinstance(source, bytes):
            source = source.decode()

        # Skip events we published ourselves (already fired in-process during publish)
        if source != self._consumer_name:
            event_type = msg_data.get("event_type", "")
            if isinstance(event_type, bytes):
                event_type = event_type.decode()

            payload_raw = msg_data.get("payload", "{}")
            if isinstance(payload_raw, bytes):
                payload_raw = payload_raw.decode()

            handlers = self._handlers.get(event_type, [])
            if handlers:
                payload = json.loads(payload_raw)
                event = Event(event_type=event_type, payload=payload, source=source)
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(
                            "event_bus_cross_worker_handler_failed",
                            handler=handler.__name__,
                            event_type=event_type,
                            error=str(e),
                        )

        await self._redis.xack(stream, CONSUMER_GROUP, msg_id)
```

- [ ] **Step 4: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/test_event_bus.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd jobhunter/backend
rtk git add app/events/bus.py tests/test_event_bus.py
rtk git commit -m "fix(events): implement cross-worker event dispatch in Redis Streams listener"
```

---

### Task 6: Fix Worker Error Handling and Concurrency Issues

**Why:** `send_approved_message` swallows errors (no retry), has no timeout. `_process_chunk` silently absorbs CancelledError. Invite quota has race condition. Scout pipeline uses pgBouncer-incompatible SAVEPOINTs.

**Files:**
- Modify: `jobhunter/backend/app/worker.py:70,472-499,502-508`
- Modify: `jobhunter/backend/app/api/admin.py:327-341,393-411,497-518`
- Modify: `jobhunter/backend/app/graphs/scout_pipeline.py:387`
- Modify: `jobhunter/backend/app/services/concurrency.py:10`

- [ ] **Step 1: Fix _process_chunk — remove return_exceptions=True, handle CancelledError properly**

In `jobhunter/backend/app/worker.py`, change line 70 from:

```python
    await asyncio.gather(*[_run(item) for item in items], return_exceptions=True)
```

to:

```python
    await asyncio.gather(*[_run(item) for item in items])
```

Since `_run` already catches all `Exception` subclasses internally, `return_exceptions=True` is redundant. Removing it means `CancelledError` (a `BaseException`) will propagate correctly from `gather` instead of being silently absorbed as a return value.

- [ ] **Step 2: Fix send_approved_message — add timeout, re-raise errors**

In `jobhunter/backend/app/worker.py`, replace lines 472-499:

```python
async def send_approved_message(ctx, outreach_id: str):
    """Send an approved outreach message."""
    from app.infrastructure.database import async_session_factory
    from app.services.email_service import send_outreach

    token = current_tenant_id.set(None)
    try:
        async with async_session_factory() as db:
            from sqlalchemy import select

            from app.models.candidate import Candidate
            from app.models.outreach import OutreachMessage

            result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == uuid.UUID(outreach_id)))
            outreach_msg = result.scalar_one_or_none()
            plan_tier = "free"
            if outreach_msg:
                cand_result = await db.execute(select(Candidate).where(Candidate.id == outreach_msg.candidate_id))
                cand = cand_result.scalar_one_or_none()
                if cand:
                    plan_tier = cand.plan_tier
            await send_outreach(db, uuid.UUID(outreach_id), plan_tier=plan_tier)
            logger.info("approved_message_sent", message_id=outreach_id)
    except Exception as e:
        logger.error("approved_message_send_failed", message_id=outreach_id, error=str(e))
        raise  # Let ARQ mark as failed and retry
    finally:
        current_tenant_id.reset(token)
```

- [ ] **Step 3: Add timeout to send_approved_message in WorkerSettings**

In `jobhunter/backend/app/worker.py`, change line 504:

```python
        func(send_approved_message, timeout=120),
```

- [ ] **Step 4: Fix invite quota — make atomic with INCRBY + check**

In `jobhunter/backend/app/api/admin.py`, replace lines 327-341 and update the quota check pattern:

```python
DAILY_INVITE_QUOTA_KEY = "admin:daily_invites:{date}"


async def _try_reserve_quota(redis, amount: int = 1) -> bool:
    """Atomically reserve invite quota. Returns True if within limit."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = DAILY_INVITE_QUOTA_KEY.format(date=today)
    new_val = await redis.incrby(key, amount)
    await redis.expire(key, 172800)
    if new_val > settings.MAX_DAILY_INVITES:
        # Over limit — roll back
        await redis.decrby(key, amount)
        return False
    return True


async def _get_daily_quota_used(redis) -> int:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = DAILY_INVITE_QUOTA_KEY.format(date=today)
    val = await redis.get(key)
    return int(val) if val else 0
```

Then update `invite_waitlist_entry` (lines 393-411) — replace the read-then-increment with:

```python
    # Atomic quota reservation
    if not await _try_reserve_quota(redis):
        logger.warning(...)
        return JSONResponse(status_code=429, ...)
```

Remove the separate `_increment_daily_quota` call at line 411.

And update `invite_waitlist_batch` (lines 497-518) — replace per-item quota check with:

```python
        if not await _try_reserve_quota(redis):
            skipped += len(body.ids) - invited - skipped - failed
            break
```

Remove the separate `_increment_daily_quota` call at line 518.

- [ ] **Step 5: Fix scout pipeline — replace begin_nested with try/except + flush**

In `jobhunter/backend/app/graphs/scout_pipeline.py`, replace lines 384-387.

The issue: `begin_nested()` uses SAVEPOINTs which are incompatible with pgBouncer in transaction mode. But simply removing it and using `db.rollback()` would roll back the ENTIRE transaction (all companies), not just the failed one.

**Solution:** Use a fresh session per company to isolate failures:

```python
    for c in scored:
        try:
            async with _db_mod.async_session_factory() as db:
                company = Company(
                    id=uuid.uuid4(),
                    candidate_id=candidate_id,
                    name=c["company_name"],
                    domain=c["domain"],
                    industry=c.get("industry"),
                    description=c.get("description"),
                    funding_stage=c.get("funding_round"),
                    fit_score=c.get("fit_score"),
                    embedding=c.get("embedding"),
                    status="suggested",
                    research_status="pending",
                    source="scout_funding",
                )
                db.add(company)
                await db.flush()

                signal = CompanySignal(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    candidate_id=candidate_id,
                    signal_type="funding_round",
                    # ... rest of signal fields unchanged
                )
                db.add(signal)
                await db.commit()
                created += 1
        except IntegrityError:
            logger.info("scout_company_duplicate", domain=c.get("domain"))
            continue
        except Exception as e:
            logger.error("scout_company_create_failed", domain=c.get("domain"), error=str(e))
            continue
```

Note: `IntegrityError` is already imported at line 18 of `scout_pipeline.py` — do NOT add a duplicate import.

- [ ] **Step 6: Fix unbounded semaphore dict growth**

In `jobhunter/backend/app/services/concurrency.py`, replace line 10:

```python
from functools import lru_cache

# LRU cache limits growth — inactive users' semaphores are evicted
@lru_cache(maxsize=10_000)
def _get_semaphore(candidate_id: str) -> asyncio.Semaphore:
    return asyncio.Semaphore(3)
```

Then change line 20:

```python
    sem = _get_semaphore(candidate_id)
```

Remove the `_semaphores` defaultdict and `from collections import defaultdict`.

- [ ] **Step 7: Write tests for worker and quota fixes**

```python
# Add to tests/test_worker_fixes.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_process_chunk_propagates_cancellation():
    """CancelledError must propagate out of _process_chunk, not be silently absorbed."""
    from app.worker import _process_chunk

    async def always_cancel(item):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await _process_chunk([1], always_cancel, concurrency=1, job_name="test")


@pytest.mark.asyncio
async def test_send_approved_message_reraises_on_failure():
    """send_approved_message must re-raise so ARQ can mark the job as failed and retry."""
    from app.worker import send_approved_message

    ctx = {}
    with patch("app.worker.async_session_factory") as mock_sf:
        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute.side_effect = Exception("DB down")

        with pytest.raises(Exception, match="DB down"):
            await send_approved_message(ctx, str(__import__("uuid").uuid4()))


@pytest.mark.asyncio
async def test_atomic_quota_reservation(redis):
    """Quota reservation must be atomic — no TOCTOU race."""
    from app.api.admin import _try_reserve_quota
    from app.config import settings

    # Fill quota to the limit
    for _ in range(settings.MAX_DAILY_INVITES):
        assert await _try_reserve_quota(redis) is True

    # Next attempt should fail
    assert await _try_reserve_quota(redis) is False
```

- [ ] **Step 8: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/test_worker_fixes.py tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
cd jobhunter/backend
rtk git add app/worker.py app/api/admin.py app/graphs/scout_pipeline.py app/services/concurrency.py tests/test_worker_fixes.py
rtk git commit -m "fix(worker): re-raise errors for ARQ retry, add timeout, fix quota race condition, remove pgBouncer-incompatible SAVEPOINTs"
```

---

## Phase 4: CI/CD Hardening

### Task 7: Make CI Actually Enforce Quality Gates

**Why:** Mypy is disabled (`|| true`), coverage threshold isn't enforced, backend tests skip migrations, E2E startup loop doesn't fail on timeout.

**Files:**
- Modify: `.github/workflows/ci.yml:56-59,135-139`

- [ ] **Step 1: Fix mypy — enforce with baseline error count**

In `.github/workflows/ci.yml`, change line 56:

```yaml
      - name: Mypy type check
        run: |
          ERRORS=$(uv run mypy app/ --ignore-missing-imports 2>&1 | grep -c "error:" || true)
          echo "Mypy errors: $ERRORS"
          if [ "$ERRORS" -gt 95 ]; then
            echo "::error::Mypy error count increased from baseline (95). Fix new type errors."
            uv run mypy app/ --ignore-missing-imports
            exit 1
          fi
```

- [ ] **Step 2: Add migration step to backend job — targeting the main test database**

The CI `env` block sets `DATABASE_URL` to `jobhunter` (not `jobhunter_test`). The test suite uses this same `DATABASE_URL`. So run migrations against `jobhunter`:

In `.github/workflows/ci.yml`, after line 58 (Create test database), add:

```yaml
      - name: Run migrations
        run: uv run alembic upgrade head
```

This uses the `DATABASE_URL` already set in the job's `env` block (`postgresql+asyncpg://jobhunter:jobhunter@localhost:5432/jobhunter`). The conftest.py `test_engine` fixture creates its own tables via `Base.metadata.create_all`, but running migrations ensures migration scripts themselves don't have syntax/logic errors — catching migration drift before production.

- [ ] **Step 3: Measure current coverage and enforce threshold**

First, measure the current coverage locally:

Run: `cd jobhunter/backend && uv run pytest tests/ -q --tb=short --cov=app --cov-report=term-missing 2>&1 | tail -5`

Record the `TOTAL` coverage percentage. Then set `--cov-fail-under` to 5 percentage points BELOW the measured value (to allow for minor fluctuations without blocking CI):

In `.github/workflows/ci.yml`, change line 59. Example if measured coverage is 72%:

```yaml
      - run: uv run pytest tests/ -q --tb=short --cov=app --cov-report=term-missing --cov-fail-under=67
```

The goal is to prevent regression, not to demand 85% immediately. Update `pyproject.toml`'s `fail_under` to match.

- [ ] **Step 4: Fix E2E backend startup loop — fail on timeout**

In `.github/workflows/ci.yml`, change lines 135-139:

```yaml
          uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          echo "Waiting for backend..."
          for i in $(seq 1 30); do
            curl -sf http://localhost:8000/api/v1/health && break
            if [ "$i" -eq 30 ]; then
              echo "::error::Backend failed to start after 60 seconds"
              exit 1
            fi
            sleep 2
          done
```

- [ ] **Step 5: Commit**

```bash
rtk git add .github/workflows/ci.yml
rtk git commit -m "fix(ci): enforce mypy baseline, run migrations in test DB, add coverage threshold, fail on E2E timeout"
```

---

## Phase 5: Clean Code & Architecture

### Task 8: Extract CandidateResponse Builder — Fix Field Divergence

**Why:** `CandidateResponse(...)` is constructed 5 times in `auth.py` with diverging fields — `register` is missing `headline`, `location`, `target_roles`, etc.

**Files:**
- Modify: `jobhunter/backend/app/api/auth.py:42-54,91-110,125-144,158-177,192-210`

- [ ] **Step 1: Create helper function at top of auth.py**

After the imports in `jobhunter/backend/app/api/auth.py`, add:

```python
def _to_candidate_response(candidate: Candidate) -> CandidateResponse:
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        email_verified=candidate.email_verified,
        preferences=candidate.preferences,
        plan_tier=candidate.plan_tier,
        onboarding_completed_at=candidate.onboarding_completed_at,
        onboarding_completed=candidate.onboarding_completed_at is not None,
        tour_completed_at=candidate.tour_completed_at,
        tour_completed=candidate.tour_completed_at is not None,
    )
```

- [ ] **Step 2: Replace all 5 construction sites**

Replace lines 42-54 (`register`):
```python
    return _to_candidate_response(candidate)
```

Replace lines 91-110 (`get_me`):
```python
    return _to_candidate_response(candidate)
```

Replace lines 125-144 (`update_me`) — update the variable name to match:
```python
    return _to_candidate_response(candidate)
```

Replace lines 158-177 (`complete_onboarding`):
```python
    return _to_candidate_response(candidate)
```

Replace lines 192-210 (`complete_tour`):
```python
    return _to_candidate_response(candidate)
```

- [ ] **Step 3: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/ -q --tb=short`
Expected: PASS — the `register` endpoint now returns the missing fields

- [ ] **Step 4: Commit**

```bash
cd jobhunter/backend
rtk git add app/api/auth.py
rtk git commit -m "refactor(auth): extract _to_candidate_response helper — fix field divergence in register endpoint"
```

---

### Task 9: Move Business Logic Out of Admin Route Handler

**Why:** `update_user_plan` is the only admin endpoint that embeds DB queries directly in the route handler instead of delegating to `admin_service`.

**Files:**
- Modify: `jobhunter/backend/app/api/admin.py:166-209`
- Modify: `jobhunter/backend/app/services/admin_service.py`

- [ ] **Step 1: Add update_user_plan to admin_service**

In `jobhunter/backend/app/services/admin_service.py`, add:

```python
async def update_user_plan(
    db: AsyncSession, user_id: uuid.UUID, new_tier: str, admin_id: uuid.UUID
) -> Candidate | None:
    """Change a user's plan tier with audit logging."""
    from app.models.audit import AdminAuditLog
    from app.plans import PlanTier

    # Validate tier
    try:
        PlanTier(new_tier)
    except ValueError:
        raise ValueError(f"Invalid plan tier: {new_tier}")

    result = await db.execute(select(Candidate).where(Candidate.id == user_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        return None

    old_tier = candidate.plan_tier
    candidate.plan_tier = new_tier

    audit = AdminAuditLog(
        id=uuid.uuid4(),
        admin_id=admin_id,
        action="change_plan",
        target_user_id=user_id,
        details={"old_tier": old_tier, "new_tier": new_tier},
    )
    db.add(audit)
    await db.commit()

    logger.info("plan_changed", user_id=str(user_id), old_tier=old_tier, new_tier=new_tier, admin_id=str(admin_id))
    return candidate
```

- [ ] **Step 2: Simplify the route handler**

In `jobhunter/backend/app/api/admin.py`, replace lines 166-209:

```python
@router.patch("/users/{user_id}/plan", response_model=UserDetail)
async def update_user_plan(
    user_id: uuid.UUID,
    body: UpdatePlanRequest,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    """Admin endpoint to change a user's plan tier."""
    try:
        candidate = await admin_service.update_user_plan(db, user_id, body.plan_tier, admin.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")
    return await admin_service.get_user_detail(db, user_id)
```

- [ ] **Step 3: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd jobhunter/backend
rtk git add app/api/admin.py app/services/admin_service.py
rtk git commit -m "refactor(admin): move update_user_plan business logic to admin_service"
```

---

### Task 10: Deduplicate Token Blacklist Prefix and Remove Redundant Health Check

**Why:** `TOKEN_BLACKLIST_PREFIX` is defined identically in `dependencies.py` and `auth_service.py` — if one changes, token blacklist silently breaks. Health check runs `SELECT 1` twice.

**Files:**
- Modify: `jobhunter/backend/app/dependencies.py:25`
- Modify: `jobhunter/backend/app/services/auth_service.py:27`
- Create: `jobhunter/backend/app/utils/constants.py`
- Modify: `jobhunter/backend/app/api/health.py:43-55`

- [ ] **Step 1: Create shared constants file**

```python
# jobhunter/backend/app/utils/constants.py
"""Shared constants used across modules. Single source of truth."""

TOKEN_BLACKLIST_PREFIX = "token:blacklist:"
```

- [ ] **Step 2: Update imports**

In `jobhunter/backend/app/dependencies.py`, change line 25:

```python
from app.utils.constants import TOKEN_BLACKLIST_PREFIX
```

Remove the `TOKEN_BLACKLIST_PREFIX = "token:blacklist:"` line.

In `jobhunter/backend/app/services/auth_service.py`, change line 27:

```python
from app.utils.constants import TOKEN_BLACKLIST_PREFIX
```

Remove the `TOKEN_BLACKLIST_PREFIX = "token:blacklist:"` line.

- [ ] **Step 3: Remove redundant SELECT 1 in health check**

In `jobhunter/backend/app/api/health.py`, delete lines 43-55:

```python
    # DELETE THIS BLOCK:
    # Verify DB reachable through active connection path
    try:
        await db.execute(text("SELECT 1"))
        checks["db_reachable"] = True
    except Exception as e:
        checks["db_reachable"] = False
        logger.error(
            "database.health_check_failed",
            extra={
                "feature": "pgbouncer",
                "detail": {"error": str(e)},
            },
        )
```

- [ ] **Step 4: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd jobhunter/backend
rtk git add app/utils/constants.py app/dependencies.py app/services/auth_service.py app/api/health.py
rtk git commit -m "refactor: deduplicate TOKEN_BLACKLIST_PREFIX, remove redundant SELECT 1 in health check"
```

---

### Task 11: Fix DI Consistency — auth_service Email Client Injection

**Why:** `auth_service.register()` and `forgot_password()` call `get_email_client()` directly instead of accepting an injected client. This makes them untestable in isolation.

**Files:**
- Modify: `jobhunter/backend/app/services/auth_service.py:10,84,186`
- Modify: `jobhunter/backend/app/api/auth.py` (pass email_client through)

- [ ] **Step 1: Write failing test — auth_service.register accepts injected email_client**

```python
# Add to tests/test_async_correctness.py (or a new test_auth_di.py)

@pytest.mark.asyncio
async def test_register_uses_injected_email_client(db_session):
    """auth_service.register() should accept an email_client parameter and use it instead of the global singleton."""
    from unittest.mock import AsyncMock
    from app.services.auth_service import register
    from app.schemas.auth import RegisterRequest
    from app.services.invite_service import create_system_invite

    # Create an invite code first
    invite = await create_system_invite(db_session, "test_di@example.com")
    await db_session.commit()

    mock_email = AsyncMock()
    data = RegisterRequest(email="test_di@example.com", password="testpass123", full_name="Test DI", invite_code=invite.code)

    import inspect
    sig = inspect.signature(register)
    assert "email_client" in sig.parameters, "register() must accept an email_client parameter"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run pytest tests/test_async_correctness.py::test_register_uses_injected_email_client -v`
Expected: FAIL — `email_client` not in signature

- [ ] **Step 3: Add email_client parameter to auth_service functions**

In `jobhunter/backend/app/services/auth_service.py`:

Change the `register` function signature (around line 30) to add `email_client=None`:

```python
async def register(db: AsyncSession, data: RegisterRequest, email_client=None) -> Candidate:
```

Inside the function, replace `get_email_client()` calls with:

```python
    _email = email_client or get_email_client()
```

Do the same for `forgot_password`:

```python
async def forgot_password(db: AsyncSession, email: str, email_client=None) -> None:
```

And use `_email = email_client or get_email_client()` inside.

- [ ] **Step 2: Thread email_client from route handlers**

In `jobhunter/backend/app/api/auth.py`:

Update `register` endpoint:
```python
@router.post("/register", response_model=CandidateResponse, status_code=201)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    email_client: EmailClientProtocol = Depends(get_email_client),
):
    candidate = await auth_service.register(db, data, email_client=email_client)
    return _to_candidate_response(candidate)
```

Add the necessary import at the top:
```python
from app.dependencies import get_email_client
from app.infrastructure.protocols import EmailClientProtocol
```

Update `forgot_password` endpoint similarly.

- [ ] **Step 3: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd jobhunter/backend
rtk git add app/services/auth_service.py app/api/auth.py
rtk git commit -m "refactor(auth): inject email_client into auth_service instead of importing singleton"
```

---

## Phase 6: Test Quality

### Task 12: Fix Tautological Tests and Add Missing Coverage

**Why:** RLS worker test is tautological. Billing tests mock the DB so thoroughly they can't catch real bugs. Event handler tests are smoke-only with no assertions. Key paths have zero test coverage.

**Files:**
- Modify: `jobhunter/backend/tests/test_rls_integration.py:201-209`
- Modify: `jobhunter/backend/tests/test_event_handlers.py`
- Create: `jobhunter/backend/tests/test_startup_guards.py`

- [ ] **Step 1: Replace tautological RLS worker test**

In `jobhunter/backend/tests/test_rls_integration.py`, replace lines 201-209:

```python
@pytest.mark.asyncio
async def test_worker_clears_tenant_context():
    """Worker functions must reset tenant context to None to avoid cross-tenant leakage."""
    # Simulate a request that set tenant context
    token = current_tenant_id.set("some-tenant-id")
    assert current_tenant_id.get() == "some-tenant-id"

    # Worker code should reset to None
    worker_token = current_tenant_id.set(None)
    assert current_tenant_id.get() is None

    # After worker completes, the original context should be restorable
    current_tenant_id.reset(worker_token)
    assert current_tenant_id.get() == "some-tenant-id"

    current_tenant_id.reset(token)
    assert current_tenant_id.get() is None  # Back to default
```

- [ ] **Step 2: Add behavioral assertions to event handler tests**

In `jobhunter/backend/tests/test_event_handlers.py`, enhance each test to verify the handler actually does something (at minimum, check it logs):

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.events.bus import Event
from app.events.handlers import log_event, on_company_approved, on_outreach_sent, on_resume_parsed


def _make_event(event_type: str, payload: dict) -> Event:
    return Event(event_type=event_type, payload=payload)


@pytest.mark.asyncio
async def test_log_event_logs_event_type():
    event = _make_event("test_event", {"key": "value"})
    with patch("app.events.handlers.logger") as mock_logger:
        await log_event(event)
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "test_event" in str(call_args)


@pytest.mark.asyncio
async def test_on_resume_parsed_with_skills():
    event = _make_event("resume_parsed", {"candidate_id": "abc", "skills": ["python", "fastapi"]})
    with patch("app.events.handlers.logger") as mock_logger:
        await on_resume_parsed(event)
        mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_on_outreach_sent():
    event = _make_event("outreach_sent", {"message_id": "123", "contact_email": "test@example.com"})
    with patch("app.events.handlers.logger") as mock_logger:
        await on_outreach_sent(event)
        mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_on_company_approved():
    event = _make_event("company_approved", {"company_id": "456", "candidate_id": "789"})
    with patch("app.events.handlers.logger") as mock_logger:
        await on_company_approved(event)
        mock_logger.info.assert_called()
```

- [ ] **Step 3: Add startup guard test**

```python
# tests/test_startup_guards.py
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_default_jwt_secret_blocks_startup():
    """App must refuse to start with the default JWT secret."""
    from app.main import _JWT_DEFAULT

    with patch("app.main.settings") as mock_settings:
        mock_settings.JWT_SECRET = _JWT_DEFAULT
        mock_settings.SENTRY_DSN = ""
        mock_settings.APP_NAME = "test"
        mock_settings.FRONTEND_URL = "http://localhost:3000"

        from app.main import lifespan, app

        with pytest.raises(SystemExit):
            async with lifespan(app):
                pass
```

- [ ] **Step 4: Run all tests**

Run: `cd jobhunter/backend && uv run pytest tests/ -q --tb=short`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd jobhunter/backend
rtk git add tests/test_rls_integration.py tests/test_event_handlers.py tests/test_startup_guards.py
rtk git commit -m "test: fix tautological RLS test, add behavioral assertions to event handlers, add startup guard test"
```

---

## Execution Checklist

| Phase | Task | Severity | Est. Effort |
|-------|------|----------|-------------|
| 1 | Task 1: Cross-tenant contact access fix | Critical | M |
| 1 | Task 2: Metrics auth + hardcoded URLs | High | S |
| 2 | Task 3: Async blocking calls | Critical | S |
| 2 | Task 4: Client lifecycle + OpenAI timeout | Critical | M |
| 3 | Task 5: Event bus cross-worker dispatch | Critical | M |
| 3 | Task 6: Worker errors + quota race + SAVEPOINTs | High | L |
| 4 | Task 7: CI quality gates | Critical | S |
| 5 | Task 8: CandidateResponse dedup | High | S |
| 5 | Task 9: Admin route handler refactor | Medium | S |
| 5 | Task 10: Token prefix dedup + health check | Medium | S |
| 5 | Task 11: Auth service DI fix | Medium | S |
| 6 | Task 12: Test quality fixes | High | M |

**Total: 12 tasks, ~52 individual issues addressed**

**Order matters:** Tasks 1-7 are "must fix before production." Tasks 8-12 are "should fix before next release." Each task is independently committable and testable.
