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
- `invite_code_id` (UUID FK to `invite_codes.id`, nullable)

### API

**`GET /api/v1/admin/waitlist`**
- List waitlist entries with filtering by status
- Pagination via `skip`/`limit`
- Ordered by `created_at` ASC (FIFO)
- Returns: email, source, status, created_at, invited_at

**`POST /api/v1/admin/waitlist/{id}/invite`**
- Generate invite code via existing `invite_service.create_invite()`
- Send invite email via Resend
- Update waitlist entry status to `invited`, set `invited_at`
- Idempotent: if already invited, return existing invite code

**`POST /api/v1/admin/waitlist/invite-batch`**
- Body: `{"ids": [1, 2, 3]}`
- Max 50 per batch
- Returns: `{"invited": 3, "skipped": 1, "errors": []}`

### Registration Hook
Modify `auth_service.register()`: when an invite code is consumed, check if its email matches a waitlist entry. If so, update waitlist status to `registered`.

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
- `app/services/invite_service.py` (extend)
- `app/services/auth_service.py` (extend registration hook)
- `app/models/waitlist.py` (extend)
- `frontend/src/app/(dashboard)/admin/waitlist/page.tsx` (new)

---

## 2. SPF/DKIM Health Check

### Overview
Admin dashboard panel that verifies SPF, DKIM, and DMARC DNS records are correctly configured for the sender email domain. Uses `dnspython` for async DNS lookups.

### Dependency
Add `dnspython>=2.6.0` to `pyproject.toml`.

### Service
**New file: `app/services/dns_health_service.py`**

Function `check_email_dns_health(domain: str)` performs three DNS lookups:

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
    "overall": "warning"  # pass / warning / fail
}
```

Overall: all three pass = `pass`, any missing = `warning`, SPF missing = `fail`.

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
- Link to `docs/email-domain-setup.md`

### Landing Page Fix
Update the trust signal on the landing page that claims "SPF/DKIM/DMARC verified" to something accurate like "Email deliverability monitoring" or conditionally show only if records are configured.

### Key Files
- `app/services/dns_health_service.py` (new)
- `app/api/admin.py` (extend)
- `frontend/src/components/admin/email-health-card.tsx` (new)
- `frontend/src/app/(marketing)/page.tsx` (fix trust signal)

---

## 3. pgBouncer Connection Pooling

### Overview
Add pgBouncer as a connection pooling proxy between the app and PostgreSQL. Transaction-mode pooling. Local dev via Docker Compose, Railway-ready via env var separation.

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

In `app/infrastructure/database.py`:
- Use `PGBOUNCER_URL` if set, fall back to `DATABASE_URL`
- When pgBouncer is active, reduce SQLAlchemy pool: `pool_size=5`, `max_overflow=5`
- Keep `pool_pre_ping=True`

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
Define in `app/schemas/company.py`:

**`CompanyDossierGeneric`** (cacheable):
- `culture_summary`, `culture_score`, `red_flags`
- `interview_format`, `compensation_data`
- `key_people`, `recent_news`

**`CompanyDossierPersonal`** (always fresh):
- `why_hire_me`, `resume_bullets`, `fit_score_tips`

Final result merges both into the existing `CompanyDossier` shape. Downstream code unchanged.

### Cache Layer
**New file: `app/infrastructure/dossier_cache.py`**

- `get_cached_dossier(domain: str) -> dict | None` - Redis GET on `dossier:generic:{domain}`, deserialize JSON
- `cache_dossier(domain: str, data: dict, ttl: int) -> None` - Redis SETEX

Uses existing `redis_safe_get` / `redis_safe_setex` helpers for graceful degradation.

Config: `DOSSIER_CACHE_TTL: int = 604800` (7 days).

### Pipeline Changes
Modify `generate_dossier_node` in `app/graphs/company_research.py`:

1. Check cache for `dossier:generic:{domain}`
2. **Cache hit**: Use cached data, skip generic OpenAI call. Log hit.
3. **Cache miss**: Call `parse_structured()` with `CompanyDossierGeneric` schema. Cache result.
4. **Always**: Call `parse_structured()` with `CompanyDossierPersonal` schema, passing generic data + candidate DNA as context. Shorter, cheaper call (3 fields only).
5. Merge generic + personal into final dossier. Continue pipeline.

### Cost Impact
Generic call: ~1500-2000 output tokens (expensive). Personal call: ~300-500 output tokens (cheap). For company researched by N users, saves (N-1) generic calls.

### Cache Invalidation
- TTL-based: 7 days, auto-expires
- Manual: `POST /api/v1/admin/cache/clear?domain=example.com` for admin force-refresh

### Key Files
- `app/schemas/company.py` (extend)
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
- Enqueue `process_followup_chunk` per chunk

**`process_followup_chunk(ctx, message_ids: list[str])`** (new):
- Takes list of message IDs
- Dedup checks + outreach graph per message
- `asyncio.gather` with `asyncio.Semaphore(ARQ_CHUNK_CONCURRENCY)`

**`run_daily_scout`** (becomes coordinator):
- Query active candidates with DNA
- Chunk candidate IDs, enqueue `process_scout_chunk` per chunk

**`process_scout_chunk(ctx, candidate_ids: list[str])`** (new):
- Scout pipeline per candidate with semaphore-bounded concurrency

**`run_weekly_analytics`** (becomes coordinator):
- Same pattern, enqueue `process_analytics_chunk`

**`process_analytics_chunk(ctx, candidate_ids: list[str])`** (new):
- Analytics pipeline per candidate with semaphore-bounded concurrency

### Error Handling
Each item in a chunk wrapped in try/except. Single item failure doesn't kill the chunk. Structured log per failure (item ID + error). Summary logged: `"Chunk complete: 9/10 succeeded, 1 failed"`.

### ARQ Registration
Add three new worker functions to `WorkerSettings.functions`. Cron schedule unchanged.

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
- `022_add_waitlist_status.py` (waitlist status, invited_at, invite_code_id FK)
