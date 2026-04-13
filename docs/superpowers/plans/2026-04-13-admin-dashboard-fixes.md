# Admin Dashboard Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two broken admin dashboard features: empty Activity Feed (events never persisted to DB) and missing waitlist status counts / quota.

**Architecture:** Event handlers get a new `persist_analytics` handler that writes to `analytics_events` via its own DB session. Waitlist endpoint adds status count aggregation and daily quota lookup to its response.

**Tech Stack:** FastAPI, SQLAlchemy async, Redis, pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/events/handlers.py` | Modify | Add `persist_analytics` handler that writes to `analytics_events` table |
| `backend/app/main.py` | Modify:68-78 | Subscribe `persist_analytics` to all three event types |
| `backend/app/schemas/admin.py` | Modify:110-112 | Add `status_counts` and `quota_remaining` to `WaitlistListResponse` |
| `backend/app/api/admin.py` | Modify:317-336 | Query status counts + Redis quota in `list_waitlist` |
| `backend/tests/test_event_handlers.py` | Modify | Add test for `persist_analytics` |
| `backend/tests/test_admin.py` | Modify | Add test for waitlist status counts + quota |

---

### Task 1: Wire event handlers to persist analytics events

**Files:**
- Modify: `backend/app/events/handlers.py`
- Modify: `backend/app/main.py:68-78`
- Test: `backend/tests/test_event_handlers.py`

The event handlers currently only log to structlog. They need to also write to the `analytics_events` table. The handlers run outside a request context, so they need their own DB session from `async_session_factory`.

**Event type mapping** (from `activity-feed.tsx` EVENT_CONFIG):
- `company_approved` → event_type=`company_approved`, entity_type=`company`
- `resume_parsed` → event_type=`resume_parsed`, entity_type=`resume`
- `outreach_sent` → event_type=`email_sent`, entity_type=`message`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_event_handlers.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_persist_analytics_writes_to_db():
    event = _make_event("company_approved", {
        "candidate_id": "00000000-0000-0000-0000-000000000001",
        "company_id": "00000000-0000-0000-0000-000000000002",
    })

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    with patch("app.events.handlers.async_session_factory", mock_factory):
        from app.events.handlers import persist_analytics
        await persist_analytics(event)

    mock_session.add.assert_called_once()
    added_obj = mock_session.add.call_args[0][0]
    assert added_obj.event_type == "company_approved"
    assert added_obj.entity_type == "company"
    assert str(added_obj.candidate_id) == "00000000-0000-0000-0000-000000000001"
    mock_session.commit.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run pytest tests/test_event_handlers.py::test_persist_analytics_writes_to_db -v`
Expected: FAIL — `persist_analytics` does not exist yet.

- [ ] **Step 3: Implement `persist_analytics` handler**

In `backend/app/events/handlers.py`, add:

```python
import uuid
from datetime import UTC, datetime

from app.events.bus import Event
from app.infrastructure.database import async_session_factory
from app.models.analytics import AnalyticsEvent

# Map event_type -> (analytics event_type, entity_type, entity_id payload key)
_EVENT_MAP: dict[str, tuple[str, str, str]] = {
    "company_approved": ("company_approved", "company", "company_id"),
    "resume_parsed": ("resume_parsed", "resume", "resume_id"),
    "outreach_sent": ("email_sent", "message", "message_id"),
}


async def persist_analytics(event: Event) -> None:
    """Persist domain events to analytics_events table for the admin activity feed."""
    mapping = _EVENT_MAP.get(event.event_type)
    if not mapping:
        return

    event_type, entity_type, entity_id_key = mapping
    candidate_id_str = event.payload.get("candidate_id")
    if not candidate_id_str:
        return

    entity_id_str = event.payload.get(entity_id_key)

    async with async_session_factory() as session:
        analytics = AnalyticsEvent(
            id=uuid.uuid4(),
            candidate_id=uuid.UUID(candidate_id_str),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=uuid.UUID(entity_id_str) if entity_id_str else None,
            metadata_=event.payload,
            occurred_at=datetime.now(UTC),
        )
        session.add(analytics)
        await session.commit()
```

Keep existing `import structlog` and existing handlers unchanged. Add the new imports at the top of the file.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd jobhunter/backend && uv run pytest tests/test_event_handlers.py::test_persist_analytics_writes_to_db -v`
Expected: PASS

- [ ] **Step 5: Subscribe `persist_analytics` in `main.py`**

In `backend/app/main.py`, modify the event bus initialization block (around line 70):

Change the import line:
```python
from app.events.handlers import log_event, on_company_approved, on_outreach_sent, on_resume_parsed
```
To:
```python
from app.events.handlers import log_event, on_company_approved, on_outreach_sent, on_resume_parsed, persist_analytics
```

Add subscriptions after the existing ones (after line 78):
```python
    bus.subscribe("company_approved", persist_analytics)
    bus.subscribe("outreach_sent", persist_analytics)
    bus.subscribe("resume_parsed", persist_analytics)
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/events/handlers.py backend/app/main.py backend/tests/test_event_handlers.py
git commit -m "fix(admin): persist domain events to analytics_events for activity feed"
```

---

### Task 2: Add waitlist status counts and quota to API response

**Files:**
- Modify: `backend/app/schemas/admin.py:110-112`
- Modify: `backend/app/api/admin.py:317-336`
- Test: `backend/tests/test_admin.py`

The frontend expects `status_counts` (dict of status→count) and `quota_remaining` (int) in the waitlist response, but the backend only returns `entries` and `total`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_admin.py`:

```python
class TestWaitlistStatusCounts:
    @pytest.mark.asyncio
    async def test_waitlist_returns_status_counts_and_quota(
        self, client: AsyncClient, admin_headers: dict, db_session: AsyncSession,
    ):
        from app.models.waitlist import WaitlistEntry

        db_session.add(WaitlistEntry(email="pending1@test.com", status="pending"))
        db_session.add(WaitlistEntry(email="pending2@test.com", status="pending"))
        db_session.add(WaitlistEntry(email="invited1@test.com", status="invited"))
        db_session.add(WaitlistEntry(email="reg1@test.com", status="registered"))
        await db_session.flush()

        resp = await client.get(f"{API}/admin/waitlist", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert "status_counts" in data
        assert data["status_counts"]["pending"] == 2
        assert data["status_counts"]["invited"] == 1
        assert data["status_counts"]["registered"] == 1
        assert data["status_counts"]["invite_failed"] == 0

        assert "quota_remaining" in data
        assert isinstance(data["quota_remaining"], int)
        assert data["quota_remaining"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run pytest tests/test_admin.py::TestWaitlistStatusCounts -v`
Expected: FAIL — `status_counts` not in response.

- [ ] **Step 3: Update `WaitlistListResponse` schema**

In `backend/app/schemas/admin.py`, change:

```python
class WaitlistListResponse(BaseModel):
    entries: list[WaitlistEntryResponse]
    total: int
```

To:

```python
class WaitlistListResponse(BaseModel):
    entries: list[WaitlistEntryResponse]
    total: int
    status_counts: dict[str, int]
    quota_remaining: int
```

- [ ] **Step 4: Update `list_waitlist` endpoint to compute counts and quota**

In `backend/app/api/admin.py`, replace the `list_waitlist` function body (lines 325-336):

```python
    """List waitlist entries, optionally filtered by status."""
    q = select(WaitlistEntry).order_by(WaitlistEntry.created_at.asc())
    if status:
        q = q.where(WaitlistEntry.status == status)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0

    entries_result = await db.execute(q.offset(skip).limit(limit))
    entries = list(entries_result.scalars().all())

    # Status counts (always unfiltered so cards show global totals)
    count_result = await db.execute(
        select(WaitlistEntry.status, func.count()).group_by(WaitlistEntry.status)
    )
    raw_counts = dict(count_result.all())
    status_counts = {
        "pending": raw_counts.get("pending", 0),
        "invited": raw_counts.get("invited", 0),
        "invite_failed": raw_counts.get("invite_failed", 0),
        "registered": raw_counts.get("registered", 0),
    }

    # Daily quota remaining
    redis = get_redis()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"admin:daily_invites:{today}"
    used = 0
    try:
        val = await redis.get(key)
        used = int(val) if val else 0
    except Exception:
        pass
    quota_remaining = max(0, settings.MAX_DAILY_INVITES - used)

    return WaitlistListResponse(
        entries=entries,
        total=total,
        status_counts=status_counts,
        quota_remaining=quota_remaining,
    )
```

Make sure `datetime` and `UTC` are already imported at the top of `admin.py` (they are — line 2).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd jobhunter/backend && uv run pytest tests/test_admin.py::TestWaitlistStatusCounts -v`
Expected: PASS

- [ ] **Step 6: Run full admin test suite to check for regressions**

Run: `cd jobhunter/backend && uv run pytest tests/test_admin.py tests/test_waitlist_api_extended.py tests/test_waitlist_invites.py -v`
Expected: All tests PASS. Existing waitlist tests may need minor updates if they assert on exact response shape — check and fix any that fail because of the new fields.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/admin.py backend/app/api/admin.py backend/tests/test_admin.py
git commit -m "fix(admin): add waitlist status counts and quota to API response"
```

---

### Task 3: Run full test suite and verify

- [ ] **Step 1: Run all backend tests**

Run: `cd jobhunter/backend && uv run pytest --tb=short -q`
Expected: All tests pass (no regressions from existing ~110 tests).

- [ ] **Step 2: Run frontend type check**

Run: `cd jobhunter/frontend && npx tsc --noEmit`
Expected: Only the pre-existing `use-admin.ts:78` error (unrelated `updateUserPlan`).

- [ ] **Step 3: Final commit if any fixups needed, then push**

```bash
git push origin feat/volume-test
```
