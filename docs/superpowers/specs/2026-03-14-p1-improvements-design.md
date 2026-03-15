# P1 Improvements Design Spec

**Date:** 2026-03-14
**Status:** Approved
**Scope:** 5 independent features covering growth, deliverability, infrastructure, cost optimization, and scalability

---

## 1. Waitlist to Beta Invites (Admin-Triggered)

### Overview
Convert the existing waitlist signup flow into an admin-triggered invite pipeline. Admins select waitlist entries from the dashboard and send invite codes via email. Reuses the existing invite system and Resend email infrastructure.

### Data Changes
**Migration: `022_add_waitlist_status.py`**

Add columns to `waitlist_entries`:
- `status` (string, default `"pending"`) - one of: `pending`, `invited`, `registered`
- `invited_at` (timestamp, nullable)
- `invite_code_id` (`sa.dialects.postgresql.UUID(as_uuid=True)`, FK to `invite_codes.id`, nullable)

Add column to `invite_codes`:
- `email` (string, nullable) - the email address this invite was generated for. Used by the registration hook to match waitlist entries.

### API

**`GET /api/v1/admin/waitlist`**
- List waitlist entries with filtering by status
- Pagination via `skip`/`limit`
- Ordered by `created_at` ASC (FIFO)
- Response model: `WaitlistListResponse` (define in `app/schemas/admin.py`)
- Returns: email, source, status, created_at, invited_at

**`POST /api/v1/admin/waitlist/{id}/invite`**
- Create a new `invite_service.create_system_invite(db, email)` variant that sets `invited_by_id=None` (system-generated invite, no candidate actor). Store the waitlist entry's email on the invite code's new `email` column.
- Send invite email via Resend
- Update waitlist entry status to `invited`, set `invited_at`, set `invite_code_id`
- Idempotent: if already invited, return existing invite code
- Create `AdminAuditLog` entry for the action

**`POST /api/v1/admin/waitlist/invite-batch`**
- Body: `{"ids": [1, 2, 3]}`
- Max 50 per batch
- **Best-effort semantics**: each invite is committed independently (emails already sent cannot be rolled back on later failures)
- Returns: `{"invited": 3, "skipped": 1, "errors": []}`
- Create `AdminAuditLog` entry for the batch action

### Invite Service Changes
Add `create_system_invite(db, email: str) -> InviteCode` to `invite_service.py`:
- Same logic as `create_invite()` but `invited_by_id=None`
- Sets `email` on the invite code
- Returns the new invite code

### Registration Hook
Modify `auth_service.register()`: when an invite code is consumed, look up the invite code's `email` field. If it matches a `waitlist_entries` row, update that row's status to `registered`. This closes the conversion tracking loop.

### Frontend
Add "Waitlist" tab to admin dashboard (`/admin/waitlist`):
- Table: Email, Source, Status (badge), Signed Up, Actions
- "Invite" button per row (disabled if already invited/registered)
- Checkbox selection + "Invite Selected" bulk action
- Filter dropdown: All / Pending / Invited / Registered
- Count badges per status

### Email Template
```
Subject: You're invited to JobHunter AI

Hi! You signed up for the JobHunter AI waitlist and we'd love to have you.

Your invite link: {FRONTEND_URL}/register?invite={code}

This link expires in 7 days.
```

### Key Files
- `alembic/versions/022_add_waitlist_status.py` (new)
- `app/api/admin.py` (extend)
- `app/schemas/admin.py` (extend - `WaitlistEntryResponse`, `WaitlistListResponse`)
- `app/services/invite_service.py` (extend - `create_system_invite`)
- `app/services/auth_service.py` (extend registration hook)
- `app/models/waitlist.py` (extend)
- `app/models/invite.py` (extend - `email` column)
- `frontend/src/app/(dashboard)/admin/waitlist/page.tsx` (new)

---

## 2. SPF/DKIM Health Check

### Overview
Admin dashboard panel that verifies SPF, DKIM, and DMARC DNS records are correctly configured for the sender email domain. Uses `dns.asyncresolver` from `dnspython` for non-blocking async DNS lookups.

### Dependency
Add `dnspython>=2.6.0` to `pyproject.toml`.

### Service
**New file: `app/services/dns_health_service.py`**

Function `async check_email_dns_health(domain: str)` performs three DNS lookups using `dns.asyncresolver.Resolver`:

- **SPF**: TXT lookup on domain. Look for record containing `v=spf1`. Check for `include:amazonses.com` (Resend's SPF). Pass/fail + raw record.
- **DKIM**: TXT lookup on `resend._domainkey.{domain}` (Resend's default selector). Pass/fail + existence check.
- **DMARC**: TXT lookup on `_dmarc.{domain}`. Look for `v=DMARC1`. Pass/fail + policy value.

Returns:
```python
{
    "domain": "hunter-job.com",
    "spf": {"status": "pass", "record": "v=spf1 include:amazonses.com ~all"},
    "dkim": {"status": "pass", "selector": "resend"},
    "dmarc": {"status": "fail", "record": null, "recommendation": "Add a DMARC record"},
    "overall": "warning"
}
```

Per-check `status` is always `"pass"` or `"fail"` (record present and valid, or not).

Overall logic (escalating):
- All three pass = `"pass"`
- DKIM or DMARC missing (but SPF present) = `"warning"`
- SPF missing = `"fail"` (SPF is the most critical for deliverability)

### API

**`GET /api/v1/admin/email-health`**
- Calls `check_email_dns_health()` with domain from `settings.SENDER_EMAIL`
- Returns health dict
- No caching - DNS lookups are fast, admin-only endpoint

### Frontend
"Email Health" card on admin dashboard:
- Three status rows: SPF, DKIM, DMARC with green check / yellow warning / red X
- Expandable detail showing raw DNS record
- Overall status badge
- Link to `docs/email-domain-setup.md` (already exists)

### Landing Page Fix
Update the trust signal on the landing page that claims "SPF/DKIM/DMARC verified" to something accurate like "Email deliverability monitoring".

### Key Files
- `app/services/dns_health_service.py` (new)
- `app/api/admin.py` (extend)
- `frontend/src/components/admin/email-health-card.tsx` (new)
- `frontend/src/app/(marketing)/page.tsx` (fix trust signal)

---

## 3. pgBouncer Connection Pooling

### Overview
Add pgBouncer as a connection pooling proxy between the app and PostgreSQL. Transaction-mode pooling. Local dev via Docker Compose, Railway-ready via env var separation.

### SAVEPOINT Compatibility Note
Transaction-mode pgBouncer does not support `SAVEPOINT` (used by SQLAlchemy nested transactions). The codebase uses `async_sessionmaker` with standard `BEGIN`/`COMMIT` patterns and does not use explicit nested transactions or `session.begin_nested()`. SQLAlchemy's `autoflush` can emit implicit `SAVEPOINT`s during `flush()` in some edge cases, but our session configuration (`expire_on_commit=False`) avoids this. No codebase changes needed, but future code must avoid `session.begin_nested()` when pgBouncer is active.

### Docker Compose
Add `pgbouncer` service:
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
  deploy:
    resources:
      limits:
        memory: 256M
        cpus: "0.5"
```

### Configuration
Add to `app/config.py`:
- `PGBOUNCER_URL: str = ""` - when set, used for regular queries

This is a **startup-time decision**, not a runtime switch. In `app/infrastructure/database.py`, at module load:
- If `PGBOUNCER_URL` is set: use it as the engine URL, reduce SQLAlchemy pool to `pool_size=5`, `max_overflow=5`
- If `PGBOUNCER_URL` is empty: use `DATABASE_URL` with current pool settings (unchanged)
- Keep `pool_pre_ping=True` in both cases

`DATABASE_URL` always used for Alembic migrations (DDL doesn't work through transaction-mode pgBouncer).

### Environment
Update `.env.example`:
```
DATABASE_URL=postgresql+asyncpg://jobhunter:jobhunter@localhost:5432/jobhunter
PGBOUNCER_URL=postgresql+asyncpg://jobhunter:jobhunter@localhost:6432/jobhunter
```

### Health Check
Extend `/api/v1/health` to report connection path (direct vs pgBouncer) in its response.

### Railway
No deployment changes. When scaling to multiple instances, set `PGBOUNCER_URL` in Railway to their managed pooling endpoint. Zero code changes.

### Key Files
- `docker-compose.yml` (extend)
- `app/config.py` (extend)
- `app/infrastructure/database.py` (modify)
- `app/api/health.py` (extend)
- `.env.example` (extend)

---

## 4. OpenAI Response Caching

### Overview
Split company dossier generation into generic (cacheable, shared across users) and personal (always fresh, per-candidate) phases. Cache generic results in Redis to avoid redundant OpenAI calls.

### Schema Split
The current `DOSSIER_SCHEMA` and `DOSSIER_PROMPT` in `company_service.py` are replaced by two new schemas and prompts.

**`DOSSIER_GENERIC_SCHEMA`** (JSON schema with `additionalProperties: false`, all fields `required`):
- `culture_summary` (string), `culture_score` (number 0-100), `red_flags` (array of strings)
- `interview_format` (string), `interview_questions` (array of strings), `compensation_data` (string)
- `key_people` (array of objects), `recent_news` (array of strings)

**`DOSSIER_GENERIC_PROMPT`**: Same context as current `DOSSIER_PROMPT` (company name, domain, industry, size, location, description, tech stack, web search context) but instructions ask only for the generic fields above. No candidate-specific context included.

**`DOSSIER_PERSONAL_SCHEMA`** (JSON schema with `additionalProperties: false`, all fields `required`):
- `why_hire_me` (string), `resume_bullets` (array of strings), `fit_score_tips` (array of strings)

**`DOSSIER_PERSONAL_PROMPT`**: Receives the generic dossier output as context (culture, interview format, key people, etc.) plus the candidate's DNA summary. Instructions ask for personalized recommendations only.

The old `DOSSIER_SCHEMA` and `DOSSIER_PROMPT` are removed. All prompt templates use `{{` to escape braces per project convention.

Define Pydantic models `CompanyDossierGeneric` and `CompanyDossierPersonal` in `app/schemas/company.py` for type safety. The final merged result matches the existing `CompanyDossier` shape so downstream code is unchanged.

### Cache Layer
**New file: `app/infrastructure/dossier_cache.py`**

- `get_cached_dossier(domain: str) -> dict | None` - Redis GET on `dossier:generic:{domain}`, deserialize JSON
- `cache_dossier(domain: str, data: dict, ttl: int) -> None` - Redis SETEX

Uses existing `redis_safe_get` / `redis_safe_setex` helpers for graceful degradation.

Config: `DOSSIER_CACHE_TTL: int = 604800` (7 days).

### Pipeline Changes
Modify `generate_dossier_node` in `app/graphs/company_research.py`:

1. Check cache for `dossier:generic:{domain}`
2. **Cache hit**: Use cached data, skip generic OpenAI call. Log cache hit.
3. **Cache miss**: Build prompt from `DOSSIER_GENERIC_PROMPT` with company fields + web context. Call `parse_structured()` with `DOSSIER_GENERIC_SCHEMA`. Cache the result.
4. **Always**: Build prompt from `DOSSIER_PERSONAL_PROMPT` with generic dossier output + candidate DNA summary. Call `parse_structured()` with `DOSSIER_PERSONAL_SCHEMA`.
5. Merge generic + personal dicts into final dossier. Continue pipeline as before.

### Cost Impact
Generic call: ~1500-2000 output tokens (expensive). Personal call: ~300-500 output tokens (cheap). For company researched by N users, saves (N-1) generic calls.

### Cache Invalidation
- TTL-based: 7 days, auto-expires
- Manual: `DELETE /api/v1/admin/cache/dossier/{domain}` for admin force-refresh (RESTful pattern consistent with existing admin API)

### Key Files
- `app/services/company_service.py` (replace `DOSSIER_SCHEMA`/`DOSSIER_PROMPT` with split versions)
- `app/schemas/company.py` (extend - `CompanyDossierGeneric`, `CompanyDossierPersonal`)
- `app/infrastructure/dossier_cache.py` (new)
- `app/graphs/company_research.py` (modify `generate_dossier_node`)
- `app/api/admin.py` (extend - cache clear endpoint)
- `app/config.py` (extend - `DOSSIER_CACHE_TTL`)

---

## 5. Batch ARQ Cron Jobs

### Overview
Convert sequential per-item cron processing to a coordinator pattern: cron jobs query items, chunk them, and enqueue worker jobs per chunk. Each chunk processes items concurrently via `asyncio.gather` with a semaphore.

### Configuration
Add to `app/config.py`:
- `ARQ_CHUNK_SIZE: int = 10` - items per chunk
- `ARQ_CHUNK_CONCURRENCY: int = 5` - max concurrent items within a chunk

### Coordinator Pattern

**Before:**
```
cron fires -> query all items -> loop one by one -> process each
```

**After:**
```
cron fires -> query all items -> chunk into groups of N -> enqueue one job per chunk
worker picks up chunk job -> asyncio.gather with semaphore -> process chunk concurrently
```

### Changes to `app/worker.py`

**`check_followup_due`** (becomes coordinator):
- Query all due follow-ups
- Chunk message IDs into groups of `ARQ_CHUNK_SIZE`
- Enqueue `process_followup_chunk` per chunk via `await ctx["redis"].enqueue_job("process_followup_chunk", message_ids=chunk)`

**`process_followup_chunk(ctx, message_ids: list[str])`** (new worker function):
- Takes list of message IDs
- Per-message dedup checks (newer-message, pending-action) remain as individual DB queries per message - these are lightweight SELECTs and batching them would add complexity without meaningful gain
- Outreach graph invocation per message
- `asyncio.gather` with `asyncio.Semaphore(ARQ_CHUNK_CONCURRENCY)`

**`run_daily_scout`** (becomes coordinator):
- Query active candidates with DNA
- Chunk candidate IDs, enqueue `process_scout_chunk` per chunk

**`process_scout_chunk(ctx, candidate_ids: list[str])`** (new worker function):
- Scout pipeline per candidate with semaphore-bounded concurrency

**`run_weekly_analytics`** (becomes coordinator):
- Same pattern, enqueue `process_analytics_chunk`

**`process_analytics_chunk(ctx, candidate_ids: list[str])`** (new worker function):
- Analytics pipeline per candidate with semaphore-bounded concurrency

### Error Handling
Each item in a chunk wrapped in try/except. Single item failure doesn't kill the chunk. Structured log per failure (item ID + error). Summary logged: `"Chunk complete: 9/10 succeeded, 1 failed"`.

### ARQ Registration
- Coordinator functions remain in `WorkerSettings.cron_jobs` (schedule unchanged)
- Three new chunk processor functions added to `WorkerSettings.functions` list (they are enqueued programmatically, not scheduled)
- Chunk jobs use default ARQ `job_timeout` (300s). If a chunk with 10 concurrent pipeline invocations needs more time, increase via `job_timeout` kwarg on the function registration.

### Scaling Path
One worker: chunks process sequentially from queue, concurrency within each chunk. Add workers: chunks automatically distribute. No code changes.

### Key Files
- `app/worker.py` (modify)
- `app/config.py` (extend)

---

## Cross-Cutting Concerns

### Testing
Each feature gets its own test file following existing patterns:
- `tests/test_waitlist_invites.py`
- `tests/test_dns_health.py`
- `tests/test_pgbouncer.py` (connection config tests only)
- `tests/test_dossier_cache.py`
- `tests/test_worker_batching.py`

All tests use existing stubs from `tests/conftest.py`. Redis tests use the existing Redis test instance.

### Configuration Summary
New env vars:
| Variable | Default | Feature |
|----------|---------|---------|
| `PGBOUNCER_URL` | `""` | pgBouncer |
| `DOSSIER_CACHE_TTL` | `604800` | OpenAI caching |
| `ARQ_CHUNK_SIZE` | `10` | Batch ARQ |
| `ARQ_CHUNK_CONCURRENCY` | `5` | Batch ARQ |

### Dependencies
New pyproject.toml additions:
- `dnspython>=2.6.0` (SPF/DKIM health checks)

### Migrations
- `022_add_waitlist_status.py` (waitlist status, invited_at, invite_code_id FK, invite_codes.email)
