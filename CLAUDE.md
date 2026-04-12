# JobSearch Codebase Guide

## 1. Memory System

- Four files at `memory/`: `user.md`, `preferences.md`, `decisions.md`, `people.md`
- Loaded automatically via SessionStart hook — no action needed
- Updated via `/remember <what>` or organic edits mid-session. No auto-update hook.
- Rules: edit in place, date `decisions.md` entries (`## YYYY-MM-DD —`), keep terse, remove stale, no secrets

## 2. Tech Stack

**Backend:** FastAPI 0.115 + SQLAlchemy 2.0 async + asyncpg + pgvector on Postgres 16, Redis 7, ARQ worker, LangGraph pipelines, Pydantic Settings, JWT auth (PyJWT + bcrypt), Stripe billing, Sentry, structlog, Prometheus

**Frontend:** Next.js 15 + React 19 + TanStack Query v5 + shadcn/ui (new-york) + Tailwind v4 + Axios + react-hook-form + zod + Recharts + Playwright + Vitest

**Infra:** Docker Compose (postgres + redis + pgbouncer local dev), Railway deployment, Cloudflare R2 storage, Plausible analytics

## 3. Project Layout

```
jobhunter/
  backend/
    app/api/            — 18 FastAPI routers (one per domain)
    app/services/       — business logic layer
    app/models/         — 18 SQLAlchemy ORM models (TimestampMixin base)
    app/schemas/        — Pydantic request/response schemas
    app/infrastructure/ — external client adapters (Protocol-based)
    app/graphs/         — 7 LangGraph state machine pipelines
    app/events/         — event bus (in-process + Redis Streams)
    app/middleware/     — 6 Starlette middlewares
    app/worker.py       — ARQ async worker + cron schedule
    app/config.py       — Pydantic Settings, loads from backend/.env
    alembic/            — 23 sequential migration versions
    tests/              — ~110 pytest files (flat, no subdirs)
  frontend/
    src/app/            — App Router (4 route groups: auth, dashboard, marketing, onboarding)
    src/components/     — by domain (ui/, layout/, companies/, analytics/, etc.)
    src/lib/api/        — Axios client + 14 domain API modules
    src/lib/hooks/      — 12 TanStack Query hook files (mirror api/ modules)
    src/lib/schemas/    — Zod validation schemas
    src/lib/types.ts    — central TypeScript interfaces (~450 lines)
    src/providers/      — AuthContext + QueryProvider
    e2e/                — 8 Playwright spec files
```

## 4. Backend Conventions

- **Layering:** Router → Service → Model. Routers = HTTP concerns only; services = business logic; models = pure ORM.
- **DI:** `Depends()` throughout. Core deps in `app/dependencies.py`: `get_db`, `get_current_candidate`, `get_current_admin`.
- **Infrastructure:** External clients implement `@runtime_checkable Protocol` from `app/infrastructure/protocols.py`. Tests swap via module-level singletons.
- **LangGraph:** TypedDict state schemas, checkpointed to Postgres.
- **Event bus:** In-process handlers + Redis Streams. Falls back gracefully if Redis is down.
- **Quota system:** Redis Lua atomic INCR-with-EXPIRE per candidate/type/date. Limits defined in `app/plans.py`.
- **pgBouncer:** Detected via `PGBOUNCER_URL`; pool drops to 5+5. No SAVEPOINTs in that mode.
- **Config:** `Settings(BaseSettings)` in `app/config.py`. Loads `backend/.env` then `jobhunter/.env`.

## 5. Frontend Conventions

- All pages use `"use client"` — zero RSC data fetching. Everything via TanStack Query hooks.
- **Hook pattern:** `src/lib/hooks/use-<domain>.ts` calls `src/lib/api/<domain>.ts`.
- **Auth:** Custom AuthContext, JWT in localStorage, Axios interceptor for silent refresh, client-side route guards.
- **Forms:** react-hook-form + zod resolver. Schemas in `src/lib/schemas/`.
- **Real-time:** `useWebSocket` hook, typed events, debounced `invalidateQueries`, exponential backoff reconnect.
- **UI:** shadcn/ui primitives + domain components. Lucide icons. Geist fonts. next-themes dark/light.
- No hand-written CSS outside `globals.css`. All Tailwind utilities.
- No OpenAPI codegen — hand-written API functions typed against `src/lib/types.ts`.

## 6. Testing

| Layer | Command | Runner | Count | Notes |
|-------|---------|--------|-------|-------|
| Backend | `uv run pytest` | pytest-asyncio (auto mode) | ~110 tests flat | Coverage 85%. `conftest.py` creates `_test` DB, provides `client` fixture with all stubs |
| Frontend unit | `npm run test` | Vitest + testing-library + happy-dom | 11 tests | In `__tests__/` subdirs |
| Frontend E2E | `npm run test:e2e` | Playwright, Chromium only | 8 specs | In `e2e/` |

**CI gates:** backend coverage ≥60%, mypy baseline ≤96 errors, `npm audit --audit-level=high`

## 7. Run Commands

```bash
# Backend (from jobhunter/backend/)
uv run pytest                              # tests
uv run pytest --cov=app --cov-report=term  # + coverage
uv run ruff check app/                     # lint
uv run ruff format app/                    # format
uv run mypy app/ --ignore-missing-imports  # type check
uv run alembic upgrade head                # migrate
uv run uvicorn app.main:app --reload       # dev server

# Frontend (from jobhunter/frontend/)
npm run test                               # vitest
npm run test:e2e                           # playwright
npm run lint                               # eslint
npm run build                              # next build
npm run dev                                # next dev

# Docker (from jobhunter/)
docker compose up -d                       # start postgres + redis
docker compose down                        # stop
```

## 8. Linting & Formatting

- **Backend:** Ruff (line-length 120, rules E/F/W/I/UP/B/SIM/RUF, B008 ignored for `Depends`). mypy with pydantic plugin, non-strict.
- **Frontend:** ESLint v9 flat config (next/core-web-vitals + typescript). No Prettier.
- **PostToolUse hook:** auto-runs `ruff format` + `ruff check` on `.py` files after every edit.

## 9. Git Conventions

- Conventional Commits: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `test`, `style`
- `release.yml` parses these for changelogs

## 10. Deployment

| Environment | URL | How |
|-------------|-----|-----|
| Production | `api.hunter-job.com` | Railway — `railway up --service jobhunter` in CI |
| Staging | on-demand Railway env | Same command, different service target |

- Health check: `GET /api/v1/health`

## 11. CI/CD Reference

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci.yml` | PR / push | backend lint/format/mypy/test/audit + frontend test/lint/build/audit + E2E |
| `deploy.yml` | CI green | gates on CI, railway up, health check poll |
| `security.yml` | schedule | Trivy image+fs scan, pip-audit, npm-audit, SBOM |
| `backup.yml` | daily 3am UTC | pg_dump → R2, 30-day retention |
| `release.yml` | `v*` tag | grouped changelog from conventional commits |

## 12. Tooling Gaps (Windows / Git Bash)

- No `jq` — use `sed` or `python -c 'import json,sys;...'` for JSON in shell scripts
- Windows junctions need PowerShell `.NET`, not `cmd /c mklink` (path translation breaks in Git Bash)
- Python subprocess resolves to WSL bash — use bash-level invocation in hook scripts

## 13. Slash Commands

| Command | Purpose |
|---------|---------|
| `/preflight <task>` | Pre-design discipline check before non-trivial changes |
| `/retro` | Self-evaluation before declaring done |
| `/remember <what>` | Save fact to project memory |
| `/typecheck` | Full-project type check + lint |
| `/pr` | Create pull request with generated description |
