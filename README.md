# JobHunter AI

![CI](https://github.com/EranDaniel98/jobhunter/actions/workflows/ci.yml/badge.svg)
![Security](https://github.com/EranDaniel98/jobhunter/actions/workflows/security.yml/badge.svg)

**AI-powered job search automation platform** - intelligent company discovery, personalized outreach, and career intelligence.

JobHunter AI is a semi-automated platform that combines AI intelligence with human judgment. The system discovers opportunities, researches companies, and drafts personalized outreach - but every action goes through you first.

## Architecture

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                      Next.js Frontend                           │
  │  Dashboard · Companies · Outreach · Resume · Analytics · Admin  │
  └───────────────────────────┬─────────────────────────────────────┘
                              │ REST API (/api/v1/)
  ┌───────────────────────────▼─────────────────────────────────────┐
  │                       FastAPI Backend                            │
  │                                                                  │
  │  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────────┐  │
  │  │  Auth &   │  │  Resume  │  │ Company │  │    Admin         │  │
  │  │  Invites  │  │  Parser  │  │ Finder  │  │  Dashboard       │  │
  │  └──────────┘  └──────────┘  └─────────┘  └──────────────────┘  │
  │  ┌──────────┐  ┌─────────┐  ┌─────────┐  ┌──────────────────┐  │
  │  │ Outreach │  │ Contact │  │ Analyt. │  │ Email Broadcast  │  │
  │  │ Drafter  │  │ Finder  │  │ Engine  │  │ & Audit Log      │  │
  │  └──────────┘  └─────────┘  └─────────┘  └──────────────────┘  │
  └──────────┬──────────┬──────────┬──────────┬─────────────────────┘
             │          │          │          │
  ┌──────────▼──────────▼──────────▼──────────▼─────────────────────┐
  │  ┌──────────┐  ┌───────┐  ┌────────┐  ┌───────────┐  ┌──────┐  │
  │  │PostgreSQL│  │ Redis │  │ OpenAI │  │ Hunter.io │  │Resend│  │
  │  │+ pgvector│  │       │  │ GPT-4o │  │           │  │      │  │
  │  └──────────┘  └───────┘  └────────┘  └───────────┘  └──────┘  │
  └─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui, React Query |
| **API** | FastAPI, Pydantic v2, Uvicorn |
| **Database** | PostgreSQL + pgvector (vector similarity search) |
| **Cache** | Redis (rate limiting, token blacklist, deduplication) |
| **AI** | OpenAI GPT-4o (structured output), text-embedding-3-large |
| **Email Discovery** | Hunter.io (domain search, email finder, verification) |
| **Email Sending** | Resend (transactional email with webhook tracking) |
| **Auth** | JWT (PyJWT) with access + refresh tokens, invite-only registration |
| **ORM** | SQLAlchemy 2.0 async |
| **Migrations** | Alembic (5 migrations) |
| **Container** | Docker Compose |
| **Package Managers** | uv (backend), npm (frontend) |

## Features

### Core
- **Resume Intelligence** - Upload PDF/DOCX, AI extracts skills taxonomy with explicit/transferable/adjacent categorization
- **Candidate DNA** - Vector representation of your professional identity for semantic company matching
- **Company Discovery** - Hunter.io integration for finding target companies with AI-computed fit scores
- **Company Dossier** - AI-generated research briefs with culture analysis, interview prep, and compensation data
- **Contact Finder** - Discover decision-makers with email verification and priority scoring
- **Outreach Drafting** - GPT-4o personalized emails referencing real experience and company specifics
- **Email Sequences** - 4-message outreach sequences (initial, followup, followup, breakup)
- **Compliance** - Daily send limits, suppression lists, CAN-SPAM unsubscribe links, webhook tracking
- **Analytics** - Pipeline funnel and outreach performance metrics

### Admin Dashboard
- **System overview** - Total users, companies, messages, contacts, invites, active users (7d/30d)
- **User management** - List, search, paginate, toggle admin/active, delete with cascade, user detail drawer
- **User suspension** - Suspend/activate users; suspended users blocked at login (403)
- **Activity feed** - Cross-tenant event stream with relative timestamps and event icons
- **Admin audit log** - Tracks toggle_admin, toggle_active, delete_user, broadcast_sent actions
- **CSV export** - Download all users with aggregated stats
- **Broadcast email** - Send to all active opted-in users with confirmation dialog
- **Registration trend** - 30-day chart with auto-refresh
- **Invite chain** - Tracks who invited whom
- **Top users** - Leaderboard by messages sent or companies added

### Settings
- **Profile management** - Name, headline, location, target roles/industries/locations, salary range
- **Notification preferences** - Opt in/out of platform emails (affects broadcast)
- **Invite system** - Generate invite links, filter by status (active/used/expired), scrollable list

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 18+
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

# Backend
cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend (117 tests)
cd backend
uv run pytest tests/ -x -q

# Frontend build check
cd frontend
npm run build
```

Tests use lightweight stubs - no real API keys needed.

## API Overview

All endpoints are under `/api/v1/`. Full OpenAPI docs at `/docs` when running.

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | Create account (invite required) |
| `POST /auth/login` | Get JWT tokens |
| `GET /auth/me` | Get profile (includes preferences) |
| `PATCH /auth/me` | Update profile & preferences |
| `POST /candidates/resume` | Upload & parse resume |
| `GET /candidates/me/dna` | Get candidate DNA profile |
| `POST /companies/add` | Add company by domain |
| `POST /companies/discover` | AI-powered company discovery |
| `GET /companies/{id}/dossier` | Get AI research dossier |
| `POST /outreach/draft` | AI-draft personalized email |
| `POST /outreach/{id}/send` | Send approved email |
| `DELETE /outreach/{id}` | Delete draft message |
| `GET /analytics/funnel` | Pipeline analytics |
| `GET /admin/overview` | System stats (admin) |
| `GET /admin/users` | User list with search (admin) |
| `GET /admin/users/export` | CSV export (admin) |
| `PATCH /admin/users/{id}/active` | Suspend/activate user (admin) |
| `GET /admin/activity` | Activity feed (admin) |
| `GET /admin/audit-log` | Audit log (admin) |
| `POST /admin/broadcast` | Send broadcast email (admin) |
| `POST /invites` | Generate invite code |
| `GET /health` | Service health check |

## Project Structure

```
jobhunter/
├── docker-compose.yml              # PostgreSQL + pgvector, Redis
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI route handlers
│   │   │   ├── auth.py             # Register, login, profile
│   │   │   ├── admin.py            # Admin dashboard endpoints
│   │   │   ├── companies.py        # Company CRUD & discovery
│   │   │   ├── outreach.py         # Message drafting & sending
│   │   │   └── invites.py          # Invite code management
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic request/response types
│   │   ├── services/               # Business logic layer
│   │   ├── infrastructure/         # External clients (OpenAI, Hunter, Resend)
│   │   ├── middleware/             # Logging, error handling, request ID
│   │   └── utils/                  # JWT, retry logic
│   ├── alembic/                    # 5 database migrations
│   ├── tests/                      # 117 async tests
│   └── scripts/                    # Dev tools (seeding, env check)
└── frontend/
    └── src/
        ├── app/                    # Next.js pages
        │   ├── (auth)/             # Login, register
        │   └── (dashboard)/        # Dashboard, companies, outreach,
        │                           # resume, analytics, admin, settings
        ├── components/
        │   ├── admin/              # Admin dashboard components
        │   ├── shared/             # Reusable components
        │   └── ui/                 # shadcn/ui primitives
        ├── lib/
        │   ├── api/                # Typed API clients
        │   └── hooks/              # React Query hooks
        └── providers/              # Auth context
```

## Design Philosophy

1. **Semi-Automated** - AI suggests, human approves. No emails sent without explicit confirmation.
2. **Resume is Source of Truth** - All matching and personalization builds from your real documented experience.
3. **Compound Learning** - The system gets smarter with every interaction cycle.
4. **SaaS-Ready** - Tenant-aware data model, API versioning, protocol-based infrastructure.

## Roadmap

- [x] Frontend (Next.js + React)
- [x] Invite-only registration
- [x] Admin dashboard with user management
- [x] Activity feed & audit log
- [x] Broadcast email & notification preferences
- [ ] LangGraph orchestration for multi-step AI workflows
- [ ] Background job queue (ARQ/Celery)
- [ ] WebSocket notifications
- [ ] Job board scraping (JobSpy)
- [ ] Interview preparation module
- [ ] A/B testing for outreach effectiveness
- [ ] Resume tailoring with tracked-changes diffs

## License

Private - All rights reserved.
