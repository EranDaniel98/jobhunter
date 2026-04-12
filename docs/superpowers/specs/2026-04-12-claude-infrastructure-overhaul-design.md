# Claude Infrastructure Overhaul — Design Spec

**Date:** 2026-04-12
**Status:** Approved
**Scope:** Claude Code configuration, hooks, slash commands, permissions, and project CLAUDE.md

---

## Problem

Claude rediscovers codebase patterns every session because CLAUDE.md only describes the memory system — nothing about the tech stack, conventions, testing, or architecture. Workflow automation is minimal (only a SessionStart hook). The permissions file has 151 stale entries including a `Bash(*)` wildcard that makes all others redundant, plus a hardcoded JWT token. There's no auto-formatting, no auto-linting, and no slash commands for common workflows like type-checking or PR creation.

## Goals

1. **Claude knows the project deeply from turn one** — comprehensive CLAUDE.md with architecture, conventions, testing patterns, and run commands
2. **Automated code quality on every edit** — format + lint fires after backend file edits (Ruff, near-instant); frontend lint deferred to slash command (ESLint is too slow for per-edit)
3. **Clean permissions** — replace 151 entries with ~40 specific patterns, remove `Bash(*)` wildcard
4. **Useful slash commands** — `/typecheck`, `/pr` join existing `/preflight`, `/retro`, `/remember`

## Non-Goals

- Changing CI/CD workflows (`.github/workflows/`)
- Adding Prettier to the frontend (no config exists, not introducing one)
- Per-edit type checking (too slow for both mypy and tsc)
- Modifying the memory system (working well as-is)

---

## Deliverable 1: CLAUDE.md Rewrite

**File:** `CLAUDE.md` (project root)
**Size target:** ~200 lines / ~3000 tokens

### Sections

1. **Persistent Memory System** — trimmed version of current content (keep: four files, SessionStart hook, `/remember`, update discipline; remove: historical context about Stop hook attempts that's already in `memory/decisions.md`)

2. **Tech Stack** — one paragraph:
   - Backend: FastAPI 0.115 + SQLAlchemy 2.0 async + asyncpg + pgvector on Postgres 16, Redis 7, ARQ worker, LangGraph pipelines, Pydantic Settings, JWT auth (PyJWT + bcrypt), Stripe billing, Sentry, structlog, Prometheus metrics
   - Frontend: Next.js 15 + React 19 + TanStack Query v5 + shadcn/ui (new-york) + Tailwind v4 + Axios + react-hook-form + zod + Recharts + Playwright + Vitest
   - Infra: Docker Compose (postgres + redis + pgbouncer for local dev), Railway for deployment, Cloudflare R2 for storage, Plausible for analytics

3. **Project Layout** — directory tree with one-line descriptions:
   ```
   jobhunter/
     backend/
       app/api/          — 18 FastAPI routers (one per domain)
       app/services/     — business logic (called by routers)
       app/models/       — SQLAlchemy ORM models (18 models, TimestampMixin base)
       app/schemas/      — Pydantic request/response schemas
       app/infrastructure/ — external client adapters (Protocol-based)
       app/graphs/       — 7 LangGraph state machine pipelines
       app/events/       — event bus (in-process + Redis Streams)
       app/middleware/    — 6 Starlette middlewares
       app/worker.py     — ARQ async worker + cron schedule
       alembic/          — 23 sequential migration versions
       tests/            — ~110 pytest files (flat, no subdirs)
     frontend/
       src/app/          — Next.js App Router (4 route groups: auth, dashboard, marketing, onboarding)
       src/components/   — organized by domain (ui/, layout/, companies/, analytics/, etc.)
       src/lib/api/      — Axios client + 14 domain API modules
       src/lib/hooks/    — 12 TanStack Query hook files (mirror api/ modules)
       src/lib/schemas/  — Zod validation schemas
       src/lib/types.ts  — central TypeScript interfaces (~450 lines)
       src/providers/    — AuthContext + QueryProvider
       e2e/              — 8 Playwright spec files
   ```

4. **Backend Conventions**
   - Router → Service → Model layering. Routers handle HTTP concerns (status codes, response models). Services handle business logic. Models are pure ORM.
   - DI via `Depends()`. Core deps in `app/dependencies.py`: `get_db`, `get_current_candidate`, `get_current_admin`, singleton external clients.
   - All external clients implement `@runtime_checkable Protocol` from `app/infrastructure/protocols.py`. Tests swap them via module-level `_*_client` variable injection.
   - LangGraph pipelines use `TypedDict` state schemas, checkpointed to Postgres for crash recovery.
   - Event bus: in-process handlers + Redis Streams persistence. Falls back if Redis unreachable.
   - Quota system: Redis Lua atomic INCR-with-EXPIRE per `quota:{candidate_id}:{type}:{date}`. Limits from `app/plans.py` tier definitions.
   - pgBouncer awareness: `database.py` detects `PGBOUNCER_URL`, drops pool to 5+5. No SAVEPOINTs.
   - Config: `app/config.py` — single `Settings(BaseSettings)` class, loads from `backend/.env` then `jobhunter/.env`.

5. **Frontend Conventions**
   - All pages are `"use client"` — zero RSC data fetching. Everything uses TanStack Query hooks.
   - Hook pattern: `src/lib/hooks/use-<domain>.ts` calls functions from `src/lib/api/<domain>.ts`. One hook file per API module.
   - Auth: custom `AuthContext` in `src/providers/auth-provider.tsx`. JWT tokens in localStorage. Axios interceptor handles silent refresh. Route protection via client-side layout guards (no middleware).
   - Forms: react-hook-form + zod resolver everywhere. Schemas in `src/lib/schemas/`.
   - Real-time: `useWebSocket` hook with typed events, debounced `invalidateQueries` on change. Exponential backoff reconnect.
   - UI: shadcn/ui primitives in `src/components/ui/`, domain components co-located by feature. Lucide icons. Geist fonts. Dark/light via next-themes.
   - No hand-written CSS outside `globals.css`. All styling via Tailwind utility classes.
   - No OpenAPI codegen — API functions are hand-written, typed against `src/lib/types.ts`.

6. **Testing**
   - Backend: `uv run pytest` — pytest-asyncio (auto mode), `conftest.py` creates `_test` database, provides `client` fixture (httpx AsyncClient + ASGI transport + all stubs wired). Coverage target 85%. ~110 test files, flat in `tests/`.
   - Frontend unit: `npm run test` — Vitest + testing-library + happy-dom. 11 test files in `__tests__/` subdirs.
   - Frontend E2E: `npm run test:e2e` — Playwright, Chromium only, 8 spec files in `e2e/`.
   - CI thresholds: backend coverage 60% (CI) / 85% (local), mypy baseline 96 errors max, frontend `npm audit --audit-level=high`.

7. **Run Commands**
   ```
   # Backend (from jobhunter/backend/)
   uv run pytest                              # tests
   uv run pytest --cov=app --cov-report=term  # tests + coverage
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

8. **Linting & Formatting**
   - Backend: Ruff (line-length 120, rules E/F/W/I/UP/B/SIM/RUF, B008 ignored for FastAPI `Depends`). mypy with pydantic plugin, non-strict.
   - Frontend: ESLint v9 flat config (next/core-web-vitals + typescript). No Prettier.
   - A PostToolUse hook auto-runs `ruff format` + `ruff check` on backend `.py` files after every edit. Frontend linting is manual via `/typecheck`.

9. **Git Conventions** — Conventional Commits: `type(scope): description`. Types: feat, fix, docs, chore, ci, refactor, test, style. `release.yml` parses these for changelogs.

10. **Deployment** — Railway. Production: `api.hunter-job.com`. Staging: on-demand Railway environment. Deploy via `railway up --service jobhunter` in CI. Health check: `GET /api/v1/health`.

11. **CI/CD Reference**
    - `ci.yml`: backend lint/format/mypy/test/audit + frontend test/lint/build/audit + E2E
    - `deploy.yml`: gates on CI, `railway up`, health check poll
    - `security.yml`: Trivy (image + fs), pip-audit, npm-audit, SBOM generation
    - `backup.yml`: daily 3am UTC pg_dump → R2, 30-day retention
    - `release.yml`: on `v*` tag, generates grouped changelog from conventional commits

12. **Tooling Gaps** — no `jq` in Git Bash (use sed/python), Windows junctions need PowerShell `.NET`, Python subprocess resolves to WSL bash (use bash-level invocation in hooks).

13. **CI/CD for Claude Workflow** — `/preflight`, `/retro`, `/remember`, `/typecheck`, `/pr`. Hook test harness at `.claude/hooks/test-all.sh`.

---

## Deliverable 2: PostToolUse Format + Lint Hook

**File:** `.claude/hooks/post-edit.sh`
**Settings:** `.claude/settings.json` — add PostToolUse entry with matcher `Write|Edit`

### Behavior

1. Extract `file_path` from stdin JSON (tool_input for Edit, tool_response for Write)
2. If file ends in `.py` and is under `jobhunter/backend/`:
   - Run `ruff format <file>` (silent on success)
   - Run `ruff check <file> --output-format text`
   - If lint warnings exist, output them as `additionalContext` so Claude sees and fixes them
3. If file ends in `.ts`/`.tsx`/`.js`/`.jsx`: skip (ESLint too slow for per-edit)
4. All other file types: skip
5. Exit 0 always (never block edits)

### Why backend-only

Ruff runs in ~50ms per file — invisible. ESLint takes 2-5s per file and needs the full Next.js config resolution. The latency tax on every frontend edit would be noticeable and annoying. Frontend linting is available via `/typecheck` on demand.

---

## Deliverable 3: Slash Commands

### `/typecheck`

**File:** `.claude/commands/typecheck.md`

Runs type checking + linting for the full project:
- Backend: `cd jobhunter/backend && uv run mypy app/ --ignore-missing-imports` + `uv run ruff check app/`
- Frontend: `cd jobhunter/frontend && npx tsc --noEmit` + `npm run lint`

Reports results and offers to fix any issues found.

### `/pr`

**File:** `.claude/commands/pr.md`

Creates a pull request:
1. Determine base branch (usually `main`)
2. Gather all commits since diverging from base (`git log main..HEAD`)
3. Gather full diff summary (`git diff main...HEAD --stat`)
4. Generate PR title (short, conventional-commit style) and body (summary bullets + test plan)
5. Push branch if needed, create PR via `gh pr create`

---

## Deliverable 4: Permissions Cleanup

**File:** `.claude/settings.local.json`

Replace the `permissions.allow` array contents. Remove `Bash(*)` wildcard. New list (~40 entries):

```json
[
  "Bash(git:*)",
  "Bash(gh:*)",
  "Bash(rtk:*)",
  "Bash(uv:*)",
  "Bash(python:*)",
  "Bash(python3:*)",
  "Bash(pip:*)",
  "Bash(npm:*)",
  "Bash(npx:*)",
  "Bash(docker:*)",
  "Bash(docker compose:*)",
  "Bash(railway:*)",
  "Bash(curl:*)",
  "Bash(bash:*)",
  "Bash(powershell.exe:*)",
  "Bash(ls:*)",
  "Bash(cat:*)",
  "Bash(head:*)",
  "Bash(tail:*)",
  "Bash(find:*)",
  "Bash(grep:*)",
  "Bash(wc:*)",
  "Bash(rm:*)",
  "Bash(mkdir:*)",
  "Bash(cp:*)",
  "Bash(mv:*)",
  "Bash(chmod:*)",
  "Bash(echo:*)",
  "Bash(cd:*)",
  "Bash(sort:*)",
  "Bash(xargs:*)",
  "Bash(test:*)",
  "Bash(timeout:*)",
  "Bash(netstat:*)",
  "Bash(taskkill:*)",
  "Bash(nslookup:*)",
  "Bash(touch:*)",
  "Bash(sed:*)",
  "WebSearch",
  "WebFetch(domain:deepwiki.com)",
  "mcp__plugin_context7_context7__query-docs",
  "mcp__plugin_context7_context7__resolve-library-id",
  "mcp__plugin_github_github__list_issues",
  "mcp__plugin_github_github__issue_write",
  "mcp__plugin_github_github__add_issue_comment",
  "mcp__plugin_github_github__get_file_contents",
  "mcp__plugin_claude-mem_mcp-search__search"
]
```

The hardcoded JWT token, stale file references, and one-off commands are all dropped.

---

## Deliverable 5: Hook Test Harness Updates

**File:** `.claude/hooks/test-all.sh`

Add test for the new `post-edit.sh` hook:
- Happy path: feed a `.py` file path, assert exit 0
- Non-Python file: feed a `.tsx` file path, assert exit 0 + no output (skip)
- Lint warning detection: feed a file with a known Ruff violation, assert `additionalContext` contains the warning

---

## Deliverable 6: Memory Update

**File:** `memory/decisions.md`

Add entry for this infrastructure overhaul capturing:
- Why backend-only auto-lint (Ruff speed vs ESLint)
- Why specific permissions over `Bash(*)`
- Why single CLAUDE.md over rules files

---

## Implementation Order

1. CLAUDE.md rewrite (biggest, standalone)
2. PostToolUse hook (post-edit.sh + settings.json update)
3. Slash commands (/typecheck, /pr)
4. Permissions cleanup
5. Hook test harness updates
6. Memory update
7. Commit all
