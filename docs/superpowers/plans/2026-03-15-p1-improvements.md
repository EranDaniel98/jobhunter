# P1 Improvements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 5 independent P1 features: waitlist-to-invites, DNS health check, pgBouncer pooling, OpenAI dossier caching, and batch ARQ cron jobs.

**Architecture:** Each feature is independent and deployed separately. Backend is FastAPI + SQLAlchemy async + Redis. Frontend is Next.js. Background jobs via ARQ. All features follow existing patterns: protocol-based DI, structured logging via structlog, Pydantic schemas, Alembic migrations with numeric prefixes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, asyncpg, Redis, ARQ, dnspython, Next.js 16, React 19, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-14-p1-improvements-design-v2.md`

---

## File Map

### Feature 1: Waitlist to Beta Invites
| Action | File |
|--------|------|
| Modify | `app/models/waitlist.py` — add status, invited_at, invite_code_id, invite_error columns |
| Modify | `app/models/invite.py` — add email column |
| Create | `alembic/versions/022_add_waitlist_status.py` — migration |
| Modify | `app/config.py` — add MAX_DAILY_INVITES |
| Modify | `app/services/invite_service.py` — add create_system_invite() |
| Modify | `app/services/auth_service.py` — registration hook |
| Modify | `app/schemas/admin.py` — WaitlistEntryResponse, WaitlistListResponse |
| Modify | `app/api/admin.py` — waitlist endpoints |
| Create | `tests/test_waitlist_invites.py` |
| Create | `frontend/src/app/(dashboard)/admin/waitlist/page.tsx` |

### Feature 2: SPF/DKIM Health Check
| Action | File |
|--------|------|
| Create | `app/services/dns_health_service.py` |
| Modify | `app/config.py` — add DNS config vars |
| Modify | `app/api/admin.py` — email-health endpoint |
| Modify | `pyproject.toml` — add dnspython |
| Create | `tests/test_dns_health.py` |
| Create | `frontend/src/components/admin/email-health-card.tsx` |
| Modify | `frontend/src/app/(marketing)/page.tsx` — fix trust signal |

### Feature 3: pgBouncer Connection Pooling
| Action | File |
|--------|------|
| Modify | `app/config.py` — add PGBOUNCER_URL |
| Modify | `app/infrastructure/database.py` — pgBouncer-aware engine creation |
| Modify | `app/api/health.py` — report connection mode |
| Modify | `app/api/admin.py` — pool stats endpoint |
| Modify | `docker-compose.yml` — add pgbouncer service |
| Modify | `backend/.env.example` — add PGBOUNCER_URL |
| Create | `tests/test_pgbouncer.py` |

### Feature 4: OpenAI Response Caching
| Action | File |
|--------|------|
| Create | `app/infrastructure/dossier_cache.py` — cache + stampede lock |
| Modify | `app/services/company_service.py` — split DOSSIER_SCHEMA/PROMPT |
| Modify | `app/schemas/company.py` — CompanyDossierGeneric, CompanyDossierPersonal |
| Modify | `app/graphs/company_research.py` — two-phase generate_dossier_node |
| Modify | `app/config.py` — add DOSSIER_CACHE_TTL |
| Modify | `app/api/admin.py` — cache clear endpoint |
| Create | `tests/test_dossier_cache.py` |

### Feature 5: Batch ARQ Cron Jobs
| Action | File |
|--------|------|
| Modify | `app/worker.py` — coordinator pattern + chunk processors |
| Modify | `app/config.py` — add ARQ_CHUNK_SIZE, ARQ_CHUNK_CONCURRENCY, ARQ_MAX_CHUNKS_PER_RUN |
| Create | `tests/test_worker_batching.py` |

---

## Chunk 1: Feature 1 — Waitlist to Beta Invites

### Task 1.1: Migration and Models

**Files:**
- Modify: `app/models/waitlist.py`
- Modify: `app/models/invite.py`
- Create: `alembic/versions/022_add_waitlist_status.py`

- [ ] **Step 1: Update WaitlistEntry model**

In `app/models/waitlist.py`, add new columns using the existing `Mapped`/`mapped_column` API (matching the codebase convention):

```python
from datetime import UTC, datetime
from typing import Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="landing_page")
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invite_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invite_codes.id"), nullable=True
    )
    invite_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_waitlist_entries_status_created", "status", "created_at"),
    )
```

- [ ] **Step 2: Update InviteCode model**

In `app/models/invite.py`:

a) Make `invited_by_id` nullable (required for system-generated invites with no candidate actor):

```python
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=True
    )
```

b) Add the `email` column after `is_used`:

```python
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 3: Create migration 022**

Run: `cd jobhunter/backend && uv run alembic revision --autogenerate -m "022_add_waitlist_status"`

Then verify the generated migration includes:
- `waitlist_entries.status` (String, default "pending")
- `waitlist_entries.invited_at` (DateTime, nullable)
- `waitlist_entries.invite_code_id` (UUID FK)
- `waitlist_entries.invite_error` (String, nullable)
- `invite_codes.email` (String, nullable)
- Composite index on `(status, created_at)` for waitlist_entries

If the autogenerate misses the composite index, add manually:

```python
op.create_index("ix_waitlist_entries_status_created", "waitlist_entries", ["status", "created_at"])
```

Also verify the migration includes making `invite_codes.invited_by_id` nullable (required for system-generated invites). If autogenerate misses it, add:

```python
op.alter_column("invite_codes", "invited_by_id", existing_type=sa.dialects.postgresql.UUID(), nullable=True)
```

- [ ] **Step 4: Verify migration applies cleanly**

Run: `cd jobhunter/backend && uv run alembic upgrade head`
Expected: Migration applies without errors.

- [ ] **Step 5: Commit**

```bash
git add app/models/waitlist.py app/models/invite.py alembic/versions/022_*.py
git commit -m "feat(waitlist): add status tracking columns and migration 022"
```

---

### Task 1.2: Config and Invite Service

**Files:**
- Modify: `app/config.py`
- Modify: `app/services/invite_service.py`

- [ ] **Step 1: Write failing test for create_system_invite**

Create `tests/test_waitlist_invites.py`:

```python
import pytest
from datetime import datetime, timezone
from app.services.invite_service import create_system_invite


@pytest.mark.asyncio
async def test_create_system_invite(db_session):
    """System invite has no invited_by and stores email."""
    invite = await create_system_invite(db_session, "test@example.com")

    assert invite.code is not None
    assert len(invite.code) > 0
    assert invite.invited_by_id is None
    assert invite.email == "test@example.com"
    assert invite.is_used is False
    assert invite.expires_at > datetime.now(timezone.utc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_waitlist_invites.py::test_create_system_invite -xvs`
Expected: FAIL — `ImportError: cannot import name 'create_system_invite'`

- [ ] **Step 3: Add MAX_DAILY_INVITES to config**

In `app/config.py`, add after `INVITE_EXPIRE_DAYS` (around line 50):

```python
    MAX_DAILY_INVITES: int = 200
```

- [ ] **Step 4: Implement create_system_invite**

In `app/services/invite_service.py`, add after the existing `create_invite()` function (after line 30):

```python
async def create_system_invite(db: AsyncSession, email: str) -> InviteCode:
    """Create an invite code generated by the system (no candidate actor)."""
    code = secrets.token_urlsafe(16)
    invite = InviteCode(
        code=code,
        invited_by_id=None,
        email=email,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.INVITE_EXPIRE_DAYS),
    )
    db.add(invite)
    await db.flush()
    return invite
```

Ensure the imports at top of file include `datetime`, `timezone`, `timedelta`, `secrets`, and `settings`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_waitlist_invites.py::test_create_system_invite -xvs`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/config.py app/services/invite_service.py tests/test_waitlist_invites.py
git commit -m "feat(waitlist): add create_system_invite and MAX_DAILY_INVITES config"
```

---

### Task 1.3: Schemas and Admin API Endpoints

**Files:**
- Modify: `app/schemas/admin.py`
- Modify: `app/api/admin.py`

- [ ] **Step 1: Write failing tests for waitlist API**

Add to `tests/test_waitlist_invites.py`:

```python
@pytest.mark.asyncio
async def test_admin_list_waitlist(authenticated_admin_client, db_session):
    """Admin can list waitlist entries with filtering."""
    # Seed a waitlist entry
    from app.models.waitlist import WaitlistEntry
    entry = WaitlistEntry(email="wait@example.com", source="landing")
    db_session.add(entry)
    await db_session.commit()

    resp = await authenticated_admin_client.get("/api/v1/admin/waitlist")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) >= 1
    assert data["entries"][0]["email"] == "wait@example.com"
    assert data["entries"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_admin_invite_waitlist_entry(authenticated_admin_client, db_session):
    """Admin can invite a waitlist entry."""
    from app.models.waitlist import WaitlistEntry
    entry = WaitlistEntry(email="invite@example.com", source="landing")
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)

    resp = await authenticated_admin_client.post(f"/api/v1/admin/waitlist/{entry.id}/invite")
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data

    # Verify entry status updated
    await db_session.refresh(entry)
    assert entry.status == "invited"
    assert entry.invited_at is not None


@pytest.mark.asyncio
async def test_admin_invite_idempotent(authenticated_admin_client, db_session):
    """Inviting an already-invited entry returns existing code."""
    from app.models.waitlist import WaitlistEntry
    entry = WaitlistEntry(email="idem@example.com", source="landing")
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)

    resp1 = await authenticated_admin_client.post(f"/api/v1/admin/waitlist/{entry.id}/invite")
    resp2 = await authenticated_admin_client.post(f"/api/v1/admin/waitlist/{entry.id}/invite")
    assert resp1.json()["code"] == resp2.json()["code"]


@pytest.mark.asyncio
async def test_admin_invite_batch(authenticated_admin_client, db_session):
    """Admin can batch-invite multiple entries."""
    from app.models.waitlist import WaitlistEntry
    entries = []
    for i in range(3):
        e = WaitlistEntry(email=f"batch{i}@example.com", source="landing")
        db_session.add(e)
        entries.append(e)
    await db_session.commit()
    for e in entries:
        await db_session.refresh(e)

    ids = [e.id for e in entries]
    resp = await authenticated_admin_client.post(
        "/api/v1/admin/waitlist/invite-batch",
        json={"ids": ids},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invited"] == 3
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_admin_invite_quota_exceeded(authenticated_admin_client, db_session, redis_client):
    """429 returned with Retry-After when daily quota exceeded."""
    from app.models.waitlist import WaitlistEntry
    from app.config import settings

    entry = WaitlistEntry(email="quota@example.com", source="landing")
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)

    # Set quota to max
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await redis_client.set(f"waitlist:invites:daily:{today}", str(settings.MAX_DAILY_INVITES))

    resp = await authenticated_admin_client.post(f"/api/v1/admin/waitlist/{entry.id}/invite")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_waitlist_invites.py -xvs -k "admin"`
Expected: FAIL — 404 or missing endpoint

- [ ] **Step 3: Add Pydantic schemas**

In `app/schemas/admin.py`, add at the end:

```python
class WaitlistEntryResponse(BaseModel):
    id: int
    email: str
    source: str | None
    status: str
    created_at: datetime
    invited_at: datetime | None
    invite_error: str | None

    model_config = ConfigDict(from_attributes=True)


class WaitlistListResponse(BaseModel):
    entries: list[WaitlistEntryResponse]
    total: int


class WaitlistInviteResponse(BaseModel):
    code: str
    email: str
    expires_at: datetime


class WaitlistBatchRequest(BaseModel):
    ids: list[int]


class WaitlistBatchResponse(BaseModel):
    invited: int
    skipped: int
    failed: int
    errors: list[str]
    daily_quota_remaining: int
```

Add `datetime` and `ConfigDict` to imports if not already present.

- [ ] **Step 4: Implement admin waitlist endpoints**

In `app/api/admin.py`, add the following endpoints. Import required modules at the top:

```python
from app.models.waitlist import WaitlistEntry
from app.services.invite_service import create_system_invite
from app.infrastructure.redis_client import get_redis
from app.schemas.admin import (
    WaitlistListResponse, WaitlistEntryResponse,
    WaitlistInviteResponse, WaitlistBatchRequest, WaitlistBatchResponse,
)
```

Add endpoints:

```python
@router.get("/waitlist", response_model=WaitlistListResponse)
async def list_waitlist(
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: Candidate = Depends(require_admin),
):
    query = select(WaitlistEntry).order_by(WaitlistEntry.created_at.asc())
    if status:
        query = query.where(WaitlistEntry.status == status)
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()
    result = await db.execute(query.offset(skip).limit(limit))
    entries = result.scalars().all()
    return WaitlistListResponse(
        entries=[WaitlistEntryResponse.model_validate(e) for e in entries],
        total=total,
    )


@router.post("/waitlist/{entry_id}/invite", response_model=WaitlistInviteResponse)
async def invite_waitlist_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Candidate = Depends(require_admin),
):
    entry = await db.get(WaitlistEntry, entry_id)
    if not entry:
        raise HTTPException(404, "Waitlist entry not found")

    # Idempotent: if already invited, return existing code
    if entry.status == "invited" and entry.invite_code_id:
        from app.models.invite import InviteCode
        invite = await db.get(InviteCode, entry.invite_code_id)
        if invite:
            return WaitlistInviteResponse(code=invite.code, email=entry.email, expires_at=invite.expires_at)

    # Check daily quota
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    quota_key = f"waitlist:invites:daily:{today}"
    current = int(await redis.get(quota_key) or 0)
    if current >= settings.MAX_DAILY_INVITES:
        logger.warning("waitlist.quota_exceeded", extra={
            "feature": "waitlist_invites", "action": "invite_single",
            "detail": {"requested": 1, "remaining": 0},
        })
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": "Daily invite quota exceeded"},
            headers={"Retry-After": "86400"},
        )

    # Reserve quota before sending (spec: decrement before processing)
    await redis.incr(quota_key)
    await redis.expire(quota_key, 172800)  # 48h TTL

    # Create invite
    invite = await create_system_invite(db, entry.email)
    entry.status = "invited"
    entry.invited_at = datetime.now(timezone.utc)
    entry.invite_code_id = invite.id

    # Send email (best-effort)
    try:
        from app.dependencies import get_email_client
        email_client = get_email_client()
        frontend_url = settings.FRONTEND_URL if hasattr(settings, "FRONTEND_URL") else "https://hunter-job.com"
        await email_client.send(
            to=entry.email,
            subject="You're invited to JobHunter AI",
            text=f"Hi! You signed up for the JobHunter AI waitlist and we'd love to have you.\n\nYour invite link: {frontend_url}/register?invite={invite.code}\n\nThis link expires in 7 days.",
        )
    except Exception as e:
        entry.status = "invite_failed"
        entry.invite_error = str(e)
        await redis.decr(quota_key)  # Release reserved quota on failure
        logger.error("waitlist.invite_failed", extra={
            "feature": "waitlist_invites", "action": "invite_sent",
            "item_id": str(entry_id), "status": "failure",
            "detail": {"error": str(e)},
        })

    await db.commit()

    # Audit log
    await admin_service.create_audit_log(db, admin.id, "invite_waitlist", details={"email": entry.email})

    logger.info("waitlist.invite_sent", extra={
        "feature": "waitlist_invites", "action": "invite_sent",
        "item_id": str(entry_id), "status": entry.status,
    })
    return WaitlistInviteResponse(code=invite.code, email=entry.email, expires_at=invite.expires_at)


@router.post("/waitlist/invite-batch", response_model=WaitlistBatchResponse)
async def invite_waitlist_batch(
    body: WaitlistBatchRequest,
    db: AsyncSession = Depends(get_db),
    admin: Candidate = Depends(require_admin),
):
    if len(body.ids) > 50:
        raise HTTPException(400, "Max 50 entries per batch")

    # Check quota
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    quota_key = f"waitlist:invites:daily:{today}"
    current = int(await redis.get(quota_key) or 0)
    remaining = settings.MAX_DAILY_INVITES - current
    if remaining < len(body.ids):
        logger.warning("waitlist.quota_exceeded", extra={
            "feature": "waitlist_invites", "action": "invite_batch",
            "detail": {"requested": len(body.ids), "remaining": remaining},
        })
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": f"Daily quota insufficient: {remaining} remaining, {len(body.ids)} requested"},
            headers={"Retry-After": "86400"},
        )

    invited = 0
    skipped = 0
    failed = 0
    errors = []

    for entry_id in body.ids:
        entry = await db.get(WaitlistEntry, entry_id)
        if not entry or entry.status in ("invited", "registered"):
            skipped += 1
            continue

        try:
            invite = await create_system_invite(db, entry.email)
            entry.status = "invited"
            entry.invited_at = datetime.now(timezone.utc)
            entry.invite_code_id = invite.id

            from app.dependencies import get_email_client
            email_client = get_email_client()
            frontend_url = settings.FRONTEND_URL if hasattr(settings, "FRONTEND_URL") else "https://hunter-job.com"
            await email_client.send(
                to=entry.email,
                subject="You're invited to JobHunter AI",
                text=f"Hi! You signed up for the JobHunter AI waitlist and we'd love to have you.\n\nYour invite link: {frontend_url}/register?invite={invite.code}\n\nThis link expires in 7 days.",
            )
            await db.commit()
            await redis.incr(quota_key)
            invited += 1
        except Exception as e:
            entry.status = "invite_failed"
            entry.invite_error = str(e)
            await db.commit()
            failed += 1
            errors.append(f"{entry.email}: {str(e)}")

    remaining_after = settings.MAX_DAILY_INVITES - int(await redis.get(quota_key) or 0)
    await redis.expire(quota_key, 172800)

    await admin_service.create_audit_log(db, admin.id, "invite_waitlist_batch", details={
        "invited": invited, "skipped": skipped, "failed": failed,
    })

    logger.info("waitlist.batch_complete", extra={
        "detail": {"invited": invited, "skipped": skipped, "failed": failed},
    })
    return WaitlistBatchResponse(
        invited=invited, skipped=skipped, failed=failed,
        errors=errors, daily_quota_remaining=remaining_after,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_waitlist_invites.py -xvs`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/schemas/admin.py app/api/admin.py tests/test_waitlist_invites.py
git commit -m "feat(waitlist): admin API endpoints for invite management"
```

---

### Task 1.4: Registration Hook

**Files:**
- Modify: `app/services/auth_service.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_waitlist_invites.py`:

```python
@pytest.mark.asyncio
async def test_registration_updates_waitlist_status(db_session):
    """Registering with an invite code updates the matching waitlist entry to 'registered'."""
    from app.models.waitlist import WaitlistEntry
    from app.services.invite_service import create_system_invite
    from app.services.auth_service import register
    from app.schemas.auth import RegisterRequest

    # Create waitlist entry and invite
    entry = WaitlistEntry(email="hook@example.com", source="landing", status="invited")
    db_session.add(entry)
    await db_session.flush()

    invite = await create_system_invite(db_session, "hook@example.com")
    entry.invite_code_id = invite.id
    await db_session.commit()

    # Register with the invite code
    req = RegisterRequest(
        email="hook@example.com",
        password="testpass123",
        full_name="Test User",
        invite_code=invite.code,
    )
    candidate = await register(db_session, req)
    assert candidate is not None

    # Verify waitlist entry updated
    await db_session.refresh(entry)
    assert entry.status == "registered"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_waitlist_invites.py::test_registration_updates_waitlist_status -xvs`
Expected: FAIL — entry.status is still "invited"

- [ ] **Step 3: Implement registration hook**

In `app/services/auth_service.py`, after the `validate_and_consume` call (around line 51), add:

```python
    # Update matching waitlist entry
    if data.invite_code:
        from app.models.invite import InviteCode
        from app.models.waitlist import WaitlistEntry
        invite_result = await db.execute(
            select(InviteCode).where(InviteCode.code == data.invite_code)
        )
        invite_code_obj = invite_result.scalar_one_or_none()
        if invite_code_obj and invite_code_obj.email:
            waitlist_result = await db.execute(
                select(WaitlistEntry).where(WaitlistEntry.email == invite_code_obj.email)
            )
            waitlist_entry = waitlist_result.scalar_one_or_none()
            if waitlist_entry:
                waitlist_entry.status = "registered"
                logger.info("waitlist.registration_matched", extra={
                    "item_id": waitlist_entry.id,
                    "detail": {"email": waitlist_entry.email},
                })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_waitlist_invites.py::test_registration_updates_waitlist_status -xvs`
Expected: PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd jobhunter/backend && uv run python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add app/services/auth_service.py tests/test_waitlist_invites.py
git commit -m "feat(waitlist): registration hook updates waitlist entry to registered"
```

---

### Task 1.5: Frontend — Admin Waitlist Page

**Files:**
- Create: `frontend/src/app/(dashboard)/admin/waitlist/page.tsx`

- [ ] **Step 1: Create the waitlist admin page**

Create `frontend/src/app/(dashboard)/admin/waitlist/page.tsx` with:
- Table displaying waitlist entries (email, source, status badge, signed up date, error tooltip, actions)
- Filter dropdown: All / Pending / Invited / Failed / Registered
- "Invite" button per row (disabled for invited/registered, shows "Retry" for failed)
- Checkbox selection with "Invite Selected" bulk action
- Count badges per status at top
- Daily quota remaining display
- Uses existing `useQuery`/`useMutation` patterns from other admin pages
- Follows the styling conventions of existing admin pages (e.g., `admin/page.tsx`)

Reference: `frontend/src/app/(dashboard)/admin/page.tsx` for layout, query patterns, and component usage.

- [ ] **Step 2: Verify it renders**

Run: `cd jobhunter/frontend && npm run build`
Expected: Build succeeds without errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(dashboard\)/admin/waitlist/page.tsx
git commit -m "feat(waitlist): admin dashboard waitlist management page"
```

---

## Chunk 2: Feature 2 — SPF/DKIM Health Check

### Task 2.1: DNS Health Service

**Files:**
- Create: `app/services/dns_health_service.py`
- Modify: `app/config.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dnspython dependency**

Run: `cd jobhunter/backend && uv add "dnspython>=2.6.0"`

- [ ] **Step 2: Add config vars**

In `app/config.py`, add after the email settings section:

```python
    # DNS Health
    DKIM_SELECTOR: str = "resend"
    SPF_EXPECTED_INCLUDES: list[str] = ["amazonses.com", "resend.com"]
    DNS_HEALTH_CACHE_TTL: int = 300
    DNS_LOOKUP_TIMEOUT: float = 3.0
```

- [ ] **Step 3: Write failing test**

Create `tests/test_dns_health.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.dns_health_service import check_email_dns_health


def _make_txt_answer(text: str):
    """Create a mock DNS TXT answer."""
    record = MagicMock()
    record.strings = [text.encode()]
    return [record]


@pytest.mark.asyncio
async def test_dns_health_all_pass():
    """All records present returns overall pass."""
    with patch("app.services.dns_health_service._resolve_txt") as mock_resolve:
        async def resolver(qname):
            if qname.startswith("_dmarc"):
                return "v=DMARC1; p=quarantine"
            elif "_domainkey" in qname:
                return "v=DKIM1; k=rsa; p=MIG..."
            else:
                return "v=spf1 include:amazonses.com ~all"

        mock_resolve.side_effect = resolver
        result = await check_email_dns_health("example.com")

    assert result["overall"] == "pass"
    assert result["spf"]["status"] == "pass"
    assert result["dkim"]["status"] == "pass"
    assert result["dmarc"]["status"] == "pass"


@pytest.mark.asyncio
async def test_dns_health_spf_missing_is_fail():
    """Missing SPF record returns overall fail."""
    with patch("app.services.dns_health_service._resolve_txt") as mock_resolve:
        async def resolver(qname):
            if qname.startswith("_dmarc"):
                return "v=DMARC1; p=none"
            elif "_domainkey" in qname:
                return "v=DKIM1; k=rsa; p=MIG..."
            else:
                return None

        mock_resolve.side_effect = resolver
        result = await check_email_dns_health("example.com")

    assert result["overall"] == "fail"
    assert result["spf"]["status"] == "fail"


@pytest.mark.asyncio
async def test_dns_health_dmarc_missing_is_warning():
    """Missing DMARC with SPF present returns warning."""
    with patch("app.services.dns_health_service._resolve_txt") as mock_resolve:
        async def resolver(qname):
            if qname.startswith("_dmarc"):
                return None
            elif "_domainkey" in qname:
                return "v=DKIM1; k=rsa; p=MIG..."
            else:
                return "v=spf1 include:amazonses.com ~all"

        mock_resolve.side_effect = resolver
        result = await check_email_dns_health("example.com")

    assert result["overall"] == "warning"
    assert result["dmarc"]["status"] == "fail"


@pytest.mark.asyncio
async def test_dns_health_uses_configurable_dkim_selector():
    """DKIM lookup uses the configured selector from settings."""
    with patch("app.services.dns_health_service._resolve_txt") as mock_resolve:
        queried_names = []
        async def resolver(qname):
            queried_names.append(qname)
            return "v=spf1 include:amazonses.com ~all"
        mock_resolve.side_effect = resolver

        with patch("app.services.dns_health_service.settings") as mock_settings:
            mock_settings.DKIM_SELECTOR = "custom_selector"
            mock_settings.SPF_EXPECTED_INCLUDES = ["amazonses.com"]
            mock_settings.DNS_LOOKUP_TIMEOUT = 3.0
            mock_settings.DNS_HEALTH_CACHE_TTL = 0  # disable cache for test
            await check_email_dns_health("example.com", force=True)

    assert any("custom_selector._domainkey" in name for name in queried_names)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_dns_health.py -xvs`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 5: Implement DNS health service**

Create `app/services/dns_health_service.py`:

```python
import time
import structlog
import dns.asyncresolver
import dns.resolver
from app.config import settings

logger = structlog.get_logger()

_cache: dict = {"result": None, "expires_at": 0}


async def _resolve_txt(qname: str) -> str | None:
    """Resolve a TXT record, returning the concatenated text or None."""
    try:
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = settings.DNS_LOOKUP_TIMEOUT
        answers = await resolver.resolve(qname, "TXT")
        texts = []
        for rdata in answers:
            texts.append(b"".join(rdata.strings).decode())
        return " ".join(texts)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return None
    except (dns.resolver.LifetimeTimeout, dns.exception.Timeout):
        logger.warning("dns_health.lookup_timeout", extra={
            "feature": "dns_health", "detail": {"qname": qname},
        })
        raise TimeoutError(f"DNS lookup timed out for {qname}")
    except Exception:
        logger.error("dns_health.lookup_error", extra={
            "feature": "dns_health", "detail": {"qname": qname},
        })
        return None


async def check_email_dns_health(domain: str, force: bool = False) -> dict:
    """Check SPF, DKIM, and DMARC records for a domain."""
    now = time.time()
    if not force and _cache["result"] and _cache["expires_at"] > now:
        return _cache["result"]

    spf_record = None
    spf_status = "fail"
    dkim_status = "fail"
    dmarc_status = "fail"
    dmarc_record = None
    dmarc_recommendation = None

    # SPF
    try:
        txt = await _resolve_txt(domain)
        if txt and "v=spf1" in txt:
            spf_record = txt
            if any(inc in txt for inc in settings.SPF_EXPECTED_INCLUDES):
                spf_status = "pass"
    except TimeoutError:
        spf_status = "timeout"

    # DKIM
    try:
        dkim_qname = f"{settings.DKIM_SELECTOR}._domainkey.{domain}"
        txt = await _resolve_txt(dkim_qname)
        if txt and ("v=DKIM1" in txt or "k=rsa" in txt):
            dkim_status = "pass"
    except TimeoutError:
        dkim_status = "timeout"

    # DMARC
    try:
        dmarc_qname = f"_dmarc.{domain}"
        txt = await _resolve_txt(dmarc_qname)
        if txt and "v=DMARC1" in txt:
            dmarc_status = "pass"
            dmarc_record = txt
        else:
            dmarc_recommendation = "Add a DMARC record: v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com"
    except TimeoutError:
        dmarc_status = "timeout"

    # Overall
    if spf_status == "fail":
        overall = "fail"
    elif all(s == "pass" for s in [spf_status, dkim_status, dmarc_status]):
        overall = "pass"
    else:
        overall = "warning"

    from datetime import datetime, timezone
    result = {
        "domain": domain,
        "spf": {"status": spf_status, "record": spf_record},
        "dkim": {"status": dkim_status, "selector": settings.DKIM_SELECTOR},
        "dmarc": {
            "status": dmarc_status,
            "record": dmarc_record,
            "recommendation": dmarc_recommendation,
        },
        "overall": overall,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache["result"] = result
    _cache["expires_at"] = now + settings.DNS_HEALTH_CACHE_TTL

    logger.info("dns_health.check_complete", extra={
        "feature": "dns_health",
        "detail": {"spf": spf_status, "dkim": dkim_status, "dmarc": dmarc_status, "overall": overall},
    })

    return result
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_dns_health.py -xvs`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock app/config.py app/services/dns_health_service.py tests/test_dns_health.py
git commit -m "feat(dns): add SPF/DKIM/DMARC health check service"
```

---

### Task 2.2: Admin API Endpoint and Frontend

**Files:**
- Modify: `app/api/admin.py`
- Create: `frontend/src/components/admin/email-health-card.tsx`
- Modify: `frontend/src/app/(marketing)/page.tsx`

- [ ] **Step 1: Write failing test for endpoint**

Add to `tests/test_dns_health.py`:

```python
@pytest.mark.asyncio
async def test_admin_email_health_endpoint(authenticated_admin_client):
    """Admin can check email DNS health."""
    with patch("app.services.dns_health_service._resolve_txt") as mock_resolve:
        async def resolver(qname):
            return "v=spf1 include:amazonses.com ~all"
        mock_resolve.side_effect = resolver

        resp = await authenticated_admin_client.get("/api/v1/admin/email-health")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall" in data
    assert "spf" in data
    assert "dkim" in data
    assert "dmarc" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_dns_health.py::test_admin_email_health_endpoint -xvs`
Expected: FAIL — 404

- [ ] **Step 3: Add email-health endpoint**

In `app/api/admin.py`, add:

```python
from app.services.dns_health_service import check_email_dns_health

@router.get("/email-health")
async def get_email_health(
    force: bool = False,
    _: Candidate = Depends(require_admin),
):
    domain = settings.SENDER_EMAIL.split("@")[1] if "@" in settings.SENDER_EMAIL else settings.SENDER_EMAIL
    return await check_email_dns_health(domain, force=force)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_dns_health.py -xvs`
Expected: All PASS

- [ ] **Step 5: Create email health card component**

Create `frontend/src/components/admin/email-health-card.tsx`:
- Card with "Email Deliverability" title
- Three rows: SPF, DKIM, DMARC with status icons (green check, yellow warning, red X)
- Expandable details showing raw DNS record
- Overall status badge
- "Refresh" button calling `GET /api/v1/admin/email-health?force=true`
- Link to `docs/email-domain-setup.md` for setup instructions
- Uses existing component patterns from the admin dashboard

Reference: existing admin components for styling conventions.

- [ ] **Step 6: Fix landing page trust signal**

In `frontend/src/app/(marketing)/page.tsx`, find the text claiming "SPF/DKIM/DMARC verified" and replace with "Email deliverability monitoring".

- [ ] **Step 7: Verify frontend builds**

Run: `cd jobhunter/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 8: Commit**

```bash
git add app/api/admin.py tests/test_dns_health.py frontend/src/components/admin/email-health-card.tsx frontend/src/app/\(marketing\)/page.tsx
git commit -m "feat(dns): admin email health endpoint and dashboard card"
```

---

## Chunk 3: Feature 3 — pgBouncer Connection Pooling

### Task 3.1: Config and Database Module

**Files:**
- Modify: `app/config.py`
- Modify: `app/infrastructure/database.py`

- [ ] **Step 1: Write failing test for pgBouncer config selection**

Create `tests/test_pgbouncer.py`:

```python
import pytest
from unittest.mock import patch
from app.infrastructure.database import _get_engine_config


def test_direct_mode_when_no_pgbouncer_url():
    """Without PGBOUNCER_URL, uses DATABASE_URL with normal pool settings."""
    with patch("app.infrastructure.database.settings") as mock_settings:
        mock_settings.PGBOUNCER_URL = ""
        mock_settings.DATABASE_URL = "postgresql+asyncpg://localhost:5432/db"
        mock_settings.DB_POOL_SIZE = 10
        mock_settings.DB_MAX_OVERFLOW = 20
        config = _get_engine_config()
        assert config["pool_size"] == 10
        assert config["max_overflow"] == 20
        assert config["mode"] == "direct"


def test_pgbouncer_mode_reduces_pool():
    """With PGBOUNCER_URL set, reduces pool size."""
    with patch("app.infrastructure.database.settings") as mock_settings:
        mock_settings.PGBOUNCER_URL = "postgresql+asyncpg://localhost:6432/db"
        config = _get_engine_config()
        assert config["pool_size"] == 5
        assert config["max_overflow"] == 5
        assert config["mode"] == "pgbouncer"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_pgbouncer.py -xvs`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Add PGBOUNCER_URL to config**

In `app/config.py`, add in the database section:

```python
    PGBOUNCER_URL: str = ""
```

- [ ] **Step 4: Refactor database.py for pgBouncer awareness**

Rewrite `app/infrastructure/database.py` (29 lines → ~45 lines):

```python
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings

logger = structlog.get_logger()

# NOTE: When using pgBouncer in transaction mode, do NOT use session.begin_nested()
# or SAVEPOINTs — they are not supported through transaction-mode pgBouncer.


def _get_engine_config() -> dict:
    """Determine engine URL and pool settings based on PGBOUNCER_URL."""
    if settings.PGBOUNCER_URL:
        return {
            "url": settings.PGBOUNCER_URL,
            "pool_size": 5,
            "max_overflow": 5,
            "mode": "pgbouncer",
        }
    return {
        "url": settings.DATABASE_URL,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "mode": "direct",
    }


_config = _get_engine_config()

engine = create_async_engine(
    _config["url"],
    pool_size=_config["pool_size"],
    max_overflow=_config["max_overflow"],
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
)

logger.info("database.pool_mode", extra={
    "feature": "pgbouncer",
    "detail": {"mode": _config["mode"], "pool_size": _config["pool_size"], "max_overflow": _config["max_overflow"]},
})

# Install RLS listener if enabled
if settings.ENABLE_RLS:
    from app.middleware.tenant import install_rls_listener
    install_rls_listener(engine)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 5: Add health check response test**

Add to `tests/test_pgbouncer.py`:

```python
@pytest.mark.asyncio
async def test_health_reports_connection_mode(authenticated_client):
    """Health endpoint reports connection mode and db_reachable."""
    resp = await authenticated_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "connection_mode" in data
    assert data["connection_mode"] in ("direct", "pgbouncer")
    assert "db_reachable" in data
    assert data["db_reachable"] is True
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_pgbouncer.py -xvs`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/config.py app/infrastructure/database.py tests/test_pgbouncer.py
git commit -m "feat(pgbouncer): pgBouncer-aware engine with reduced pool sizing"
```

---

### Task 3.2: Health Check, Pool Stats, and Docker

**Files:**
- Modify: `app/api/health.py`
- Modify: `app/api/admin.py`
- Modify: `docker-compose.yml`
- Modify: `backend/.env.example`

- [ ] **Step 1: Extend health check to report connection mode**

In `app/api/health.py`, add to the response dict (after the Redis check):

```python
    from app.infrastructure.database import _config
    checks["connection_mode"] = _config["mode"]
    checks["pgbouncer_configured"] = bool(settings.PGBOUNCER_URL)

    # Verify DB reachable through active connection path
    try:
        await db.execute(text("SELECT 1"))
        checks["db_reachable"] = True
    except Exception as e:
        checks["db_reachable"] = False
        logger.error("database.health_check_failed", extra={
            "feature": "pgbouncer", "detail": {"error": str(e)},
        })
```

- [ ] **Step 2: Add pool stats admin endpoint**

In `app/api/admin.py`, add:

```python
@router.get("/db-pool-stats")
async def get_db_pool_stats(
    _: Candidate = Depends(require_admin),
):
    from app.infrastructure.database import engine, _config
    pool = engine.pool
    return {
        "connection_mode": _config["mode"],
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_in": pool.checkedin(),
    }
```

- [ ] **Step 3: Add pgBouncer to docker-compose.yml**

In `docker-compose.yml`, add after the `redis` service (after line 40):

```yaml
  pgbouncer:
    image: edoburu/pgbouncer:1.23.1
    environment:
      DATABASE_URL: postgresql://jobhunter:jobhunter@postgres:5432/jobhunter
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 200
      DEFAULT_POOL_SIZE: 20
      MIN_POOL_SIZE: 5
      RESERVE_POOL_SIZE: 5
    ports:
      - "6432:5432"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "pg_isready", "-h", "localhost", "-p", "5432"]
      interval: 10s
      timeout: 3s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: "0.5"
```

- [ ] **Step 4: Update .env.example**

Add to `backend/.env.example`:

```
# pgBouncer (optional - set to use connection pooling proxy)
# PGBOUNCER_URL=postgresql+asyncpg://jobhunter:jobhunter@localhost:6432/jobhunter
```

- [ ] **Step 5: Run full test suite**

Run: `cd jobhunter/backend && uv run python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add jobhunter/backend/app/api/health.py jobhunter/backend/app/api/admin.py jobhunter/docker-compose.yml jobhunter/backend/.env.example
git commit -m "feat(pgbouncer): health check, pool stats endpoint, Docker service"
```

---

## Chunk 4: Feature 4 — OpenAI Response Caching

### Task 4.1: Dossier Cache Layer

**Files:**
- Create: `app/infrastructure/dossier_cache.py`
- Modify: `app/config.py`

- [ ] **Step 1: Write failing tests for cache operations**

Create `tests/test_dossier_cache.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.infrastructure.dossier_cache import (
    get_cached_dossier,
    cache_dossier,
    invalidate_dossier,
    _compute_input_hash,
)


def test_compute_input_hash_deterministic():
    """Same inputs produce same hash."""
    h1 = _compute_input_hash("Acme", "acme.com", "Tech", "50-100", "A company", "Python")
    h2 = _compute_input_hash("Acme", "acme.com", "Tech", "50-100", "A company", "Python")
    assert h1 == h2
    assert len(h1) == 12


def test_compute_input_hash_changes_on_different_input():
    """Different inputs produce different hash."""
    h1 = _compute_input_hash("Acme", "acme.com", "Tech", "50-100", "A company", "Python")
    h2 = _compute_input_hash("Beta", "beta.com", "Finance", "100-200", "B company", "Java")
    assert h1 != h2


@pytest.mark.asyncio
async def test_cache_roundtrip(redis_client):
    """Cache a dossier and retrieve it."""
    data = {"culture_summary": "Great culture", "culture_score": 85}
    await cache_dossier("acme.com", "abc123", data, ttl=60)
    result = await get_cached_dossier("acme.com", "abc123")
    assert result == data


@pytest.mark.asyncio
async def test_cache_miss_returns_none(redis_client):
    """Missing cache key returns None."""
    result = await get_cached_dossier("nonexistent.com", "xyz")
    assert result is None


@pytest.mark.asyncio
async def test_cache_ttl_expiry(redis_client):
    """Cached entry expires after TTL."""
    import asyncio
    data = {"culture_summary": "Expires soon"}
    await cache_dossier("ttl.com", "hash1", data, ttl=1)  # 1 second TTL
    assert await get_cached_dossier("ttl.com", "hash1") is not None
    await asyncio.sleep(1.5)
    assert await get_cached_dossier("ttl.com", "hash1") is None


@pytest.mark.asyncio
async def test_invalidate_dossier(redis_client):
    """Invalidation removes cached entries."""
    await cache_dossier("acme.com", "hash1", {"a": 1}, ttl=60)
    await cache_dossier("acme.com", "hash2", {"b": 2}, ttl=60)
    deleted = await invalidate_dossier("acme.com")
    assert deleted >= 2
    assert await get_cached_dossier("acme.com", "hash1") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_dossier_cache.py -xvs`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Add DOSSIER_CACHE_TTL to config**

In `app/config.py`, add:

```python
    DOSSIER_CACHE_TTL: int = 604800  # 7 days
```

- [ ] **Step 4: Implement dossier cache**

Create `app/infrastructure/dossier_cache.py`:

```python
import hashlib
import json
import structlog
from app.infrastructure.redis_client import get_redis, redis_safe_get, redis_safe_setex
from app.config import settings

logger = structlog.get_logger()


def _compute_input_hash(
    name: str, domain: str, industry: str | None,
    size: str | None, description: str | None, tech_stack: str | None,
) -> str:
    """Hash company fields that affect generic dossier output."""
    payload = f"{name}|{domain}|{industry}|{size}|{description}|{tech_stack}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


async def get_cached_dossier(domain: str, input_hash: str) -> dict | None:
    """Get cached generic dossier from Redis."""
    key = f"dossier:generic:{domain}:{input_hash}"
    raw = await redis_safe_get(key)
    if raw:
        logger.info("dossier_cache.hit", extra={
            "feature": "dossier_cache", "detail": {"domain": domain, "hash": input_hash},
        })
        return json.loads(raw)
    return None


async def cache_dossier(domain: str, input_hash: str, data: dict, ttl: int | None = None) -> None:
    """Cache generic dossier result in Redis."""
    key = f"dossier:generic:{domain}:{input_hash}"
    ttl = ttl or settings.DOSSIER_CACHE_TTL
    raw = json.dumps(data)
    await redis_safe_setex(key, ttl, raw)
    logger.info("dossier_cache.stored", extra={
        "feature": "dossier_cache",
        "detail": {"domain": domain, "hash": input_hash, "size_bytes": len(raw)},
    })


async def invalidate_dossier(domain: str) -> int:
    """Delete all cached dossier entries for a domain."""
    redis = get_redis()
    pattern = f"dossier:generic:{domain}:*"
    keys = []
    async for key in redis.scan_iter(match=pattern):
        keys.append(key)
    if keys:
        deleted = await redis.delete(*keys)
        logger.info("dossier_cache.invalidated", extra={
            "feature": "dossier_cache", "detail": {"domain": domain, "keys_deleted": deleted},
        })
        return deleted
    return 0


async def acquire_stampede_lock(domain: str, ttl: int = 60) -> bool:
    """Try to acquire a lock for generating a dossier. Returns True if acquired."""
    redis = get_redis()
    lock_key = f"dossier:lock:{domain}"
    return await redis.set(lock_key, "1", nx=True, ex=ttl)


async def release_stampede_lock(domain: str) -> None:
    """Release the stampede lock."""
    redis = get_redis()
    lock_key = f"dossier:lock:{domain}"
    await redis.delete(lock_key)


async def wait_for_cache(domain: str, input_hash: str, max_wait: int = 30, interval: int = 2) -> dict | None:
    """Poll cache waiting for another generator to populate it."""
    import asyncio
    logger.info("dossier_cache.stampede_wait", extra={
        "feature": "dossier_cache", "detail": {"domain": domain},
    })
    elapsed = 0
    while elapsed < max_wait:
        result = await get_cached_dossier(domain, input_hash)
        if result:
            return result
        await asyncio.sleep(interval)
        elapsed += interval
    logger.warning("dossier_cache.stampede_timeout", extra={
        "feature": "dossier_cache", "detail": {"domain": domain},
    })
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_dossier_cache.py -xvs`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add app/config.py app/infrastructure/dossier_cache.py tests/test_dossier_cache.py
git commit -m "feat(cache): dossier cache layer with stampede protection"
```

---

### Task 4.2: Schema Split and Pipeline Changes

**Files:**
- Modify: `app/services/company_service.py`
- Modify: `app/schemas/company.py`
- Modify: `app/graphs/company_research.py`
- Modify: `app/api/admin.py`

- [ ] **Step 1: Define split schemas in company_service.py**

In `app/services/company_service.py`, replace `DOSSIER_SCHEMA` (lines 49-115) and `DOSSIER_PROMPT` (lines 17-47) with:

**`DOSSIER_GENERIC_PROMPT`** — same as current DOSSIER_PROMPT but:
- Remove candidate-specific instructions (why_hire_me, resume_bullets, fit_score_tips)
- Keep: company context, web context
- Instruct to generate only generic fields

**`DOSSIER_GENERIC_SCHEMA`** — JSON schema with `"additionalProperties": false` and ALL fields listed in the `"required"` array (project rule: OpenAI structured output rejects schemas without this). Fields:
- `culture_summary`, `culture_score`, `red_flags`, `interview_format`, `interview_questions`, `compensation_data`, `key_people`, `recent_news`

**`DOSSIER_PERSONAL_PROMPT`** — new prompt:
- Receives generic dossier output + candidate DNA summary
- Instructs to generate: why_hire_me, resume_bullets, fit_score_tips

**`DOSSIER_PERSONAL_SCHEMA`** — JSON schema with `"additionalProperties": false` and ALL fields in `"required"` array:
- `why_hire_me`, `resume_bullets`, `fit_score_tips`

Remember: escape all literal braces as `{{` and `}}` in prompt templates that use `.format()`.

- [ ] **Step 2: Add Pydantic models**

In `app/schemas/company.py`, add:

```python
class CompanyDossierGeneric(BaseModel):
    culture_summary: str
    culture_score: int
    red_flags: list[str]
    interview_format: str
    interview_questions: list[str]
    compensation_data: str
    key_people: list[dict]
    recent_news: list[str]


class CompanyDossierPersonal(BaseModel):
    why_hire_me: str
    resume_bullets: list[str]
    fit_score_tips: list[str]
```

- [ ] **Step 3: Modify generate_dossier_node for two-phase generation**

In `app/graphs/company_research.py`, modify `generate_dossier_node` (lines 166-230):

1. After loading company and candidate DNA, compute `input_hash` from company fields
2. Check cache via `get_cached_dossier(domain, input_hash)`
3. On cache hit: use cached generic data, skip OpenAI generic call
4. On cache miss: log `dossier_cache.miss` with `{"domain": domain, "hash": input_hash}`. Acquire stampede lock, generate with `DOSSIER_GENERIC_SCHEMA`, cache result, release lock
5. Always: call `parse_structured()` with `DOSSIER_PERSONAL_SCHEMA` + generic data + candidate DNA
6. Merge generic + personal into existing dossier record fields

Import from `dossier_cache.py`:

```python
from app.infrastructure.dossier_cache import (
    get_cached_dossier, cache_dossier, _compute_input_hash,
    acquire_stampede_lock, release_stampede_lock, wait_for_cache,
)
from app.services.company_service import (
    DOSSIER_GENERIC_PROMPT, DOSSIER_GENERIC_SCHEMA,
    DOSSIER_PERSONAL_PROMPT, DOSSIER_PERSONAL_SCHEMA,
)
```

- [ ] **Step 4: Add cache invalidation admin endpoint**

In `app/api/admin.py`, add:

```python
from app.infrastructure.dossier_cache import invalidate_dossier

@router.delete("/cache/dossier/{domain}")
async def clear_dossier_cache(
    domain: str,
    _: Candidate = Depends(require_admin),
):
    deleted = await invalidate_dossier(domain)
    return {"deleted": deleted, "domain": domain}
```

- [ ] **Step 5: Write integration test for cache behavior**

Add to `tests/test_dossier_cache.py`:

```python
@pytest.mark.asyncio
async def test_stampede_lock_prevents_duplicate_generation(redis_client):
    """Only one generator acquires the lock."""
    from app.infrastructure.dossier_cache import acquire_stampede_lock, release_stampede_lock
    assert await acquire_stampede_lock("test.com") is True
    assert await acquire_stampede_lock("test.com") is False  # Already locked
    await release_stampede_lock("test.com")
    assert await acquire_stampede_lock("test.com") is True  # Lock released
    await release_stampede_lock("test.com")
```

- [ ] **Step 6: Run full test suite**

Run: `cd jobhunter/backend && uv run python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add app/services/company_service.py app/schemas/company.py app/graphs/company_research.py app/api/admin.py tests/test_dossier_cache.py
git commit -m "feat(cache): two-phase dossier generation with Redis caching"
```

---

## Chunk 5: Feature 5 — Batch ARQ Cron Jobs

### Task 5.1: Config and Chunking Utilities

**Files:**
- Modify: `app/config.py`
- Modify: `app/worker.py`

- [ ] **Step 1: Write failing tests for chunking and coordinator pattern**

Create `tests/test_worker_batching.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio


def test_chunk_list():
    """Chunking splits items into correct groups."""
    from app.worker import _chunk_list
    items = list(range(25))
    chunks = _chunk_list(items, 10)
    assert len(chunks) == 3
    assert chunks[0] == list(range(10))
    assert chunks[1] == list(range(10, 20))
    assert chunks[2] == list(range(20, 25))


def test_chunk_list_empty():
    """Empty list produces no chunks."""
    from app.worker import _chunk_list
    assert _chunk_list([], 10) == []


def test_chunk_list_exact_size():
    """List exactly chunk size produces one chunk."""
    from app.worker import _chunk_list
    assert _chunk_list([1, 2, 3], 3) == [[1, 2, 3]]


@pytest.mark.asyncio
async def test_process_chunk_error_isolation():
    """One failing item in a chunk doesn't kill other items."""
    from app.worker import _process_chunk

    call_count = 0

    async def processor(item_id):
        nonlocal call_count
        call_count += 1
        if item_id == "fail":
            raise ValueError("Intentional failure")
        return f"ok:{item_id}"

    results = await _process_chunk(
        items=["a", "fail", "c"],
        processor=processor,
        concurrency=5,
        job_name="test",
    )
    assert call_count == 3  # All items were attempted
    assert results["succeeded"] == 2
    assert results["failed"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_worker_batching.py -xvs`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Add ARQ config vars**

In `app/config.py`, add:

```python
    # ARQ Batching
    ARQ_CHUNK_SIZE: int = 10
    ARQ_CHUNK_CONCURRENCY: int = 5
    ARQ_MAX_CHUNKS_PER_RUN: int = 50
```

- [ ] **Step 4: Add chunking utilities to worker.py**

In `app/worker.py`, add `import asyncio` to the top-level imports, then add these utility functions before the existing cron functions:

```python
import asyncio
import structlog

logger = structlog.get_logger()


def _chunk_list(items: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of chunk_size."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


async def _process_chunk(
    items: list,
    processor,
    concurrency: int,
    job_name: str,
) -> dict:
    """Process items concurrently with error isolation."""
    sem = asyncio.Semaphore(concurrency)
    results = {"succeeded": 0, "failed": 0}

    logger.info("chunk.started", extra={
        "feature": "arq_batch", "action": job_name,
        "detail": {"chunk_size": len(items)},
    })

    async def _run(item_id):
        async with sem:
            try:
                await processor(item_id)
                results["succeeded"] += 1
            except Exception as e:
                results["failed"] += 1
                logger.error("chunk.item_failed", extra={
                    "feature": "arq_batch",
                    "action": job_name,
                    "item_id": str(item_id),
                    "status": "failure",
                    "detail": {"error": str(e), "type": type(e).__name__},
                })

    await asyncio.gather(*[_run(item) for item in items], return_exceptions=True)
    logger.info("chunk.complete", extra={
        "feature": "arq_batch",
        "action": job_name,
        "detail": results,
    })
    return results
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_worker_batching.py -xvs`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add app/config.py app/worker.py tests/test_worker_batching.py
git commit -m "feat(arq): add chunking utilities and error-isolated processing"
```

---

### Task 5.2: Refactor Cron Jobs to Coordinator Pattern

**Files:**
- Modify: `app/worker.py`

- [ ] **Step 1: Write test for coordinator pattern**

Add to `tests/test_worker_batching.py`:

```python
@pytest.mark.asyncio
async def test_coordinator_acquires_lock(redis_client):
    """Coordinator acquires a run lock and skips if already held."""
    from app.worker import _acquire_run_lock
    assert await _acquire_run_lock("test_job", ttl=60) is True
    assert await _acquire_run_lock("test_job", ttl=60) is False  # Already held


@pytest.mark.asyncio
async def test_coordinator_caps_items(redis_client):
    """Coordinator respects MAX_CHUNKS_PER_RUN."""
    from app.worker import _chunk_list
    from app.config import settings

    items = list(range(600))  # More than MAX_CHUNKS_PER_RUN * CHUNK_SIZE
    max_items = settings.ARQ_MAX_CHUNKS_PER_RUN * settings.ARQ_CHUNK_SIZE
    capped = items[:max_items]
    chunks = _chunk_list(capped, settings.ARQ_CHUNK_SIZE)
    assert len(chunks) <= settings.ARQ_MAX_CHUNKS_PER_RUN
```

- [ ] **Step 2: Add run lock helper**

In `app/worker.py`, add:

```python
async def _acquire_run_lock(job_name: str, ttl: int) -> bool:
    """Acquire a Redis-based run lock for cron deduplication."""
    from app.infrastructure.redis_client import get_redis
    redis = get_redis()
    lock_key = f"lock:cron:{job_name}"
    return await redis.set(lock_key, "1", nx=True, ex=ttl)
```

- [ ] **Step 3: Refactor check_followup_due to coordinator pattern**

Refactor `check_followup_due` (lines 48-157) into:

1. `check_followup_due(ctx)` — coordinator: acquire lock, query due follow-ups, cap at `MAX_CHUNKS_PER_RUN * CHUNK_SIZE` items (log `cron.overflow` with `total_items`, `processing`, `deferred` counts if items exceed cap), chunk IDs, enqueue `process_followup_chunk` per chunk, log `cron.started` with items found and chunks enqueued
2. `process_followup_chunk(ctx, message_ids: list[str])` — worker: process each message with the existing per-message logic (dedup checks + outreach graph), using `_process_chunk` for concurrency

The per-message processing logic from the current function body moves into a `_process_single_followup(message_id)` async function called by the chunk processor.

- [ ] **Step 4: Refactor run_daily_scout to coordinator pattern**

Same pattern:
1. `run_daily_scout(ctx)` — coordinator: lock `daily_scout` (TTL 82800), query candidates, chunk, enqueue
2. `process_scout_chunk(ctx, candidate_ids: list[str])` — worker: run scout pipeline per candidate with concurrency

- [ ] **Step 5: Refactor run_weekly_analytics to coordinator pattern**

Same pattern:
1. `run_weekly_analytics(ctx)` — coordinator: lock `weekly_analytics` (TTL 590400), query candidates, chunk, enqueue
2. `process_analytics_chunk(ctx, candidate_ids: list[str])` — worker: run analytics pipeline per candidate with concurrency

- [ ] **Step 6: Register new functions in WorkerSettings**

Update `WorkerSettings` at the bottom of `app/worker.py`:

```python
class WorkerSettings:
    functions = [
        send_approved_message,
        func(process_followup_chunk, timeout=600),
        func(process_scout_chunk, timeout=600),
        func(process_analytics_chunk, timeout=600),
    ]
    cron_jobs = [
        cron(check_followup_due, minute={0, 15, 30, 45}),
        cron(expire_stale_actions, hour={3}, minute={0}),
        cron(run_daily_scout, hour={9}, minute={0}),
        cron(run_weekly_analytics, weekday={0}, hour={8}, minute={0}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = None  # Set dynamically
```

- [ ] **Step 7: Run full test suite**

Run: `cd jobhunter/backend && uv run python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add app/worker.py tests/test_worker_batching.py
git commit -m "feat(arq): refactor cron jobs to coordinator + chunk pattern"
```

---

## Chunk 6: Final Integration and Cleanup

### Task 6.1: Full Test Suite and Linting

- [ ] **Step 1: Run full backend test suite**

Run: `cd jobhunter/backend && uv run python -m pytest tests/ -x -q --tb=short`
Expected: All tests pass

- [ ] **Step 2: Run linters**

Run: `cd jobhunter/backend && uv run ruff check app/ && uv run ruff format --check app/`
Expected: No errors

- [ ] **Step 3: Build frontend**

Run: `cd jobhunter/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Run frontend tests**

Run: `cd jobhunter/frontend && npm run test`
Expected: All tests pass

- [ ] **Step 5: Verify .env.example is up to date**

Check that `backend/.env.example` includes all new env vars:
- `PGBOUNCER_URL`
- `MAX_DAILY_INVITES`
- `DKIM_SELECTOR`
- `SPF_EXPECTED_INCLUDES`
- `DNS_HEALTH_CACHE_TTL`
- `DNS_LOOKUP_TIMEOUT`
- `DOSSIER_CACHE_TTL`
- `ARQ_CHUNK_SIZE`
- `ARQ_CHUNK_CONCURRENCY`
- `ARQ_MAX_CHUNKS_PER_RUN`

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: P1 improvements integration cleanup"
```

---

## Deployment Order and Rollback

Per the spec, the recommended deployment sequence (lowest risk first):

1. **Feature 3 (pgBouncer)** — infrastructure only, zero app code risk
2. **Feature 2 (DNS Health)** — read-only, low risk
3. **Feature 4 (Dossier Caching)** — cost savings start immediately
4. **Feature 5 (Batch ARQ)** — scalability improvement
5. **Feature 1 (Waitlist Invites)** — user-facing, deploy last to allow soak time on infra changes

**Rollback procedures:**

| Feature | Rollback |
|---------|----------|
| 1 - Waitlist Invites | Migration is additive (new columns with defaults) — backward-compatible. Revert API deploy; old code ignores new columns. |
| 2 - DNS Health | Remove endpoint + frontend card. No data changes. |
| 3 - pgBouncer | Unset `PGBOUNCER_URL`, restart app. Falls back to direct connection. |
| 4 - Dossier Caching | Revert to previous `company_service.py`. Cache keys in Redis expire naturally via TTL. |
| 5 - Batch ARQ | Revert `worker.py`. Crons fall back to sequential processing. |

**Security note:** All admin endpoints (`/api/v1/admin/*`) are protected by the existing `require_admin` dependency which validates JWT tokens and checks the user's `is_admin` flag. No changes needed.
