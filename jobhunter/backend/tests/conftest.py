import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
import app.dependencies as _deps
from app.dependencies import get_db, get_openai, get_hunter, get_email_client
from app.infrastructure.database import get_session
from app.infrastructure.redis_client import init_redis, close_redis, get_redis
from app.models.base import Base
from app.models.candidate import CandidateDNA
from app.models.invite import InviteCode
from app.main import app


# ---------------------------------------------------------------------------
# Lightweight test stubs for external API clients
# ---------------------------------------------------------------------------

class OpenAIStub:
    """Test stub that returns plausible data without hitting real OpenAI."""

    async def parse_structured(self, system_prompt: str, user_content: str, response_schema: dict) -> dict:
        # Detect schema type by checking top-level required keys
        schema_keys = set(response_schema.get("properties", {}).keys())

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

        # Return a response that satisfies both resume parsing and outreach drafting schemas
        return {
            "name": "Test User",
            "headline": "Software Engineer",
            "experiences": [{"company": "TestCo", "title": "Engineer"}],
            "skills": ["Python", "FastAPI"],
            "education": [{"institution": "MIT", "degree": "BS CS"}],
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
            "recent_news": [{"title": "Series B", "date": "2025-01-01"}],
        }

    async def embed(self, text: str, dimensions: int = 1536) -> list[float]:
        return [0.0] * dimensions

    async def batch_embed(self, texts: list[str], dimensions: int = 1536) -> list[list[float]]:
        return [[0.0] * dimensions for _ in texts]

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


class ResendStub:
    """Test stub that returns plausible Resend-shaped data."""

    async def send(self, to: str, from_email: str, subject: str, body: str,
                   tags: list[str] | None = None, headers: dict | None = None,
                   attachments: list[dict] | None = None) -> dict:
        return {"id": f"test_{uuid.uuid4().hex[:12]}"}

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        import json
        return json.loads(payload)

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

    from app.infrastructure.openai_client import OpenAIClient
    from app.infrastructure.hunter_client import HunterClient

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_db] = override_get_session
    # Use real OpenAI and Hunter clients; only stub email sending
    app.dependency_overrides[get_email_client] = lambda: ResendStub()

    # Inject real clients into singletons for code that calls get_*() directly
    _deps._openai_client = OpenAIClient()
    _deps._hunter_client = HunterClient()
    _deps._email_client = ResendStub()

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
    _storage_mod._storage_instance = None


async def _create_invite_code(db_session: AsyncSession) -> str:
    """Create an invite code directly in the DB for testing."""
    # We need a candidate to be the inviter. Create a system-level one.
    from app.models.candidate import Candidate
    from app.utils.security import hash_password

    # Check if seed inviter already exists
    from sqlalchemy import select
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
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
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
    from sqlalchemy import select
    from app.models.candidate import Candidate

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
