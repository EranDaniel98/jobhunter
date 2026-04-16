# Railway Worker Service Setup

The ARQ worker runs scheduled cron jobs (scout, analytics, follow-ups, news ingest, GitHub retry) and processes background job queues. It's a second Railway service alongside `jobhunter` (the API), sharing the same repo, Dockerfile, and env vars but with a different entrypoint.

## Why a separate service

- ARQ is a long-running asyncio worker, not an HTTP server — a single container can't serve both cleanly.
- Isolates blast radius: if the worker OOMs or crashes in a cron, API stays up.
- Railway's per-service restart, scale, and observability apply independently.

## One-time setup (Railway dashboard)

Railway's CLI doesn't support creating services yet; this is a click-through.

### 1. Create the service

1. Open the [JobHunter Railway project](https://railway.com/project/cc873661-d54c-44b4-acda-975758d196fe).
2. `+ Create` → `GitHub Repo` → select `EranDaniel98/jobhunter`.
3. Name the service **`jobhunter-worker`**.

### 2. Configure the build

In the new service's **Settings** tab:

| Setting | Value |
|---------|-------|
| Source → Root Directory | `/jobhunter/backend` |
| Source → Config Path | `railway.worker.toml` |
| Source → Branch | `main` |
| Build → Builder | Dockerfile (inherited from config) |
| Deploy → Healthcheck Path | (leave blank) |
| Deploy → Restart Policy | On Failure (inherited from config) |

### 3. Set environment variables

In the **Variables** tab, add **all** of these. The two marked `(worker-specific)` are required; the rest mirror the API service.

| Variable | Value / Source |
|----------|----------------|
| `PROCESS_TYPE` *(worker-specific)* | `worker` |
| `PYTHONUNBUFFERED` *(worker-specific)* | `1` |
| `DATABASE_URL` | Reference `${{pgvector.DATABASE_URL}}` or copy from jobhunter service |
| `REDIS_URL` | Reference `${{Redis.REDIS_URL}}` or copy from jobhunter service |
| `OPENAI_API_KEY` | Copy from jobhunter service |
| `NEWSAPI_KEY` | Copy from jobhunter service |
| `HUNTER_API_KEY` | Copy from jobhunter service |
| `RESEND_API_KEY` | Copy from jobhunter service |
| `RESEND_WEBHOOK_SECRET` | Copy from jobhunter service |
| `GITHUB_TOKEN` | Copy from jobhunter service |
| `GITHUB_REPO` | `EranDaniel98/jobhunter` |
| `JWT_SECRET` | Copy from jobhunter service (used by token decode on some code paths) |
| `UNSUBSCRIBE_SECRET` | Copy from jobhunter service |
| `SENDER_EMAIL`, `SENDER_NAME`, `PHYSICAL_ADDRESS` | Copy from jobhunter service |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | Copy from jobhunter service |
| `STRIPE_SECRET_KEY`, `STRIPE_PRICE_EXPLORER`, `STRIPE_PRICE_HUNTER` | Copy from jobhunter service |
| `DKIM_SELECTOR`, `SPF_EXPECTED_INCLUDES` | Copy from jobhunter service |
| `ARQ_CHUNK_SIZE`, `ARQ_CHUNK_CONCURRENCY`, `ARQ_MAX_CHUNKS_PER_RUN` | Copy if overridden, otherwise skip (defaults apply) |
| `SCOUT_QUERIES_MODEL`, `SCOUT_PARSE_MODEL`, `ANALYTICS_INSIGHTS_MODEL` | Optional — defaults to `gpt-4o-mini` |

Do **NOT** set: `PORT` (worker doesn't serve HTTP), `FRONTEND_URL` (worker doesn't render pages).

**Fastest way to copy envs:** In the jobhunter service's Variables tab, use the "Copy as JSON" or "Raw Editor" export, paste into the worker's Variables tab, then add `PROCESS_TYPE=worker` and `PYTHONUNBUFFERED=1`.

### 4. Deploy

Click **Deploy** on the worker service. Watch the logs — expected sequence:

```
Starting Container
INFO:     Redis connected
INFO:     arq_worker_started
```

No migrations, no uvicorn. If you see `alembic upgrade head` or `Uvicorn running`, `PROCESS_TYPE` wasn't set correctly.

## Verifying

Once deployed, confirm the worker is picking up crons:

```bash
# Watch logs for a cron tick (happens every 15 min at :05, :20, :35, :50)
railway logs --service jobhunter-worker | grep cron
```

Expected lines:
- `cron.started` with `action: retry_failed_github_syncs` (bounded, safe)
- `news_ingest.completed` at 08:00 UTC
- `cron.started` with `action: run_daily_scout` at 09:00 UTC
- `cron.started` with `action: run_weekly_analytics` on Mondays at 08:00 UTC

## Deploy ordering on migrations

`PROCESS_TYPE=api` applies migrations. `PROCESS_TYPE=worker` assumes schema already exists. Rules:

- On every merge that includes a migration, deploy the **API first**, then the worker. Railway auto-deploys both on push to `main`, but the worker crashes on startup if a new migration hasn't applied yet — the on-failure restart policy retries every ~30s until the API completes.
- For emergency rollbacks, roll the worker back first, then the API.

## Cost

Each Railway service bills separately. Worker is idle most of the day (short crons + queue processing), so the same hobby plan tier as the API is fine until you have significant traffic.
