# Incident Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Authenticated users can submit categorized incidents (bug/feature/question/other) with screenshots from a floating button on all dashboard pages, persisted to DB and synced to GitHub Issues.

**Architecture:** New backend domain (model → schema → service → router) following existing patterns. GitHub API integration via Protocol-based `httpx` client. Frontend floating button opens a Sheet with categorized form. Images uploaded to R2 via existing StorageProtocol. Failed GitHub syncs retried via ARQ cron.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, httpx (GitHub API), Alembic, React, TanStack Query, shadcn/ui Sheet, Sonner toasts

**Spec:** `docs/superpowers/specs/2026-04-12-incident-submission-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `app/models/incident.py` | Incident ORM model |
| Modify | `app/models/__init__.py` | Export Incident |
| Modify | `app/models/enums.py` | Add IncidentCategory, GitHubSyncStatus |
| Create | `app/schemas/incident.py` | Request/response Pydantic schemas |
| Create | `app/infrastructure/github_client.py` | GitHub Issues API client (Protocol-based) |
| Modify | `app/infrastructure/protocols.py` | Add GitHubClientProtocol |
| Modify | `app/dependencies.py` | Add get_github singleton |
| Modify | `app/config.py` | GITHUB_TOKEN, GITHUB_REPO settings |
| Create | `app/services/incident_service.py` | Create incident, upload images, sync to GitHub |
| Create | `app/api/incidents.py` | POST /incidents, GET /incidents (admin) |
| Modify | `app/main.py` | Register incidents router |
| Modify | `app/worker.py` | Add retry_failed_github_syncs cron |
| Create | `alembic/versions/024_add_incidents.py` | Migration |
| Modify | `backend/.env.example` | GITHUB_TOKEN, GITHUB_REPO |
| Create | `tests/test_incidents.py` | Backend tests |
| Modify | `tests/conftest.py` | Add GitHubStub |
| Create | `src/components/incidents/incident-button.tsx` | Floating button |
| Create | `src/components/incidents/incident-form.tsx` | Sheet form with category, attachments |
| Create | `src/lib/api/incidents.ts` | API module |
| Create | `src/lib/hooks/use-incidents.ts` | useMutation hook |
| Modify | `src/lib/types.ts` | IncidentResponse type |
| Modify | `src/app/(dashboard)/layout.tsx` | Mount button + console error capture |
| Modify | `src/components/admin/overview-stats.tsx` | Incident count card |

---

### Task 1: Enums and Model

**Files:**
- Modify: `jobhunter/backend/app/models/enums.py`
- Create: `jobhunter/backend/app/models/incident.py`
- Modify: `jobhunter/backend/app/models/__init__.py`

- [ ] **Step 1: Add enums**

Add to the end of `app/models/enums.py`:

```python
# ── Incidents ────────────────────────────────────────────────────────

class IncidentCategory(StrEnum):
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    QUESTION = "question"
    OTHER = "other"

class GitHubSyncStatus(StrEnum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
```

- [ ] **Step 2: Create Incident model**

Create `app/models/incident.py`:

```python
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Incident(TimestampMixin, Base):
    __tablename__ = "incidents"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB)
    attachments: Mapped[list | None] = mapped_column(JSONB)
    github_issue_number: Mapped[int | None] = mapped_column(Integer)
    github_issue_url: Mapped[str | None] = mapped_column(String(500))
    github_status: Mapped[str] = mapped_column(String(20), default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    candidate: Mapped["Candidate"] = relationship()
```

- [ ] **Step 3: Export in `__init__.py`**

Add to `app/models/__init__.py`:

```python
from app.models.incident import Incident
```

And add `"Incident"` to the `__all__` list (alphabetical order, after `"InviteCode"`).

- [ ] **Step 4: Verify import works**

Run: `cd jobhunter/backend && uv run python -c "from app.models import Incident; print(Incident.__tablename__)"`
Expected: `incidents`

- [ ] **Step 5: Commit**

```bash
cd jobhunter/backend && git add app/models/enums.py app/models/incident.py app/models/__init__.py
git commit -m "feat(incidents): add Incident model and enums

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Alembic Migration

**Files:**
- Create: `jobhunter/backend/alembic/versions/024_add_incidents.py`

- [ ] **Step 1: Generate migration**

Run: `cd jobhunter/backend && uv run alembic revision --autogenerate -m "add incidents"`

This should detect the new `incidents` table from the model.

- [ ] **Step 2: Review generated migration**

Read the generated file and verify it creates the `incidents` table with all columns: `id`, `candidate_id` (FK), `category`, `title`, `description`, `context` (JSONB), `attachments` (JSONB), `github_issue_number`, `github_issue_url`, `github_status`, `retry_count`, `created_at`, `updated_at`. Verify the `downgrade()` drops the table.

If the auto-generated migration is missing anything, manually adjust. Rename the file to `024_add_incidents.py` for consistency with the existing numbering.

- [ ] **Step 3: Test migration runs**

Run: `cd jobhunter/backend && uv run alembic upgrade head`
Expected: migration applies without errors.

- [ ] **Step 4: Commit**

```bash
cd jobhunter/backend && git add alembic/versions/
git commit -m "feat(incidents): add incidents table migration

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Schemas

**Files:**
- Create: `jobhunter/backend/app/schemas/incident.py`

- [ ] **Step 1: Create schemas**

```python
from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    category: str = Field(..., pattern="^(bug|feature_request|question|other)$")
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    context: dict | None = None


class IncidentResponse(BaseModel):
    id: str
    category: str
    title: str
    github_issue_url: str | None = None
    github_status: str
    created_at: str
    model_config = {"from_attributes": True}


class IncidentAdminResponse(BaseModel):
    id: str
    candidate_email: str
    category: str
    title: str
    description: str
    github_issue_url: str | None = None
    github_issue_number: int | None = None
    github_status: str
    retry_count: int
    created_at: str
    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    items: list[IncidentAdminResponse]
    total: int
    page: int
    per_page: int
```

- [ ] **Step 2: Verify import**

Run: `cd jobhunter/backend && uv run python -c "from app.schemas.incident import IncidentCreate; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd jobhunter/backend && git add app/schemas/incident.py
git commit -m "feat(incidents): add incident Pydantic schemas

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: GitHub Client (Protocol + Implementation)

**Files:**
- Modify: `jobhunter/backend/app/infrastructure/protocols.py`
- Create: `jobhunter/backend/app/infrastructure/github_client.py`
- Modify: `jobhunter/backend/app/dependencies.py`
- Modify: `jobhunter/backend/app/config.py`
- Modify: `jobhunter/backend/backend/.env.example`

- [ ] **Step 1: Add Protocol**

Add to the end of `app/infrastructure/protocols.py`:

```python
@runtime_checkable
class GitHubClientProtocol(Protocol):
    async def create_issue(self, title: str, body: str, labels: list[str]) -> dict: ...
```

- [ ] **Step 2: Add config settings**

Add to `app/config.py` Settings class (before `model_config`):

```python
    # GitHub (incident sync)
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = "EranDaniel98/jobhunter"
```

- [ ] **Step 3: Update .env.example**

Add to `backend/.env.example`:

```
# GitHub (incident sync to GitHub Issues)
GITHUB_TOKEN=ghp_your_fine_grained_pat_here
GITHUB_REPO=EranDaniel98/jobhunter
```

- [ ] **Step 4: Create GitHub client**

Create `app/infrastructure/github_client.py`:

```python
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class GitHubClient:
    def __init__(self) -> None:
        self._base_url = f"https://api.github.com/repos/{settings.GITHUB_REPO}"
        self._headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/issues",
                headers=self._headers,
                json={"title": title, "body": body, "labels": labels},
            )
            response.raise_for_status()
            data = response.json()
            logger.info("github_issue_created", number=data["number"], url=data["html_url"])
            return {"number": data["number"], "url": data["html_url"]}
```

- [ ] **Step 5: Add dependency singleton**

Add to `app/dependencies.py` (following the existing pattern):

```python
from app.infrastructure.protocols import GitHubClientProtocol

_github_client: GitHubClientProtocol | None = None

def get_github() -> GitHubClientProtocol:
    global _github_client
    if _github_client is None:
        from app.infrastructure.github_client import GitHubClient
        _github_client = GitHubClient()
    return _github_client
```

- [ ] **Step 6: Verify import chain**

Run: `cd jobhunter/backend && uv run python -c "from app.dependencies import get_github; print(type(get_github()))"`
Expected: `<class 'app.infrastructure.github_client.GitHubClient'>`

- [ ] **Step 7: Commit**

```bash
cd jobhunter/backend && git add app/infrastructure/protocols.py app/infrastructure/github_client.py app/dependencies.py app/config.py .env.example
git commit -m "feat(incidents): add GitHub Issues API client with Protocol

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Incident Service

**Files:**
- Create: `jobhunter/backend/app/services/incident_service.py`

- [ ] **Step 1: Create the service**

```python
import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.protocols import GitHubClientProtocol, StorageProtocol
from app.models.candidate import Candidate
from app.models.enums import GitHubSyncStatus, IncidentCategory
from app.models.incident import Incident

logger = structlog.get_logger()

CATEGORY_LABELS = {
    IncidentCategory.BUG: "bug",
    IncidentCategory.FEATURE_REQUEST: "enhancement",
    IncidentCategory.QUESTION: "question",
    IncidentCategory.OTHER: "incident",
}


def _build_issue_body(incident: Incident) -> str:
    ctx = incident.context or {}
    attachments_md = "None"
    if incident.attachments:
        attachments_md = "\n".join(
            f"![{a['filename']}]({a['url']})" for a in incident.attachments
        )

    console_errors = ctx.get("console_errors") or "None"
    if isinstance(console_errors, list):
        console_errors = "\n".join(console_errors) if console_errors else "None"

    return f"""## Description

{incident.description}

## Attachments

{attachments_md}

## Context

| Field | Value |
|-------|-------|
| User | {ctx.get('email', 'N/A')} |
| Plan | {ctx.get('plan_tier', 'N/A')} |
| Page | {ctx.get('page_url', 'N/A')} |
| Browser | {ctx.get('browser', 'N/A')} |
| OS | {ctx.get('os', 'N/A')} |
| Submitted | {incident.created_at} |
| Incident ID | {incident.id} |

## Console Errors

```
{console_errors}
```"""


async def create_incident(
    db: AsyncSession,
    candidate: Candidate,
    category: str,
    title: str,
    description: str,
    context: dict | None,
    files: list[tuple[str, bytes, str]],
    storage: StorageProtocol,
    github: GitHubClientProtocol,
) -> Incident:
    incident_id = uuid.uuid4()

    # Upload attachments
    attachments = []
    for filename, data, content_type in files:
        key = f"incidents/{incident_id}/{filename}"
        url = await storage.upload(key, data, content_type)
        attachments.append({
            "filename": filename,
            "url": url,
            "size_bytes": len(data),
            "content_type": content_type,
        })

    incident = Incident(
        id=incident_id,
        candidate_id=candidate.id,
        category=category,
        title=title,
        description=description,
        context=context,
        attachments=attachments or None,
        github_status=GitHubSyncStatus.PENDING,
        retry_count=0,
    )
    db.add(incident)
    await db.flush()

    # Sync to GitHub
    await _sync_to_github(incident, github)

    await db.commit()
    await db.refresh(incident)
    return incident


async def _sync_to_github(incident: Incident, github: GitHubClientProtocol) -> None:
    try:
        label = CATEGORY_LABELS.get(incident.category, "incident")
        body = _build_issue_body(incident)
        result = await github.create_issue(
            title=f"[{incident.category}] {incident.title}",
            body=body,
            labels=[label],
        )
        incident.github_issue_number = result["number"]
        incident.github_issue_url = result["url"]
        incident.github_status = GitHubSyncStatus.SYNCED
    except Exception:
        logger.exception("github_sync_failed", incident_id=str(incident.id))
        incident.github_status = GitHubSyncStatus.FAILED


async def retry_failed_syncs(db: AsyncSession, github: GitHubClientProtocol) -> int:
    result = await db.execute(
        select(Incident).where(
            Incident.github_status == GitHubSyncStatus.FAILED,
            Incident.retry_count < 5,
        )
    )
    incidents = result.scalars().all()
    retried = 0
    for incident in incidents:
        incident.retry_count += 1
        await _sync_to_github(incident, github)
        retried += 1
    await db.commit()
    return retried


async def list_incidents(
    db: AsyncSession, page: int = 1, per_page: int = 20,
    github_status: str | None = None, category: str | None = None,
) -> tuple[list, int]:
    query = select(Incident).join(Candidate)
    count_query = select(func.count(Incident.id))

    if github_status:
        query = query.where(Incident.github_status == github_status)
        count_query = count_query.where(Incident.github_status == github_status)
    if category:
        query = query.where(Incident.category == category)
        count_query = count_query.where(Incident.category == category)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Incident.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return result.scalars().all(), total


async def get_incident_count(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count(Incident.id)))).scalar() or 0
    failed = (await db.execute(
        select(func.count(Incident.id)).where(Incident.github_status == GitHubSyncStatus.FAILED)
    )).scalar() or 0
    return {"total": total, "failed": failed}
```

- [ ] **Step 2: Verify import**

Run: `cd jobhunter/backend && uv run python -c "from app.services.incident_service import create_incident; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd jobhunter/backend && git add app/services/incident_service.py
git commit -m "feat(incidents): add incident service with GitHub sync and retry

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Router

**Files:**
- Create: `jobhunter/backend/app/api/incidents.py`
- Modify: `jobhunter/backend/app/main.py`

- [ ] **Step 1: Create the router**

```python
import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin, get_current_candidate, get_db, get_github
from app.infrastructure.protocols import GitHubClientProtocol, StorageProtocol
from app.infrastructure.storage import get_storage
from app.models.candidate import Candidate
from app.rate_limit import limiter
from app.schemas.incident import IncidentCreate, IncidentListResponse, IncidentAdminResponse, IncidentResponse
from app.services import incident_service

router = APIRouter(prefix="/incidents", tags=["incidents"])
logger = structlog.get_logger()

MAX_FILES = 3
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("", response_model=IncidentResponse, status_code=201)
@limiter.limit("3/hour")
async def submit_incident(
    request: Request,
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    context: str = Form("{}"),
    files: list[UploadFile] = File(default=[]),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
    github: GitHubClientProtocol = Depends(get_github),
):
    # Validate category
    if category not in ("bug", "feature_request", "question", "other"):
        raise HTTPException(status_code=400, detail="Invalid category")
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="Title too long (max 200)")
    if len(description) > 5000:
        raise HTTPException(status_code=400, detail="Description too long (max 5000)")

    # Parse context JSON
    try:
        context_data = json.loads(context)
    except json.JSONDecodeError:
        context_data = {}

    # Validate and read files
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Max {MAX_FILES} files allowed")

    file_tuples: list[tuple[str, bytes, str]] = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"File {f.filename} is not an image")
        data = await f.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {f.filename} too large (max 5MB)")
        file_tuples.append((f.filename or "image", data, f.content_type))

    storage: StorageProtocol = get_storage()
    incident = await incident_service.create_incident(
        db=db,
        candidate=candidate,
        category=category,
        title=title,
        description=description,
        context=context_data,
        files=file_tuples,
        storage=storage,
        github=github,
    )

    return IncidentResponse(
        id=str(incident.id),
        category=incident.category,
        title=incident.title,
        github_issue_url=incident.github_issue_url,
        github_status=incident.github_status,
        created_at=str(incident.created_at),
    )


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    github_status: str | None = Query(None),
    category: str | None = Query(None),
    candidate: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await incident_service.list_incidents(
        db=db, page=page, per_page=per_page,
        github_status=github_status, category=category,
    )
    return IncidentListResponse(
        items=[
            IncidentAdminResponse(
                id=str(i.id),
                candidate_email=i.candidate.email,
                category=i.category,
                title=i.title,
                description=i.description,
                github_issue_url=i.github_issue_url,
                github_issue_number=i.github_issue_number,
                github_status=i.github_status,
                retry_count=i.retry_count,
                created_at=str(i.created_at),
            )
            for i in items
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats")
async def incident_stats(
    candidate: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await incident_service.get_incident_count(db)
```

- [ ] **Step 2: Register router in main.py**

Add import and `include_router` to `app/main.py`:

```python
from app.api.incidents import router as incidents_router  # noqa: E402
```

And:

```python
app.include_router(incidents_router, prefix=settings.API_V1_PREFIX)
```

Add both after the existing `waitlist_router` lines.

- [ ] **Step 3: Verify server starts**

Run: `cd jobhunter/backend && uv run python -c "from app.main import app; print([r.path for r in app.routes if 'incident' in r.path])"`
Expected: list containing `/api/v1/incidents` paths

- [ ] **Step 4: Commit**

```bash
cd jobhunter/backend && git add app/api/incidents.py app/main.py
git commit -m "feat(incidents): add incidents router (POST submit + GET admin list)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: ARQ Retry Cron

**Files:**
- Modify: `jobhunter/backend/app/worker.py`

- [ ] **Step 1: Add the retry function**

Add above `WorkerSettings`:

```python
async def retry_failed_github_syncs(ctx: dict) -> None:
    """Retry incidents that failed to sync to GitHub Issues."""
    from app.dependencies import get_github
    from app.services.incident_service import retry_failed_syncs

    lock_key = "lock:cron:retry_github_syncs"
    lock = await _acquire_run_lock(ctx["redis"], lock_key, ttl=300)
    if not lock:
        return

    try:
        async with get_session() as db:
            retried = await retry_failed_syncs(db, get_github())
            if retried:
                logger.info("github_sync_retried", count=retried)
    finally:
        await ctx["redis"].delete(lock_key)
```

- [ ] **Step 2: Add to cron schedule**

Add to `WorkerSettings.cron_jobs`:

```python
        cron(retry_failed_github_syncs, minute={5, 20, 35, 50}),  # Every 15 min (offset from followups)
```

- [ ] **Step 3: Verify worker parses**

Run: `cd jobhunter/backend && uv run python -c "from app.worker import WorkerSettings; print(len(WorkerSettings.cron_jobs), 'cron jobs')"`
Expected: `5 cron jobs` (was 4, now 5)

- [ ] **Step 4: Commit**

```bash
cd jobhunter/backend && git add app/worker.py
git commit -m "feat(incidents): add ARQ cron to retry failed GitHub syncs

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Backend Tests

**Files:**
- Create: `jobhunter/backend/tests/test_incidents.py`
- Modify: `jobhunter/backend/tests/conftest.py`

- [ ] **Step 1: Add GitHubStub to conftest.py**

Add the stub class (near the other stubs):

```python
class GitHubStub:
    """Stub for GitHubClientProtocol."""
    def __init__(self):
        self.created_issues = []

    async def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        issue = {"number": len(self.created_issues) + 1, "url": f"https://github.com/test/repo/issues/{len(self.created_issues) + 1}"}
        self.created_issues.append({"title": title, "body": body, "labels": labels})
        return issue
```

Add to the `client` fixture setup (alongside the other stub injections):

```python
    _deps._github_client = GitHubStub()
```

And in the cleanup:

```python
    _deps._github_client = None
```

- [ ] **Step 2: Write tests**

Create `tests/test_incidents.py`:

```python
import pytest


@pytest.fixture
async def auth_headers_for_incidents(client, invite_code):
    """Register and login a user, return auth headers."""
    await client.post("/api/v1/auth/register", json={
        "email": "incident_user@test.com",
        "password": "TestPass123!",
        "full_name": "Incident User",
        "invite_code": invite_code,
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "incident_user@test.com",
        "password": "TestPass123!",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_submit_incident_success(client, auth_headers_for_incidents):
    resp = await client.post(
        "/api/v1/incidents",
        data={
            "category": "bug",
            "title": "Button does not work",
            "description": "The submit button on the dashboard is unresponsive.",
            "context": '{"email":"incident_user@test.com","plan_tier":"free"}',
        },
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "bug"
    assert body["title"] == "Button does not work"
    assert body["github_status"] == "synced"
    assert body["github_issue_url"] is not None


async def test_submit_incident_invalid_category(client, auth_headers_for_incidents):
    resp = await client.post(
        "/api/v1/incidents",
        data={
            "category": "invalid",
            "title": "Test",
            "description": "Test",
        },
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 400


async def test_submit_incident_title_too_long(client, auth_headers_for_incidents):
    resp = await client.post(
        "/api/v1/incidents",
        data={
            "category": "bug",
            "title": "x" * 201,
            "description": "Test",
        },
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 400


async def test_submit_incident_unauthenticated(client):
    resp = await client.post(
        "/api/v1/incidents",
        data={
            "category": "bug",
            "title": "Test",
            "description": "Test",
        },
    )
    assert resp.status_code == 403 or resp.status_code == 401


async def test_list_incidents_admin_only(client, auth_headers_for_incidents):
    # Non-admin should get 403
    resp = await client.get(
        "/api/v1/incidents",
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 403


async def test_incident_stats_admin_only(client, auth_headers_for_incidents):
    resp = await client.get(
        "/api/v1/incidents/stats",
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 403
```

- [ ] **Step 3: Run tests**

Run: `cd jobhunter/backend && uv run pytest tests/test_incidents.py -v`
Expected: all 6 tests pass

- [ ] **Step 4: Commit**

```bash
cd jobhunter/backend && git add tests/test_incidents.py tests/conftest.py
git commit -m "test(incidents): add incident submission tests with GitHubStub

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Frontend Types + API Module

**Files:**
- Modify: `jobhunter/frontend/src/lib/types.ts`
- Create: `jobhunter/frontend/src/lib/api/incidents.ts`
- Create: `jobhunter/frontend/src/lib/hooks/use-incidents.ts`

- [ ] **Step 1: Add types**

Add to `src/lib/types.ts` (before the closing DNS section):

```typescript
// Incidents
export type IncidentCategory = "bug" | "feature_request" | "question" | "other";

export interface IncidentResponse {
  id: string;
  category: IncidentCategory;
  title: string;
  github_issue_url: string | null;
  github_status: "pending" | "synced" | "failed";
  created_at: string;
}

export interface IncidentStats {
  total: number;
  failed: number;
}
```

- [ ] **Step 2: Create API module**

Create `src/lib/api/incidents.ts`:

```typescript
import api from "./client";
import type { IncidentResponse, IncidentStats } from "../types";

export async function submitIncident(formData: FormData): Promise<IncidentResponse> {
  const { data } = await api.post<IncidentResponse>("/incidents", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getIncidentStats(): Promise<IncidentStats> {
  const { data } = await api.get<IncidentStats>("/incidents/stats");
  return data;
}
```

- [ ] **Step 3: Create hook**

Create `src/lib/hooks/use-incidents.ts`:

```typescript
"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import * as incidentsApi from "@/lib/api/incidents";
import { toastError } from "@/lib/api/error-utils";
import { toast } from "sonner";

export function useSubmitIncident() {
  return useMutation({
    mutationFn: incidentsApi.submitIncident,
    onSuccess: (data) => {
      if (data.github_issue_url) {
        toast.success("Incident submitted", {
          description: "A GitHub issue has been created.",
          action: {
            label: "View",
            onClick: () => window.open(data.github_issue_url!, "_blank"),
          },
        });
      } else {
        toast.success("Incident submitted", {
          description: "We'll look into it shortly.",
        });
      }
    },
    onError: (err: unknown) => {
      toastError(err, "Failed to submit incident");
    },
  });
}

export function useIncidentStats() {
  return useQuery({
    queryKey: ["incident-stats"],
    queryFn: incidentsApi.getIncidentStats,
  });
}
```

- [ ] **Step 4: Commit**

```bash
cd jobhunter/frontend && git add src/lib/types.ts src/lib/api/incidents.ts src/lib/hooks/use-incidents.ts
git commit -m "feat(incidents): add frontend types, API module, and mutation hook

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Incident Form Component

**Files:**
- Create: `jobhunter/frontend/src/components/incidents/incident-form.tsx`

- [ ] **Step 1: Create the form component**

Create `src/components/incidents/incident-form.tsx`. This is a Sheet that opens from the right side. It contains:

1. Category radio group (4 options)
2. Title input (max 200)
3. Description textarea (max 5000, placeholder adapts per category)
4. Image dropzone (max 3, max 5MB each, image/* only) with thumbnails + remove
5. Submit button with loading state

The form collects auto-context (`email`, `plan_tier` from `useAuth()`, `page_url` from `window.location.href`, `browser` and `os` parsed from `navigator.userAgent`, and `console_errors` from a ref passed as prop).

On submit: builds a `FormData` with category, title, description, context (JSON string), and files. Calls `useSubmitIncident()`. On success: closes sheet, resets form. On failure: stays open.

Use `Sheet`, `SheetContent`, `SheetHeader`, `SheetTitle` from shadcn/ui. `Input`, `Textarea`, `Button`, `Label` from shadcn/ui. `RadioGroup`, `RadioGroupItem` from shadcn/ui (add via `npx shadcn@latest add radio-group --yes` if not present). Icons from Lucide.

The component should be ~150-200 lines. Keep it focused — no data fetching beyond the mutation.

**Props interface:**

```typescript
interface IncidentFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  consoleErrors: React.RefObject<string[]>;
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep -i incident || echo "no errors"`

- [ ] **Step 3: Commit**

```bash
cd jobhunter/frontend && git add src/components/incidents/
git commit -m "feat(incidents): add incident submission form Sheet component

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Floating Button + Dashboard Layout Integration

**Files:**
- Create: `jobhunter/frontend/src/components/incidents/incident-button.tsx`
- Modify: `jobhunter/frontend/src/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Create floating button**

Create `src/components/incidents/incident-button.tsx`:

```tsx
"use client";

import { useState, useRef } from "react";
import { MessageSquarePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { IncidentForm } from "./incident-form";

interface IncidentButtonProps {
  consoleErrors: React.RefObject<string[]>;
}

export function IncidentButton({ consoleErrors }: IncidentButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="default"
        size="icon"
        className="fixed bottom-6 right-6 z-40 h-12 w-12 rounded-full shadow-lg"
        onClick={() => setOpen(true)}
        aria-label="Report an incident"
      >
        <MessageSquarePlus className="h-5 w-5" />
      </Button>
      <IncidentForm open={open} onOpenChange={setOpen} consoleErrors={consoleErrors} />
    </>
  );
}
```

- [ ] **Step 2: Modify dashboard layout**

In `src/app/(dashboard)/layout.tsx`:

Add imports:
```typescript
import { useRef, useEffect } from "react";  // add useRef if not already imported
import { IncidentButton } from "@/components/incidents/incident-button";
```

Add console error capture ref inside `DashboardLayout`:
```typescript
  const consoleErrorsRef = useRef<string[]>([]);

  useEffect(() => {
    const originalError = console.error;
    console.error = (...args: unknown[]) => {
      const message = args.map(a => typeof a === 'string' ? a : JSON.stringify(a)).join(' ');
      const errors = consoleErrorsRef.current;
      errors.push(message);
      if (errors.length > 10) errors.shift();
      originalError.apply(console, args);
    };
    return () => { console.error = originalError; };
  }, []);
```

Add `<IncidentButton>` inside the return JSX, after `<TourOverlay />`:
```tsx
      <IncidentButton consoleErrors={consoleErrorsRef} />
```

- [ ] **Step 3: Verify it compiles**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep -i error | head -5 || echo "clean"`

- [ ] **Step 4: Commit**

```bash
cd jobhunter/frontend && git add src/components/incidents/incident-button.tsx src/app/\(dashboard\)/layout.tsx
git commit -m "feat(incidents): add floating incident button to dashboard layout

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Admin Overview Incident Card

**Files:**
- Modify: `jobhunter/frontend/src/components/admin/overview-stats.tsx`
- Modify: `jobhunter/frontend/src/lib/types.ts` (if SystemOverview needs updating)

- [ ] **Step 1: Add incident stats to admin overview**

Modify `src/components/admin/overview-stats.tsx`:

Add import:
```typescript
import { AlertTriangle } from "lucide-react";
import { useIncidentStats } from "@/lib/hooks/use-incidents";
```

Inside the component, fetch incident stats:
```typescript
  const { data: incidentStats } = useIncidentStats();
```

Add a 5th card to the `cards` array:
```typescript
    {
      title: "Incidents",
      value: incidentStats?.total ?? 0,
      subtitle: incidentStats?.failed ? `${incidentStats.failed} failed sync` : undefined,
      icon: AlertTriangle,
      href: "https://github.com/EranDaniel98/jobhunter/issues",
    },
```

Make the card clickable by wrapping it in an `<a>` tag when `href` is present. Add `href?: string` to the card type.

- [ ] **Step 2: Verify it compiles**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep -i error | head -5 || echo "clean"`

- [ ] **Step 3: Commit**

```bash
cd jobhunter/frontend && git add src/components/admin/overview-stats.tsx
git commit -m "feat(incidents): add incident count card to admin overview

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Manual E2E Verification + .env.example

**Files:**
- Modify: `jobhunter/backend/.env.example`

- [ ] **Step 1: Ensure .env.example has the new vars**

Verify `backend/.env.example` has:
```
GITHUB_TOKEN=ghp_your_fine_grained_pat_here
GITHUB_REPO=EranDaniel98/jobhunter
```

(This was done in Task 4 but verify it survived all commits.)

- [ ] **Step 2: Ensure GitHub labels exist**

Run (one-time setup):
```bash
gh label create "question" --repo EranDaniel98/jobhunter --color "d876e3" --description "User question" 2>/dev/null || true
gh label create "incident" --repo EranDaniel98/jobhunter --color "e4e669" --description "User-reported incident" 2>/dev/null || true
```

- [ ] **Step 3: Start dev servers and test manually**

1. Start backend: `cd jobhunter/backend && uv run uvicorn app.main:app --reload`
2. Start frontend: `cd jobhunter/frontend && npm run dev`
3. Login, verify floating button appears bottom-right on dashboard
4. Click button, verify Sheet opens with category/title/description/attachment fields
5. Submit a test bug report, verify toast appears with GitHub link
6. Check GitHub Issues — verify the issue was created with correct title, body, labels

- [ ] **Step 4: Final commit if any adjustments needed**

```bash
git add -A && git commit -m "fix(incidents): post-E2E adjustments

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Execution Order

Tasks are mostly sequential due to build-on dependencies:

1. **Task 1** — Enums + Model (foundation)
2. **Task 2** — Migration (needs model)
3. **Task 3** — Schemas (needs enums)
4. **Task 4** — GitHub client (needs config, protocols)
5. **Task 5** — Service (needs model, schemas, GitHub client, storage)
6. **Task 6** — Router (needs service, schemas)
7. **Task 7** — ARQ retry (needs service)
8. **Task 8** — Tests (needs all backend)
9. **Task 9** — Frontend types + API + hook (independent of backend order, but needs API to exist)
10. **Task 10** — Form component (needs hook)
11. **Task 11** — Floating button + layout (needs form)
12. **Task 12** — Admin card (needs hook)
13. **Task 13** — E2E verification (needs everything)

**Parallelizable:** Tasks 9-12 (frontend) can start after Task 6 (router) is done. Tasks 7-8 can run in parallel with Tasks 9-12.
