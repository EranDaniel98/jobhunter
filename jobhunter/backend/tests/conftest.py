import secrets
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.dependencies as _deps
from app.config import settings
from app.dependencies import get_db, get_email_client
from app.infrastructure.database import get_session
from app.infrastructure.redis_client import close_redis, init_redis
from app.main import app
from app.models.base import Base
from app.models.candidate import CandidateDNA
from app.models.invite import InviteCode

# ---------------------------------------------------------------------------
# Lightweight test stubs for external API clients
# ---------------------------------------------------------------------------

class OpenAIStub:
    """Test stub that returns plausible data without hitting real OpenAI."""

    async def parse_structured(self, system_prompt: str, user_content: str, response_schema: dict) -> dict:
        # Detect schema type by checking top-level required keys
        schema_keys = set(response_schema.get("properties", {}).keys())

        # Scout query generation schema (has "queries" key)
        if "queries" in schema_keys:
            return {
                "queries": [
                    "Series B funding AI developer tools",
                    "startup raises round cloud infrastructure",
                ]
            }

        # Scout article parsing schema (companies with company_name)
        companies_items = response_schema.get("properties", {}).get("companies", {}).get("items", {}).get("properties", {})
        if "companies" in schema_keys and "company_name" in companies_items:
            return {
                "companies": [
                    {
                        "company_name": "TechStartup",
                        "estimated_domain": "techstartup.io",
                        "funding_round": "Series B",
                        "amount": "$50M",
                        "industry": "Developer Tools",
                        "description": "AI-powered developer tools platform",
                    },
                    {
                        "company_name": "CloudCorp",
                        "estimated_domain": "cloudcorp.com",
                        "funding_round": "Series A",
                        "amount": "$30M",
                        "industry": "Cloud Infrastructure",
                        "description": "Cloud infrastructure platform for enterprises",
                    },
                ]
            }

        # Company discovery schema
        if "companies" in schema_keys and len(schema_keys) == 1:
            return {
                "companies": [
                    {"domain": "stripe.com", "name": "Stripe", "reason": "Strong fintech fit",
                     "industry": "Financial Technology", "size": "1001-5000",
                     "tech_stack": ["Ruby", "Go", "React"]},
                    {"domain": "plaid.com", "name": "Plaid", "reason": "API-focused fintech",
                     "industry": "Financial Technology", "size": "501-1000",
                     "tech_stack": ["Python", "TypeScript", "Kubernetes"]},
                    {"domain": "vercel.com", "name": "Vercel", "reason": "Developer tools",
                     "industry": "Developer Tools", "size": "201-500",
                     "tech_stack": ["Next.js", "Go", "Rust"]},
                ]
            }

        # Skills extraction schema (has "skills" key with items containing category/proficiency)
        skills_props = response_schema.get("properties", {}).get("skills", {})
        items_props = skills_props.get("items", {}).get("properties", {})
        if "skills" in schema_keys and "category" in items_props and "proficiency" in items_props:
            return {
                "skills": [
                    {"name": "Python", "category": "explicit", "proficiency": "expert",
                     "years_experience": 5.0, "evidence": "5 years professional Python development"},
                    {"name": "FastAPI", "category": "explicit", "proficiency": "advanced",
                     "years_experience": 3.0, "evidence": "Built REST APIs with FastAPI"},
                    {"name": "Leadership", "category": "transferable", "proficiency": "intermediate",
                     "years_experience": 2.0, "evidence": "Led team of 5 engineers"},
                ]
            }

        # Interview prep: company_qa schema
        if "questions" in schema_keys and "tips" in schema_keys:
            return {
                "questions": [
                    {"question": "Tell me about your experience with Python", "suggested_answer": "I have 5 years of professional Python development...", "category": "technical"},
                    {"question": "Why do you want to work here?", "suggested_answer": "I'm drawn to the company's innovative culture...", "category": "culture-fit"},
                ],
                "tips": ["Research the company culture", "Prepare STAR stories"],
            }

        # Interview prep: behavioral schema
        if "stories" in schema_keys:
            return {
                "stories": [
                    {"question": "Tell me about a challenge you overcame", "situation": "At TestCo, we faced a critical production outage.",
                     "task": "I needed to identify the root cause and restore service.",
                     "action": "I led the incident response, identified a memory leak, and deployed a fix.",
                     "result": "Service restored in 30 minutes, implemented monitoring to prevent recurrence."},
                ],
            }

        # Interview prep: technical schema
        if "topics" in schema_keys:
            return {
                "topics": [
                    {"name": "System Design", "questions": [
                        {"question": "Design a URL shortener", "answer": "I would use a hash-based approach with a NoSQL store...", "difficulty": "medium"},
                    ]},
                ],
            }

        # Interview prep: culture_fit schema
        if "values" in schema_keys and "alignment_tips" in schema_keys:
            return {
                "values": ["Innovation", "Collaboration"],
                "alignment_tips": ["Show passion for continuous learning"],
                "questions": [{"question": "How do you handle disagreements?", "suggested_answer": "I approach conflicts with empathy and data..."}],
            }

        # Interview prep: salary_negotiation schema
        if "range" in schema_keys and "talking_points" in schema_keys:
            return {
                "range": {"min": "120k", "max": "180k", "median": "150k"},
                "talking_points": ["Market data supports this range"],
                "counter_strategies": ["Emphasize total compensation package"],
            }

        # Mock interview feedback schema
        if "overall_score" in schema_keys and "strengths" in schema_keys and "improvements" in schema_keys:
            return {
                "overall_score": 7.5,
                "strengths": ["Clear communication", "Good technical depth"],
                "improvements": ["Provide more specific examples", "Ask clarifying questions"],
                "summary": "Good performance overall. Strong technical answers with room for improvement in behavioral responses.",
            }

        # Apply: job parsing schema
        if "required_skills" in schema_keys and "ats_keywords" in schema_keys:
            return {
                "required_skills": ["Python", "FastAPI", "PostgreSQL"],
                "preferred_skills": ["Docker", "Kubernetes"],
                "experience_years": 3,
                "education": "BS Computer Science",
                "responsibilities": ["Build APIs", "Write tests"],
                "ats_keywords": ["Python", "REST API", "microservices", "PostgreSQL"],
            }

        # Apply: resume tips schema
        if "tips" in schema_keys and "readiness_score" in schema_keys:
            return {
                "tips": [
                    {"section": "Skills", "tip": "Add PostgreSQL to your skills section", "priority": "high"},
                    {"section": "Experience", "tip": "Highlight API development projects", "priority": "medium"},
                ],
                "readiness_score": 72.5,
            }

        # Apply: cover letter schema
        if "cover_letter" in schema_keys and len(schema_keys) == 1:
            return {"cover_letter": "Dear Hiring Manager,\n\nI am excited to apply for this position. My experience in Python and FastAPI aligns well with your requirements.\n\nBest regards,\nTest User"}

        # Analytics insights schema
        if "insights" in schema_keys:
            items_props = response_schema.get("properties", {}).get("insights", {}).get("items", {}).get("properties", {})
            if "insight_type" in items_props:
                return {
                    "insights": [
                        {"insight_type": "pipeline_health", "title": "Pipeline Growing",
                         "body": "You have 5 companies in your pipeline, up from 3 last week.",
                         "severity": "success", "data": {"current": 5, "previous": 3}},
                        {"insight_type": "recommendation", "title": "Follow Up Needed",
                         "body": "3 companies haven't received follow-ups in over a week.",
                         "severity": "action_needed", "data": {"company_count": 3}},
                    ],
                }

        # Return a response that satisfies both resume parsing and outreach drafting schemas
        return {
            "name": "Test User",
            "headline": "Software Engineer",
            "experiences": [{"company": "TestCo", "title": "Engineer", "dates": "2020-2024",
                            "description": "Backend development", "achievements": ["Built API"]}],
            "skills": ["Python", "FastAPI"],
            "education": [{"institution": "MIT", "degree": "BS CS", "year": "2020"}],
            "certifications": [],
            "summary": "Experienced engineer.",
            "strengths": ["Python", "APIs", "Databases", "Testing", "Architecture"],
            "gaps": ["Frontend", "Mobile"],
            "career_stage": "mid",
            "experience_summary": "Mid-level engineer with backend focus.",
            # Outreach drafting fields
            "subject": "Quick question about your team",
            "body": "Hi, I noticed your team is doing great work. I'd love to connect.",
            "personalization_points": ["team growth", "tech stack alignment"],
            # Company dossier fields
            "culture_summary": "Innovative and collaborative engineering culture.",
            "culture_score": 8,
            "red_flags": [],
            "interview_format": "Phone screen, technical, system design, onsite",
            "interview_questions": ["Tell me about yourself"],
            "compensation_data": {"range": "150k-250k", "equity": "0.1%", "benefits": ["health"]},
            "key_people": [{"name": "Jane Doe", "title": "CTO"}],
            "why_hire_me": "Strong backend experience aligns with team needs.",
            "resume_bullets": ["Highlight Python backend experience", "Emphasize API design skills"],
            "fit_score_tips": ["Learn Kubernetes basics", "Emphasize cloud experience"],
            "recent_news": [{"title": "Series B", "date": "2025-01-01"}],
        }

    async def embed(self, text: str, dimensions: int = 1536) -> list[float]:
        return [0.1] * dimensions

    async def batch_embed(self, texts: list[str], dimensions: int = 1536) -> list[list[float]]:
        return [[0.1] * dimensions for _ in texts]

    async def chat(self, messages: list[dict]) -> str:
        return "Test chat response"

    async def vision(self, messages: list[dict], images: list[bytes]) -> str:
        return "Test vision response"


class HunterStub:
    """Test stub that returns plausible Hunter.io-shaped data."""

    async def domain_search(self, domain: str) -> dict:
        return {
            "domain": domain,
            "organization": domain.split(".")[0].capitalize(),
            "industry": "Technology",
            "emails": [
                {
                    "value": f"contact@{domain}",
                    "first_name": "John",
                    "last_name": "Doe",
                    "position": "Engineering Manager",
                    "confidence": 90,
                }
            ],
        }

    async def email_finder(self, domain: str, first_name: str, last_name: str) -> dict:
        return {
            "email": f"{first_name.lower()}.{last_name.lower()}@{domain}",
            "confidence": 90,
        }

    async def email_verifier(self, email: str) -> dict:
        return {"email": email, "result": "deliverable", "score": 90}

    async def enrichment(self, email: str) -> dict:
        return {"email": email}


class StorageStub:
    """In-memory storage stub for tests."""

    def __init__(self):
        self._data: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, content_type: str = "") -> str:
        self._data[key] = data
        return key

    async def download(self, key: str) -> bytes:
        if key not in self._data:
            raise FileNotFoundError(f"Key not found: {key}")
        return self._data[key]

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)


class NewsAPIStub:
    """Test stub that returns plausible NewsAPI-shaped data."""

    async def search_articles(
        self,
        query: str,
        from_date: str | None = None,
        to_date: str | None = None,
        page_size: int = 100,
        language: str = "en",
    ) -> list[dict]:
        return [
            {
                "title": "TechStartup raises $50M Series B for AI platform",
                "description": "TechStartup, an AI-powered developer tools company, announced a $50M Series B round.",
                "url": "https://example.com/techstartup-series-b",
                "publishedAt": "2026-02-20T10:00:00Z",
                "source": {"name": "TechCrunch"},
            },
            {
                "title": "CloudCorp secures $30M Series A for cloud infrastructure",
                "description": "CloudCorp has raised $30M in Series A funding to expand its cloud platform.",
                "url": "https://example.com/cloudcorp-series-a",
                "publishedAt": "2026-02-21T14:00:00Z",
                "source": {"name": "VentureBeat"},
            },
        ]


class ResendStub:
    """Test stub that returns plausible Resend-shaped data."""

    async def send(self, to: str, from_email: str, subject: str, body: str,
                   tags: list[str] | None = None, headers: dict | None = None,
                   attachments: list[dict] | None = None, reply_to: str | None = None) -> dict:
        return {"id": f"test_{uuid.uuid4().hex[:12]}"}

    def verify_webhook(self, payload: bytes, headers: dict) -> dict:
        import json
        return json.loads(payload)


class GitHubStub:
    """Stub for GitHubClientProtocol."""
    def __init__(self):
        self.created_issues = []

    async def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        issue = {"number": len(self.created_issues) + 1, "url": f"https://github.com/test/repo/issues/{len(self.created_issues) + 1}"}
        self.created_issues.append({"title": title, "body": body, "labels": labels})
        return issue

# Use a separate test database (only replace the database name at the end of the URL)
_base_url, _, _db_name = settings.DATABASE_URL.rpartition("/")
TEST_DATABASE_URL = f"{_base_url}/{_db_name}_test"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def redis():
    r = await init_redis()
    yield r
    await r.flushdb()
    await close_redis()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_db] = override_get_session
    # Use stubs for all external API clients - no real API calls in tests
    app.dependency_overrides[get_email_client] = lambda: ResendStub()

    # Inject stubs into singletons for code that calls get_*() directly
    _deps._openai_client = OpenAIStub()
    _deps._hunter_client = HunterStub()
    _deps._email_client = ResendStub()
    _deps._newsapi_client = NewsAPIStub()
    _deps._github_client = GitHubStub()

    # Use in-memory storage stub for tests
    import app.infrastructure.storage as _storage_mod
    _storage_mod._storage_instance = StorageStub()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    _deps._openai_client = None
    _deps._hunter_client = None
    _deps._email_client = None
    _deps._newsapi_client = None
    _deps._github_client = None
    _storage_mod._storage_instance = None


async def _create_invite_code(db_session: AsyncSession) -> str:
    """Create an invite code directly in the DB for testing."""
    # We need a candidate to be the inviter. Create a system-level one.
    # Check if seed inviter already exists
    from sqlalchemy import select

    from app.models.candidate import Candidate
    from app.utils.security import hash_password
    result = await db_session.execute(
        select(Candidate).where(Candidate.email == "seed-inviter@test.local")
    )
    inviter = result.scalar_one_or_none()
    if not inviter:
        inviter = Candidate(
            id=uuid.uuid4(),
            email="seed-inviter@test.local",
            password_hash=hash_password("seedpass123"),
            full_name="Seed Inviter",
        )
        db_session.add(inviter)
        await db_session.flush()

    code = secrets.token_urlsafe(16)
    invite = InviteCode(
        id=uuid.uuid4(),
        code=code,
        invited_by_id=inviter.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(invite)
    await db_session.flush()
    return code


@pytest_asyncio.fixture
async def invite_code(db_session: AsyncSession) -> str:
    """Return a valid invite code for test registration."""
    return await _create_invite_code(db_session)


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Register a test user and return auth headers."""
    code = await _create_invite_code(db_session)
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": email, "password": "testpass123", "full_name": "Test User", "invite_code": code},
    )
    resp = await client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def seed_candidate_dna(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    """Seed CandidateDNA for the authenticated test user (needed by discover)."""

    # Get the candidate_id from /auth/me
    resp = await client.get(f"{settings.API_V1_PREFIX}/auth/me", headers=auth_headers)
    candidate_id = uuid.UUID(resp.json()["id"])

    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="Experienced software engineer with 5 years in Python and cloud.",
        strengths=["Python", "Cloud Architecture"],
        gaps=[],
        career_stage="mid",
    )
    db_session.add(dna)
    await db_session.commit()
