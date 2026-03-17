# P1 Improvements Design Spec (v2 — Enhanced)

**Date:** 2026-03-14  
**Revised:** 2026-03-15  
**Status:** Approved  
**Scope:** 5 independent features covering growth, deliverability, infrastructure, cost optimization, and scalability

---

## Deployment & Rollback Strategy

All 5 features are independent and may be deployed in any order, with one constraint: **Feature 1 requires migration `022` to run before the API deployment**. The recommended deployment sequence is:

1. **Feature 3 (pgBouncer)** — infrastructure only, zero app code risk
2. **Feature 2 (DNS Health)** — read-only, low risk
3. **Feature 4 (Dossier Caching)** — cost savings start immediately
4. **Feature 5 (Batch ARQ)** — scalability improvement
5. **Feature 1 (Waitlist Invites)** — user-facing, deploy last to allow soak time on infra changes

**Rollback procedures per feature:**

| Feature | Rollback |
|---------|----------|
| 1 - Waitlist Invites | Migration is additive (new columns with defaults) — backward-compatible. Revert API deploy; old code ignores new columns. |
| 2 - DNS Health | Remove endpoint + frontend card. No data changes. |
| 3 - pgBouncer | Unset `PGBOUNCER_URL`, restart app. Falls back to direct connection. |
| 4 - Dossier Caching | Revert to previous `company_service.py`. Cache keys in Redis expire naturally. |
| 5 - Batch ARQ | Revert `worker.py`. Crons fall back to sequential processing. |

---

## Observability Standard

All features follow a consistent structured logging convention. Every significant action emits a structured log entry containing:

```python
logger.info(
    "action_description",
    extra={
        "feature": "waitlist_invites",   # feature identifier
        "action": "invite_sent",          # specific action
        "item_id": "waitlist:42",         # affected entity
        "duration_ms": 230,               # wall-clock time
        "status": "success",              # success | failure | skipped
        "detail": {}                      # action-specific metadata
    }
)
```

Each feature section below specifies its key log events.

---

## Scale Assumptions

| Metric | Expected Range | Impacts |
|--------|---------------|---------|
| Waitlist entries | 500–5,000 at launch | Batch size (50 max), index design |
| Dossier requests/day | 50–200 | Cache hit rate, Redis memory (~2KB × unique domains) |
| Unique company domains | ~500 in first 3 months | Redis memory: ~1MB — negligible |
| Cron items per run (follow-ups) | 20–100 | Chunk count, queue depth |
| Cron items per run (scout) | 50–300 | Chunk count, worker capacity |
| Concurrent users | 10–50 | pgBouncer pool sizing |

---

## 1. Waitlist to Beta Invites (Admin-Triggered)

### Overview
Convert the existing waitlist signup flow into an admin-triggered invite pipeline. Admins select waitlist entries from the dashboard and send invite codes via email. Reuses the existing invite system and Resend email infrastructure.

### Data Changes
**Migration: `022_add_waitlist_status.py`**

Add columns to `waitlist_entries`:
- `status` (string, default `"pending"`) — one of: `pending`, `invited`, `invite_failed`, `registered`
- `invited_at` (timestamp, nullable)
- `invite_code_id` (`sa.dialects.postgresql.UUID(as_uuid=True)`, FK to `invite_codes.id`, nullable)
- `invite_error` (string, nullable) — stores last error message on failure for admin visibility

Add column to `invite_codes`:
- `email` (string, nullable) — the email address this invite was generated for. Used by the registration hook to match waitlist entries.

**Index:**
- Composite index on `waitlist_entries(status, created_at)` — supports the admin list endpoint's filter + sort pattern.

### Rate Limiting

Add to `app/config.py`:
- `MAX_DAILY_INVITES: int = 200` — rolling 24-hour cap across all admin users

Track via Redis counter: `waitlist:invites:daily:{YYYY-MM-DD}` with 48h TTL. Both the single-invite and batch-invite endpoints decrement the remaining quota before processing. If quota is exceeded, return `429 Too Many Requests` with a `Retry-After` header.

### API

**`GET /api/v1/admin/waitlist`**
- List waitlist entries with filtering by status
- Pagination via `skip`/`limit`
- Ordered by `created_at` ASC (FIFO)
- Response model: `WaitlistListResponse` (define in `app/schemas/admin.py`)
- Returns: email, source, status, created_at, invited_at, invite_error

**`POST /api/v1/admin/waitlist/{id}/invite`**
- Check daily invite quota (reject with 429 if exceeded)
- Create a new `invite_service.create_system_invite(db, email)` variant that sets `invited_by_id=None` (system-generated invite, no candidate actor). Store the waitlist entry's email on the invite code's new `email` column.
- Send invite email via Resend
- **On email success:** Update waitlist entry status to `invited`, set `invited_at`, set `invite_code_id`
- **On email failure:** Update waitlist entry status to `invite_failed`, store error in `invite_error`. The invite code remains valid — admin can retry or the code can be sent manually.
- Idempotent: if already `invited`, return existing invite code. If `invite_failed`, allow retry (reset status, re-send).
- Create `AdminAuditLog` entry for the action

**`POST /api/v1/admin/waitlist/invite-batch`**
- Body: `{"ids": [1, 2, 3]}`
- Max 50 per batch
- Check daily invite quota (reject entire batch with 429 if remaining quota < batch size)
- **Best-effort semantics**: each invite is committed independently (emails already sent cannot be rolled back on later failures)
- Failed items marked `invite_failed` with error detail
- Returns: `{"invited": 3, "skipped": 1, "failed": 0, "errors": [], "daily_quota_remaining": 196}`
- Create `AdminAuditLog` entry for the batch action

### Invite Expiration
Confirm: the existing `invite_codes` table already has an `expires_at` column set to 7 days from creation. The `create_system_invite` function must set this consistently. The registration flow already rejects expired codes. No changes needed — documenting for completeness.

### Invite Service Changes
Add `create_system_invite(db, email: str) -> InviteCode` to `invite_service.py`:
- Same logic as `create_invite()` but `invited_by_id=None`
- Sets `email` on the invite code
- Sets `expires_at` to `utcnow() + timedelta(days=7)`
- Returns the new invite code

### Registration Hook
Modify `auth_service.register()`: when an invite code is consumed, look up the invite code's `email` field. If it matches a `waitlist_entries` row, update that row's status to `registered`. This closes the conversion tracking loop.

### Frontend
Add "Waitlist" tab to admin dashboard (`/admin/waitlist`):
- Table: Email, Source, Status (badge), Signed Up, Error (tooltip on failed), Actions
- "Invite" button per row (disabled if already invited/registered; shows "Retry" if `invite_failed`)
- Checkbox selection + "Invite Selected" bulk action
- Filter dropdown: All / Pending / Invited / Failed / Registered
- Count badges per status
- Daily quota remaining shown at top of page

### Email Template
```
Subject: You're invited to JobHunter AI

Hi! You signed up for the JobHunter AI waitlist and we'd love to have you.

Your invite link: {FRONTEND_URL}/register?invite={code}

This link expires in 7 days.
```

### Log Events
- `waitlist.invite_sent` — successful invite (item_id: waitlist entry ID)
- `waitlist.invite_failed` — email send failure (detail: error message)
- `waitlist.batch_complete` — batch summary (detail: invited/skipped/failed counts)
- `waitlist.registration_matched` — invite code consumed, waitlist entry closed
- `waitlist.quota_exceeded` — daily cap hit (detail: requested count, remaining)

### Key Files
- `alembic/versions/022_add_waitlist_status.py` (new)
- `app/api/admin.py` (extend)
- `app/schemas/admin.py` (extend — `WaitlistEntryResponse`, `WaitlistListResponse`)
- `app/services/invite_service.py` (extend — `create_system_invite`)
- `app/services/auth_service.py` (extend registration hook)
- `app/models/waitlist.py` (extend)
- `app/models/invite.py` (extend — `email` column)
- `app/config.py` (extend — `MAX_DAILY_INVITES`)
- `frontend/src/app/(dashboard)/admin/waitlist/page.tsx` (new)

---

## 2. SPF/DKIM Health Check

### Overview
Admin dashboard panel that verifies SPF, DKIM, and DMARC DNS records are correctly configured for the sender email domain. Uses `dns.asyncresolver` from `dnspython` for non-blocking async DNS lookups.

### Dependency
Add `dnspython>=2.6.0` to `pyproject.toml`.

### Configuration
Add to `app/config.py`:
- `DKIM_SELECTOR: str = "resend"` — DKIM selector to check (change if switching email providers)
- `SPF_EXPECTED_INCLUDES: list[str] = ["amazonses.com", "resend.com"]` — any of these in the SPF record counts as pass
- `DNS_HEALTH_CACHE_TTL: int = 300` — 5-minute in-memory cache for DNS results
- `DNS_LOOKUP_TIMEOUT: float = 3.0` — per-lookup timeout in seconds

### Service
**New file: `app/services/dns_health_service.py`**

Function `async check_email_dns_health(domain: str)` performs three DNS lookups using `dns.asyncresolver.Resolver` with a per-lookup timeout of `DNS_LOOKUP_TIMEOUT` seconds:

- **SPF**: TXT lookup on domain. Look for record containing `v=spf1`. Check for any value in `SPF_EXPECTED_INCLUDES`. Pass/fail + raw record.
- **DKIM**: TXT lookup on `{DKIM_SELECTOR}._domainkey.{domain}`. Pass/fail + existence check.
- **DMARC**: TXT lookup on `_dmarc.{domain}`. Look for `v=DMARC1`. Pass/fail + policy value.

Each lookup is wrapped in a try/except catching `dns.resolver.NXDOMAIN`, `dns.resolver.NoAnswer`, `dns.resolver.Timeout`, and generic exceptions. Timeouts are reported as `"timeout"` status (distinct from `"fail"`).

Returns:
```python
{
    "domain": "hunter-job.com",
    "spf": {"status": "pass", "record": "v=spf1 include:amazonses.com ~all"},
    "dkim": {"status": "pass", "selector": "resend"},
    "dmarc": {"status": "fail", "record": null, "recommendation": "Add a DMARC record"},
    "overall": "warning",
    "checked_at": "2026-03-14T12:00:00Z"
}
```

Per-check `status` is one of: `"pass"`, `"fail"`, `"timeout"`.

Overall logic (escalating):
- All three pass = `"pass"`
- DKIM or DMARC missing (but SPF present) = `"warning"`
- SPF missing = `"fail"` (SPF is the most critical for deliverability)
- Any timeout = `"warning"` with recommendation to retry

### Caching
Results are cached in-memory using a module-level dict with TTL (`DNS_HEALTH_CACHE_TTL`, default 5 minutes). This prevents repeated DNS hits when admins refresh the dashboard. No Redis needed — this is a single-value, low-frequency cache.

```python
_cache: dict = {"result": None, "expires_at": 0}
```

### API

**`GET /api/v1/admin/email-health`**
- Calls `check_email_dns_health()` with domain from `settings.SENDER_EMAIL`
- Returns health dict (served from in-memory cache if fresh)
- Query param `?force=true` bypasses cache

### Frontend
"Email Health" card on admin dashboard:
- Three status rows: SPF, DKIM, DMARC with green check / yellow warning (timeout) / red X
- Expandable detail showing raw DNS record
- Overall status badge
- "Refresh" button (calls with `?force=true`)
- Link to `docs/email-domain-setup.md` (already exists)

### Landing Page Fix
Update the trust signal on the landing page that claims "SPF/DKIM/DMARC verified" to something accurate like "Email deliverability monitoring".

### Log Events
- `dns_health.check_complete` — overall result (detail: per-check statuses)
- `dns_health.lookup_timeout` — individual DNS timeout (detail: record type, domain)

### Key Files
- `app/services/dns_health_service.py` (new)
- `app/api/admin.py` (extend)
- `app/config.py` (extend — `DKIM_SELECTOR`, `SPF_EXPECTED_INCLUDES`, `DNS_HEALTH_CACHE_TTL`, `DNS_LOOKUP_TIMEOUT`)
- `frontend/src/components/admin/email-health-card.tsx` (new)
- `frontend/src/app/(marketing)/page.tsx` (fix trust signal)

---

## 3. pgBouncer Connection Pooling

### Overview
Add pgBouncer as a connection pooling proxy between the app and PostgreSQL. Transaction-mode pooling. Local dev via Docker Compose, Railway-ready via env var separation.

### SAVEPOINT Compatibility Note
Transaction-mode pgBouncer does not support `SAVEPOINT` (used by SQLAlchemy nested transactions). The codebase uses `async_sessionmaker` with standard `BEGIN`/`COMMIT` patterns and does not use explicit nested transactions or `session.begin_nested()`. SQLAlchemy's `autoflush` can emit implicit `SAVEPOINT`s during `flush()` in some edge cases, but our session configuration (`expire_on_commit=False`) avoids this. No codebase changes needed, but future code must avoid `session.begin_nested()` when pgBouncer is active.

### pool_pre_ping Note
`pool_pre_ping=True` is kept in both direct and pgBouncer modes. With transaction-mode pgBouncer, the ping query runs as its own transaction before the main query's transaction — this is safe and tested. The ping ensures stale connections are detected after pgBouncer recycling. This is intentional.

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

### Configuration
Add to `app/config.py`:
- `PGBOUNCER_URL: str = ""` — when set, used for regular queries

This is a **startup-time decision**, not a runtime switch. In `app/infrastructure/database.py`, at module load:
- If `PGBOUNCER_URL` is set: use it as the engine URL, reduce SQLAlchemy pool to `pool_size=5`, `max_overflow=5`
- If `PGBOUNCER_URL` is empty: use `DATABASE_URL` with current pool settings (unchanged)
- Keep `pool_pre_ping=True` in both cases (see note above)

`DATABASE_URL` always used for Alembic migrations (DDL doesn't work through transaction-mode pgBouncer).

### Environment
Update `.env.example`:
```
DATABASE_URL=postgresql+asyncpg://jobhunter:jobhunter@localhost:5432/jobhunter
PGBOUNCER_URL=postgresql+asyncpg://jobhunter:jobhunter@localhost:6432/jobhunter
```

### Health Check
Extend `/api/v1/health` to report:
- `connection_mode`: `"pgbouncer"` or `"direct"` (derived from whether `PGBOUNCER_URL` is set)
- `db_reachable`: boolean — a lightweight `SELECT 1` through the active connection path
- `pgbouncer_url_configured`: boolean

### Monitoring
Add admin endpoint `GET /api/v1/admin/db-pool-stats` that returns SQLAlchemy pool status:
```python
{
    "connection_mode": "pgbouncer",
    "pool_size": 5,
    "checked_out": 2,
    "overflow": 0,
    "checked_in": 3
}
```

This uses `engine.pool.status()`. For deeper pgBouncer-level stats (`SHOW STATS`, `SHOW POOLS`), add a note that these require direct admin connection to pgBouncer's admin console (port 6432, `pgbouncer` database) — out of scope for v1, but recommended for production monitoring dashboards.

### Railway
No deployment changes. When scaling to multiple instances, set `PGBOUNCER_URL` in Railway to their managed pooling endpoint. Zero code changes.

### Log Events
- `database.pool_mode` — logged once at startup (detail: connection mode, pool sizes)
- `database.health_check_failed` — connection check failure

### Key Files
- `docker-compose.yml` (extend)
- `app/config.py` (extend)
- `app/infrastructure/database.py` (modify)
- `app/api/health.py` (extend)
- `app/api/admin.py` (extend — pool stats endpoint)
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

- `get_cached_dossier(domain: str, input_hash: str) -> dict | None` — Redis GET on `dossier:generic:{domain}:{input_hash}`, deserialize JSON
- `cache_dossier(domain: str, input_hash: str, data: dict, ttl: int) -> None` — Redis SETEX
- `invalidate_dossier(domain: str) -> int` — Delete all keys matching `dossier:generic:{domain}:*`, returns count deleted

Uses existing `redis_safe_get` / `redis_safe_setex` helpers for graceful degradation.

**Cache key includes an input hash** to handle company data updates:
```python
def _compute_input_hash(company: CompanyRecord) -> str:
    """Hash of fields that affect generic dossier output."""
    payload = f"{company.name}|{company.domain}|{company.industry}|{company.size}|{company.description}|{company.tech_stack}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]
```

If any company field changes, the hash changes, and the old cached entry expires naturally via TTL while the new entry is generated fresh.

Config: `DOSSIER_CACHE_TTL: int = 604800` (7 days).

### Stampede Protection
When multiple users research the same company simultaneously (cache miss), only one should trigger the OpenAI call. Use a Redis-based lock:

```python
lock_key = f"dossier:lock:{domain}"
acquired = await redis.set(lock_key, "1", nx=True, ex=60)

if acquired:
    # Generate generic dossier, cache it, release lock
    ...
    await redis.delete(lock_key)
else:
    # Poll cache every 2s for up to 30s, then fall through to generate anyway
    ...
```

This prevents N identical OpenAI calls when N users hit the same uncached company. The 60s lock TTL ensures the lock is released even if the generator crashes.

### Pipeline Changes
Modify `generate_dossier_node` in `app/graphs/company_research.py`:

1. Compute `input_hash` from company fields
2. Check cache for `dossier:generic:{domain}:{input_hash}`
3. **Cache hit**: Use cached data, skip generic OpenAI call. Log cache hit.
4. **Cache miss**: Attempt to acquire stampede lock.
   - **Lock acquired**: Build prompt from `DOSSIER_GENERIC_PROMPT` with company fields + web context. Call `parse_structured()` with `DOSSIER_GENERIC_SCHEMA`. Cache the result. Release lock.
   - **Lock not acquired**: Poll cache with backoff (2s intervals, 30s max). If cache populated, use it. If timeout, generate anyway (graceful degradation).
5. **Always**: Build prompt from `DOSSIER_PERSONAL_PROMPT` with generic dossier output + candidate DNA summary. Call `parse_structured()` with `DOSSIER_PERSONAL_SCHEMA`.
6. Merge generic + personal dicts into final dossier. Continue pipeline as before.

### Cost Impact
Generic call: ~1500–2000 output tokens (expensive). Personal call: ~300–500 output tokens (cheap). For a company researched by N users, saves (N−1) generic calls.

**Redis memory impact**: ~2KB per cached domain. At 500 unique domains = ~1MB. At 5,000 domains = ~10MB. Negligible relative to typical Redis capacity.

### Cache Invalidation
- **TTL-based**: 7 days, auto-expires
- **Input-hash based**: Company data changes produce a new hash, new cache entry (old one expires via TTL)
- **Manual**: `DELETE /api/v1/admin/cache/dossier/{domain}` — clears all cached entries for the domain (all hashes). Does **not** trigger regeneration — next user request will regenerate. Returns `{"deleted": N}`.

### Log Events
- `dossier_cache.hit` — cache hit (detail: domain, hash)
- `dossier_cache.miss` — cache miss, generating (detail: domain, hash)
- `dossier_cache.stampede_wait` — lock contention, waiting (detail: domain)
- `dossier_cache.stampede_timeout` — waited too long, generating anyway (detail: domain)
- `dossier_cache.stored` — new entry cached (detail: domain, hash, size_bytes)
- `dossier_cache.invalidated` — admin manual clear (detail: domain, keys_deleted)

### Key Files
- `app/services/company_service.py` (replace `DOSSIER_SCHEMA`/`DOSSIER_PROMPT` with split versions)
- `app/schemas/company.py` (extend — `CompanyDossierGeneric`, `CompanyDossierPersonal`)
- `app/infrastructure/dossier_cache.py` (new)
- `app/graphs/company_research.py` (modify `generate_dossier_node`)
- `app/api/admin.py` (extend — cache clear endpoint)
- `app/config.py` (extend — `DOSSIER_CACHE_TTL`)

---

## 5. Batch ARQ Cron Jobs

### Overview
Convert sequential per-item cron processing to a coordinator pattern: cron jobs query items, chunk them, and enqueue worker jobs per chunk. Each chunk processes items concurrently via `asyncio.gather` with a semaphore.

### Configuration
Add to `app/config.py`:
- `ARQ_CHUNK_SIZE: int = 10` — items per chunk
- `ARQ_CHUNK_CONCURRENCY: int = 5` — max concurrent items within a chunk
- `ARQ_MAX_CHUNKS_PER_RUN: int = 50` — max chunks enqueued per cron invocation (back-pressure limit: 50 × 10 = 500 items max per run, remainder processed next cycle)

### Coordinator Pattern

**Before:**
```
cron fires -> query all items -> loop one by one -> process each
```

**After:**
```
cron fires -> acquire run lock -> query all items -> cap at MAX_CHUNKS_PER_RUN * CHUNK_SIZE
-> chunk into groups of N -> enqueue one job per chunk -> release run lock
worker picks up chunk job -> asyncio.gather(return_exceptions=True) with semaphore -> process chunk concurrently
```

### Run Lock (Deduplication)
Each coordinator acquires a Redis lock before querying items:

```python
lock_key = f"lock:cron:{job_name}"
acquired = await redis.set(lock_key, "1", nx=True, ex=lock_ttl)
if not acquired:
    logger.info("cron.skipped_overlap", extra={"feature": "arq_batch", "action": job_name})
    return
```

Lock TTL = cron interval (e.g., 5 minutes for follow-ups, 24 hours for daily scout). This prevents overlapping runs from enqueueing duplicate chunks when previous chunks are still processing.

### Changes to `app/worker.py`

**`check_followup_due`** (becomes coordinator):
- Acquire run lock `lock:cron:followup_due` (TTL: 300s)
- Query all due follow-ups
- Cap at `ARQ_MAX_CHUNKS_PER_RUN * ARQ_CHUNK_SIZE` items. If more exist, log a warning with the overflow count.
- Chunk message IDs into groups of `ARQ_CHUNK_SIZE`
- Enqueue `process_followup_chunk` per chunk via `await ctx["redis"].enqueue_job("process_followup_chunk", message_ids=chunk)`

**`process_followup_chunk(ctx, message_ids: list[str])`** (new worker function):
- Takes list of message IDs
- Per-message dedup checks (newer-message, pending-action) remain as individual DB queries per message — these are lightweight SELECTs and batching them would add complexity without meaningful gain
- Outreach graph invocation per message
- `asyncio.gather(*tasks, return_exceptions=True)` with `asyncio.Semaphore(ARQ_CHUNK_CONCURRENCY)`
- After gather: iterate results, log each exception individually with item ID

**`run_daily_scout`** (becomes coordinator):
- Acquire run lock `lock:cron:daily_scout` (TTL: 82800s / 23 hours)
- Query active candidates with DNA
- Cap, chunk, and enqueue `process_scout_chunk` per chunk

**`process_scout_chunk(ctx, candidate_ids: list[str])`** (new worker function):
- Scout pipeline per candidate with semaphore-bounded concurrency

**`run_weekly_analytics`** (becomes coordinator):
- Acquire run lock `lock:cron:weekly_analytics` (TTL: 590400s / ~6.8 days)
- Same pattern, enqueue `process_analytics_chunk`

**`process_analytics_chunk(ctx, candidate_ids: list[str])`** (new worker function):
- Analytics pipeline per candidate with semaphore-bounded concurrency

### Error Handling
Each item in a chunk is processed via:
```python
async def _process_with_semaphore(sem, coro, item_id):
    async with sem:
        try:
            return await coro
        except Exception as e:
            logger.error("chunk.item_failed", extra={
                "feature": "arq_batch",
                "action": "process_item",
                "item_id": item_id,
                "status": "failure",
                "detail": {"error": str(e), "type": type(e).__name__}
            })
            return e
```

`asyncio.gather` is called with `return_exceptions=True` so a single item failure never cancels sibling tasks. After gather, summary is logged:
```
"Chunk complete: 9/10 succeeded, 1 failed"
```

### ARQ Registration
- Coordinator functions remain in `WorkerSettings.cron_jobs` (schedule unchanged)
- Three new chunk processor functions added to `WorkerSettings.functions` list (they are enqueued programmatically, not scheduled)
- Chunk jobs use explicit `job_timeout=600` (10 minutes). Rationale: worst case is `CHUNK_SIZE=10` items in 2 rounds of `CONCURRENCY=5`, each taking up to 30s with OpenAI + retries = ~120s typical, 600s generous ceiling. Adjust if pipeline latency changes.

### Back-Pressure
`ARQ_MAX_CHUNKS_PER_RUN` caps how many chunks a single cron invocation enqueues. If the cron queries 500 items but `MAX_CHUNKS_PER_RUN=50` with `CHUNK_SIZE=10`, it processes the first 500 items. If it queries 800, it processes the first 500 and logs:

```python
logger.warning("cron.overflow", extra={
    "feature": "arq_batch",
    "action": "followup_due",
    "detail": {"total_items": 800, "processing": 500, "deferred": 300}
})
```

Deferred items are picked up in the next cron cycle. This prevents unbounded queue growth with a single worker.

### Scaling Path
One worker: chunks process sequentially from queue, concurrency within each chunk. Add workers: chunks automatically distribute. No code changes.

### Log Events
- `cron.started` — coordinator begins (detail: job name, items found, chunks enqueued)
- `cron.skipped_overlap` — run lock not acquired, skipping
- `cron.overflow` — more items than max chunks can handle (detail: total, processing, deferred)
- `chunk.started` — worker begins chunk (detail: chunk size, job name)
- `chunk.item_failed` — individual item failure (detail: item ID, error)
- `chunk.complete` — chunk finished (detail: succeeded, failed counts, duration_ms)

### Key Files
- `app/worker.py` (modify)
- `app/config.py` (extend)

---

## Cross-Cutting Concerns

### Security Confirmation
All admin endpoints (`/api/v1/admin/*`) are protected by the existing `require_admin` dependency which validates JWT tokens and checks the user's `is_admin` flag. No changes needed — documenting for completeness.

### Testing
Each feature gets its own test file following existing patterns:
- `tests/test_waitlist_invites.py` — invite flow, batch semantics, idempotency, quota enforcement, registration hook
- `tests/test_dns_health.py` — pass/fail/timeout scenarios, caching, configurable selectors
- `tests/test_pgbouncer.py` — connection config selection, pool sizing, health check response
- `tests/test_dossier_cache.py` — cache hit/miss, input hash invalidation, stampede lock, TTL expiry
- `tests/test_worker_batching.py` — chunking logic, semaphore concurrency, error isolation, run lock dedup, back-pressure cap

All tests use existing stubs from `tests/conftest.py`. Redis tests use the existing Redis test instance.

### Configuration Summary
New env vars:
| Variable | Default | Feature |
|----------|---------|---------|
| `PGBOUNCER_URL` | `""` | pgBouncer |
| `DOSSIER_CACHE_TTL` | `604800` | OpenAI caching |
| `ARQ_CHUNK_SIZE` | `10` | Batch ARQ |
| `ARQ_CHUNK_CONCURRENCY` | `5` | Batch ARQ |
| `ARQ_MAX_CHUNKS_PER_RUN` | `50` | Batch ARQ |
| `MAX_DAILY_INVITES` | `200` | Waitlist Invites |
| `DKIM_SELECTOR` | `"resend"` | DNS Health |
| `SPF_EXPECTED_INCLUDES` | `["amazonses.com","resend.com"]` | DNS Health |
| `DNS_HEALTH_CACHE_TTL` | `300` | DNS Health |
| `DNS_LOOKUP_TIMEOUT` | `3.0` | DNS Health |

### Dependencies
New pyproject.toml additions:
- `dnspython>=2.6.0` (SPF/DKIM health checks)

### Migrations
- `022_add_waitlist_status.py` (waitlist status, invite_error, invited_at, invite_code_id FK, invite_codes.email, composite index on status+created_at)
