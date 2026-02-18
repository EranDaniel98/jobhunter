# JobHunter AI

**AI-powered job search automation platform** — intelligent company discovery, personalized outreach, and career intelligence.

JobHunter AI is a semi-automated platform that combines AI intelligence with human judgment. The system discovers opportunities, researches companies, and drafts personalized outreach — but every action goes through you first.

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              FastAPI Backend             │
                    │                                         │
  ┌─────────┐      │  ┌──────────┐  ┌──────────┐  ┌───────┐ │
  │ Frontend │◄────►│  │  Auth    │  │  Resume   │  │Company│ │
  │ (planned)│      │  │  System  │  │  Parser   │  │Finder │ │
  └─────────┘      │  └──────────┘  └──────────┘  └───────┘ │
                    │  ┌──────────┐  ┌──────────┐  ┌───────┐ │
                    │  │ Outreach │  │ Contact   │  │Analyt.│ │
                    │  │ Drafter  │  │ Finder    │  │Engine │ │
                    │  └──────────┘  └──────────┘  └───────┘ │
                    └──────────┬──────────┬──────────┬────────┘
                               │          │          │
              ┌────────────────┼──────────┼──────────┼────────────┐
              │                ▼          ▼          ▼            │
              │  ┌──────────┐  ┌──────┐  ┌──────┐  ┌──────────┐  │
              │  │PostgreSQL│  │Redis │  │OpenAI│  │Hunter.io │  │
              │  │+ pgvector│  │      │  │GPT-4o│  │          │  │
              │  └──────────┘  └──────┘  └──────┘  └──────────┘  │
              └───────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI, Pydantic v2, Uvicorn |
| **Database** | PostgreSQL + pgvector (vector similarity search) |
| **Cache** | Redis (rate limiting, token blacklist, deduplication) |
| **AI** | OpenAI GPT-4o (structured output), text-embedding-3-large |
| **Email Discovery** | Hunter.io (domain search, email finder, verification) |
| **Email Sending** | Resend (transactional email with webhook tracking) |
| **Auth** | JWT (PyJWT) with access + refresh tokens |
| **ORM** | SQLAlchemy 2.0 async |
| **Migrations** | Alembic |
| **Container** | Docker Compose |
| **Package Manager** | uv |

## Features

- **Resume Intelligence** — Upload PDF/DOCX, AI extracts skills taxonomy with explicit/transferable/adjacent categorization
- **Candidate DNA** — Vector representation of your professional identity for semantic company matching
- **Company Discovery** — Hunter.io integration for finding target companies with AI-computed fit scores
- **Company Dossier** — AI-generated research briefs with culture analysis, interview prep, and compensation data
- **Contact Finder** — Discover decision-makers with email verification and priority scoring
- **Outreach Drafting** — GPT-4o personalized emails referencing real experience and company specifics
- **Email Sequences** — 4-message outreach sequences (initial, followup, followup, breakup)
- **Compliance** — Daily send limits, suppression lists, CAN-SPAM unsubscribe links, webhook tracking
- **Analytics** — Pipeline funnel and outreach performance metrics

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys: OpenAI, Hunter.io, Resend

### Setup

```bash
# Clone and navigate
git clone https://github.com/EranDaniel98/jobhunter.git
cd jobhunter

# Copy environment template and add your API keys
cp .env.example .env
# Edit .env with your keys

# Start infrastructure
docker compose up -d

# Install dependencies
cd backend
uv sync --all-extras

# Run migrations
uv run alembic upgrade head

# Start the server
uv run uvicorn app.main:app --reload
```

### Running Tests

```bash
cd backend
uv run pytest tests/ -x -q
```

Tests use lightweight stubs — no real API keys needed.

## API Overview

All endpoints are under `/api/v1/`. Full OpenAPI docs at `/docs` when running.

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | Create account |
| `POST /auth/login` | Get JWT tokens |
| `POST /candidates/resume` | Upload & parse resume |
| `GET /candidates/me/dna` | Get candidate DNA profile |
| `POST /companies/add` | Add company by domain |
| `POST /companies/discover` | AI-powered company discovery |
| `GET /companies/{id}/dossier` | Get AI research dossier |
| `POST /outreach/draft` | AI-draft personalized email |
| `POST /outreach/{id}/send` | Send approved email |
| `GET /analytics/funnel` | Pipeline analytics |
| `GET /health` | Service health check |

## Project Structure

```
jobhunter/
├── docker-compose.yml          # PostgreSQL + pgvector, Redis
└── backend/
    ├── app/
    │   ├── api/                # FastAPI route handlers
    │   ├── models/             # SQLAlchemy ORM models
    │   ├── schemas/            # Pydantic request/response types
    │   ├── services/           # Business logic layer
    │   ├── infrastructure/     # External clients (OpenAI, Hunter, Resend)
    │   ├── middleware/         # Logging, error handling, request ID
    │   └── utils/              # JWT, retry logic
    ├── alembic/                # Database migrations
    ├── tests/                  # 28 async tests
    └── scripts/                # Dev tools (seeding, env check)
```

## Design Philosophy

1. **Semi-Automated** — AI suggests, human approves. No emails sent without explicit confirmation.
2. **Resume is Source of Truth** — All matching and personalization builds from your real documented experience.
3. **Compound Learning** — The system gets smarter with every interaction cycle.
4. **SaaS-Ready** — Tenant-aware data model, API versioning, protocol-based infrastructure.

## Roadmap

- [ ] Frontend (React/Next.js)
- [ ] LangGraph orchestration for multi-step AI workflows
- [ ] Background job queue (ARQ/Celery)
- [ ] WebSocket notifications
- [ ] Job board scraping (JobSpy)
- [ ] Interview preparation module
- [ ] A/B testing for outreach effectiveness
- [ ] Resume tailoring with tracked-changes diffs

## License

Private — All rights reserved.
