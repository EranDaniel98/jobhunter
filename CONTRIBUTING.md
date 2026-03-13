# Contributing to JobHunter AI

## Prerequisites

- **Python 3.12+** with [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 22+** with npm
- **Docker & Docker Compose** (for PostgreSQL + Redis)
- **Git**

## Quick Start

### 1. Start infrastructure

```bash
cd jobhunter
docker compose up -d postgres redis
```

### 2. Backend setup

```bash
cd backend

# Install dependencies
uv sync --all-extras

# Copy environment file and fill in secrets
cp .env.example .env
# Edit .env - at minimum set JWT_SECRET and API keys

# Run database migrations
uv run alembic upgrade head

# Start the server
uv run uvicorn app.main:app --reload --port 8000
```

### 3. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.production .env.local
# Edit .env.local - set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Start dev server
npm run dev
```

The app is now running at http://localhost:3000 with the API at http://localhost:8000.

## Testing

### Backend (pytest)

```bash
cd backend

# Run all tests
uv run python -m pytest tests/ -x -q

# Run a specific test file
uv run python -m pytest tests/test_companies.py -xvs

# Run with coverage
uv run python -m pytest tests/ --cov=app --cov-report=html
```

Tests use **lightweight stubs** for external APIs (OpenAI, Hunter.io, Resend) - no real API calls are made. See `tests/conftest.py` for stub implementations.

### Frontend (Playwright E2E)

```bash
cd frontend

# Install browsers (first time only)
npx playwright install chromium

# Run E2E tests (requires backend + frontend running with seed data)
npm run test:e2e

# Run with UI
npm run test:e2e:ui
```

## Architecture

Key patterns used throughout the codebase:

- **Protocol-based DI** - External clients (OpenAI, Hunter, Resend) implement protocols, swapped with stubs in tests
- **Redis helpers** - Atomic INCR for daily limits (email, API quotas), graceful degradation via `redis_safe_*` helpers
- **structlog** - Structured JSON logging with request ID context
- **Singleton clients** - `dependencies.py` manages single instances of API clients
- **LangGraph** - Resume processing pipeline with PostgreSQL-backed checkpointing

See [docs/architecture-decisions.md](docs/architecture-decisions.md) for detailed ADRs.

## Adding Endpoints

1. Define the Pydantic schema in `app/schemas/<resource>.py`
2. Create or extend the router in `app/api/<resource>.py`
3. Add business logic in `app/services/<resource>_service.py`
4. Register the router in `app/main.py`
5. Add tests in `tests/test_<resource>.py`
6. Run the full test suite to verify: `uv run python -m pytest tests/ -x -q`

## Adding Migrations

```bash
cd backend

# Create a new migration
uv run alembic revision --autogenerate -m "NNN_short_description"

# Apply migrations
uv run alembic upgrade head
```

We use **numeric revision prefixes** (001, 002, ...) for clear ordering.

## Environment Variables

See [`backend/.env.example`](backend/.env.example) for all available variables with descriptions.

## Sentry Setup

1. Create a free account at https://sentry.io
2. Create a new project (select **FastAPI** for backend, **Next.js** for frontend)
3. Copy the DSN from the project settings
4. Set `SENTRY_DSN` in `backend/.env` (for the backend)
5. Set `NEXT_PUBLIC_SENTRY_DSN` in `frontend/.env.local` (for the frontend)
6. Restart the servers - Sentry will auto-capture unhandled exceptions

## Email Domain Setup

See [docs/email-domain-setup.md](docs/email-domain-setup.md) for step-by-step Resend domain verification.
