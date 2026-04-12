# Incident Submission Feature — Design Spec

**Date:** 2026-04-12
**Status:** Approved
**Scope:** Backend (new router, service, model, infra client) + Frontend (floating button, sheet form) + GitHub Issues integration

---

## Problem

Users have no way to report bugs, request features, or ask questions from within the app. The only support touchpoint is a `mailto:` link in the marketing footer. Incidents need to reach the GitHub repo (private, single-developer) for triage, while also being persisted locally for reliability.

## Goals

1. Authenticated users can submit categorized incidents (bug, feature request, question, other) with title, description, and up to 3 screenshot attachments
2. Incidents are saved to the database first (guaranteed persistence), then synced to GitHub Issues with rich context
3. Failed GitHub syncs are retried automatically via ARQ cron
4. Admin sees incident count on the overview dashboard; manages incidents on GitHub
5. Floating button on all dashboard pages — always discoverable, opens a side sheet

## Non-Goals

- Anonymous/unauthenticated submission
- In-app incident management UI (GitHub is the triage tool)
- Email notifications (GitHub notifies repo watchers)
- Status updates pushed back to users (they get the GitHub issue link)
- Non-image attachments (PDFs, logs, etc.)

---

## Data Model

New `Incident` model in `app/models/incident.py` using `TimestampMixin`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | TimestampMixin auto |
| `candidate_id` | FK → candidates | who submitted |
| `category` | StrEnum | `bug`, `feature_request`, `question`, `other` |
| `title` | String(200) | required |
| `description` | Text | required, max 5000 chars |
| `context` | JSONB | auto-collected: email, plan_tier, browser, os, page_url, console_errors |
| `attachments` | JSONB | array of `{filename, url, size_bytes, content_type}`, max 3 items |
| `github_issue_number` | Integer, nullable | set after successful sync |
| `github_issue_url` | String, nullable | set after successful sync |
| `github_status` | StrEnum | `pending`, `synced`, `failed` |
| `retry_count` | Integer | default 0, max 5 |
| `created_at` | DateTime | TimestampMixin auto |
| `updated_at` | DateTime | TimestampMixin auto |

New StrEnums in `app/models/enums.py`:
- `IncidentCategory`: `bug`, `feature_request`, `question`, `other`
- `GitHubSyncStatus`: `pending`, `synced`, `failed`

Alembic migration: `024_add_incidents.py`

---

## Backend API

### Router: `app/api/incidents.py`

Registered at `/api/v1/incidents` in `app/main.py`.

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|-----------|---------|
| `POST /incidents` | `get_current_candidate` | `3/hour` | Submit incident (multipart form) |
| `GET /incidents` | `get_current_admin` | — | List all incidents (admin, paginated) |

### POST /incidents

**Input:** Multipart form data:
- `category` — required, one of: bug, feature_request, question, other
- `title` — required, string, max 200 chars
- `description` — required, string, max 5000 chars
- `context` — required, JSON string with auto-collected fields
- `files` — optional, up to 3 image files, max 5MB each, content-type image/*

**Flow:**
1. Validate fields and file constraints
2. Upload images to R2 via `StorageProtocol` (path: `incidents/{incident_id}/{filename}`)
3. Save `Incident` row with `github_status: pending`
4. Call GitHub Issues API inline:
   - `POST /repos/{GITHUB_REPO}/issues`
   - Title: `[{category}] {title}`
   - Body: formatted markdown (see GitHub Issue Format below)
   - Labels: `bug` / `enhancement` / `question` / `incident` (mapped from category)
5. On success: update `github_issue_number`, `github_issue_url`, `github_status: synced`
6. On failure: leave `github_status: failed`, log error to Sentry, return 201 anyway
7. Return: `{id, title, category, github_issue_url, github_status, created_at}`

### GET /incidents (admin)

**Query params:** `page`, `per_page`, `github_status` (filter), `category` (filter)

**Returns:** Paginated list of `{id, candidate_email, category, title, github_issue_url, github_status, created_at}`

---

## GitHub Issue Format

```markdown
## Description

{user's description}

## Attachments

![{filename}]({r2_url})
...or "None" if no attachments

## Context

| Field | Value |
|-------|-------|
| User | {email} |
| Plan | {plan_tier} |
| Page | {page_url} |
| Browser | {browser/version} |
| OS | {os} |
| Submitted | {ISO timestamp} |
| Incident ID | {uuid} |

## Console Errors

```
{last 10 console.error entries, or "None"}
```
```

**Label mapping:**
- `bug` → `bug` (exists)
- `feature_request` → `enhancement` (exists)
- `question` → `question` (create if missing)
- `other` → `incident` (create if missing)

---

## GitHub Client

New `app/infrastructure/github_client.py`:

- Protocol: `GitHubClientProtocol` with `create_issue(title, body, labels) -> {number, url}`
- Implementation: `GitHubClient` using `httpx.AsyncClient`
- Auth: `Authorization: Bearer {GITHUB_TOKEN}` header
- Endpoint: `https://api.github.com/repos/{GITHUB_REPO}/issues`
- Timeout: 10 seconds
- Test stub: `GitHubStub` that returns a fake issue number/url

Follows the same Protocol pattern as `OpenAIClientProtocol`, `HunterClientProtocol`, etc.

---

## Retry Cron

Add to `app/worker.py` ARQ cron schedule:

- **Job:** `retry_failed_github_syncs`
- **Schedule:** every 15 minutes
- **Logic:** query incidents where `github_status = 'failed'` and `retry_count < 5`, attempt GitHub API call, update status. After 5 failures, leave as `failed` (admin sees it in the list).
- **Lock:** `lock:cron:retry_github_syncs` Redis key (follows existing ARQ lock pattern)

---

## Config

Add to `app/config.py` `Settings`:

| Setting | Default | Notes |
|---------|---------|-------|
| `GITHUB_TOKEN` | `""` | Fine-grained PAT with Issues write permission. Required for incident sync. |
| `GITHUB_REPO` | `"EranDaniel98/jobhunter"` | Target repo for issues |

Add to `backend/.env.example` with comments.

---

## Frontend

### Floating Button

**File:** `src/components/incidents/incident-button.tsx`

- Circular button, fixed position bottom-right (e.g., `bottom-6 right-6`)
- Lucide `MessageSquarePlus` icon
- z-index above page content but below modals
- Opens the incident Sheet on click
- Mounted in `src/app/(dashboard)/layout.tsx`

### Incident Form (Sheet)

**File:** `src/components/incidents/incident-form.tsx`

Opens as a right-side `Sheet` (shadcn/ui). Contents:

1. **Category** — 4 radio buttons: Bug, Feature Request, Question, Other
2. **Title** — Input, required, max 200 chars
3. **Description** — Textarea, required, max 5000 chars. Placeholder adapts per category:
   - Bug: "Steps to reproduce..."
   - Feature Request: "What would you like to see?"
   - Question: "What do you need help with?"
   - Other: "Tell us more..."
4. **Attachments** — Image dropzone (reuse pattern from resume UploadZone). Max 3 files, 5MB each, image/* only. Shows thumbnails with remove button.
5. **Submit button** — loading spinner during submission, disabled while submitting

**Auto-collected context** (not shown to user):
- `email` — from `useAuth()` user
- `plan_tier` — from `useAuth()` user
- `page_url` — `window.location.href` captured when sheet opens
- `browser` — parsed from `navigator.userAgent`
- `os` — parsed from `navigator.userAgent`
- `console_errors` — last 10 `console.error` calls captured via global listener

**Console error capture:** Dashboard layout installs a global `console.error` wrapper on mount that pushes entries to a `useRef` array (max 10, FIFO). The ref is passed to the incident form as a prop or via context.

**After submission:**
- Success: Sonner toast "Incident submitted" with optional GitHub issue link. Close sheet, reset form.
- Failure: Sonner toast error. Sheet stays open, form preserved for retry.

### API Module

**File:** `src/lib/api/incidents.ts`

- `submitIncident(data: FormData): Promise<IncidentResponse>` — POST multipart to `/incidents`

### Hook

**File:** `src/lib/hooks/use-incidents.ts`

- `useSubmitIncident()` — `useMutation` wrapping `submitIncident`, invalidates admin queries on success

### Types

Add to `src/lib/types.ts`:

```typescript
interface IncidentResponse {
  id: string;
  title: string;
  category: "bug" | "feature_request" | "question" | "other";
  github_issue_url: string | null;
  github_status: "pending" | "synced" | "failed";
  created_at: string;
}
```

### Admin Overview

**Modify:** `src/components/admin/overview-stats.tsx`

Add an incident count card showing total incidents + how many have `github_status: failed`. Card links to GitHub Issues page (filtered by label) on click.

**New API/hook:** `GET /incidents?per_page=0` with a count-only response, or add incident stats to the existing admin overview endpoint if one exists.

---

## File Map

| Action | File | Layer |
|--------|------|-------|
| Create | `app/models/incident.py` | Model |
| Modify | `app/models/__init__.py` | Export |
| Modify | `app/models/enums.py` | New enums |
| Create | `app/schemas/incident.py` | Pydantic schemas |
| Create | `app/services/incident_service.py` | Business logic |
| Create | `app/infrastructure/github_client.py` | GitHub API client |
| Modify | `app/infrastructure/protocols.py` | Add GitHubClientProtocol |
| Create | `app/api/incidents.py` | Router |
| Modify | `app/main.py` | Register router |
| Modify | `app/config.py` | GITHUB_TOKEN, GITHUB_REPO |
| Modify | `app/dependencies.py` | get_github_client |
| Modify | `app/worker.py` | Retry cron job |
| Create | `alembic/versions/024_add_incidents.py` | Migration |
| Create | `src/components/incidents/incident-button.tsx` | Floating button |
| Create | `src/components/incidents/incident-form.tsx` | Sheet form |
| Create | `src/lib/api/incidents.ts` | API module |
| Create | `src/lib/hooks/use-incidents.ts` | Mutation hook |
| Modify | `src/lib/types.ts` | Incident types |
| Modify | `src/app/(dashboard)/layout.tsx` | Mount button + console capture |
| Modify | `src/components/admin/overview-stats.tsx` | Incident count card |
| Modify | `backend/.env.example` | New env vars |
| Modify | `tests/conftest.py` | GitHubStub |
