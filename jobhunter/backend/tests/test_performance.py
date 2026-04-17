"""Tests for performance optimizations: subqueries, SQL aggregation, concurrent broadcast, numpy cosine, caching."""
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.contact import Contact
from app.models.outreach import OutreachMessage
from app.services import admin_service, analytics_service
from app.services.embedding_service import cosine_similarity
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_email(prefix: str = "perf") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


async def _create_user(
    db: AsyncSession,
    full_name: str = "Perf User",
    is_admin: bool = False,
    is_active: bool = True,
) -> Candidate:
    candidate = Candidate(
        id=uuid.uuid4(),
        email=_unique_email(),
        password_hash=hash_password("Testpass123"),
        full_name=full_name,
        is_admin=is_admin,
        is_active=is_active,
    )
    db.add(candidate)
    await db.flush()
    return candidate


async def _create_company(db: AsyncSession, candidate_id: uuid.UUID, domain: str = "test.com", status: str = "approved", research_status: str = "completed") -> Company:
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        domain=domain,
        name=domain.split(".")[0].capitalize(),
        status=status,
        research_status=research_status,
    )
    db.add(company)
    await db.flush()
    return company


async def _create_contact(db: AsyncSession, company_id: uuid.UUID, candidate_id: uuid.UUID, email: str | None = None) -> Contact:
    contact = Contact(
        id=uuid.uuid4(),
        company_id=company_id,
        candidate_id=candidate_id,
        email=email or _unique_email("contact"),
        full_name="John Doe",
    )
    db.add(contact)
    await db.flush()
    return contact


async def _create_message(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    contact_id: uuid.UUID,
    status: str = "sent",
    channel: str = "email",
) -> OutreachMessage:
    msg = OutreachMessage(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        contact_id=contact_id,
        channel=channel,
        subject="Test",
        body="Test body",
        status=status,
    )
    db.add(msg)
    await db.flush()
    return msg


# ---------------------------------------------------------------------------
# 1. Subquery tests - list_users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_users_returns_correct_counts(db_session: AsyncSession):
    """Subquery approach returns accurate company + message counts."""
    user = await _create_user(db_session)

    # Create 3 companies
    for i in range(3):
        await _create_company(db_session, user.id, domain=f"company{i}.com")

    # Create 2 sent messages via a contact
    company = await _create_company(db_session, user.id, domain="msg-test.com")
    contact = await _create_contact(db_session, company.id, user.id)
    await _create_message(db_session, user.id, contact.id, status="sent")
    await _create_message(db_session, user.id, contact.id, status="delivered")
    # Draft should NOT be counted
    await _create_message(db_session, user.id, contact.id, status="draft")

    result = await admin_service.list_users(db_session)

    # Find our user in the results
    target = next(u for u in result.users if u.id == str(user.id))
    assert target.companies_count == 4  # 3 + 1 (msg-test.com)
    assert target.messages_sent_count == 2  # sent + delivered, not draft


@pytest.mark.asyncio
async def test_list_users_no_cartesian_inflation(db_session: AsyncSession):
    """3 companies + 4 messages doesn't inflate either count via Cartesian product."""
    user = await _create_user(db_session)

    # Create 3 companies
    companies = []
    for i in range(3):
        c = await _create_company(db_session, user.id, domain=f"inflate{i}.com")
        companies.append(c)

    # Create 4 sent messages through different contacts
    for i in range(4):
        contact = await _create_contact(db_session, companies[i % 3].id, user.id)
        await _create_message(db_session, user.id, contact.id, status="sent")

    result = await admin_service.list_users(db_session)
    target = next(u for u in result.users if u.id == str(user.id))

    # Without the fix, Cartesian product would give 12 for companies_count
    assert target.companies_count == 3
    assert target.messages_sent_count == 4


# ---------------------------------------------------------------------------
# 2. Analytics SQL aggregation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outreach_stats_sql_aggregation(db_session: AsyncSession):
    """SQL GROUP BY returns correct sent/opened/replied counts by channel."""
    user = await _create_user(db_session)
    company = await _create_company(db_session, user.id)
    contact = await _create_contact(db_session, company.id, user.id)

    # Email channel: 2 sent, 1 opened, 1 replied
    await _create_message(db_session, user.id, contact.id, status="sent", channel="email")
    await _create_message(db_session, user.id, contact.id, status="opened", channel="email")
    await _create_message(db_session, user.id, contact.id, status="replied", channel="email")
    # Draft should be excluded from totals
    await _create_message(db_session, user.id, contact.id, status="draft", channel="email")

    # LinkedIn channel: 1 sent
    await _create_message(db_session, user.id, contact.id, status="sent", channel="linkedin")

    stats = await analytics_service.get_outreach_stats(db_session, user.id)

    # Sent includes: sent, opened, replied (not draft)
    assert stats["total_sent"] == 4  # 3 email + 1 linkedin
    assert stats["total_opened"] == 2  # opened + replied
    assert stats["total_replied"] == 1
    assert stats["by_channel"]["email"]["sent"] == 3
    assert stats["by_channel"]["email"]["opened"] == 2
    assert stats["by_channel"]["linkedin"]["sent"] == 1


@pytest.mark.asyncio
async def test_pipeline_stats_combined_query(db_session: AsyncSession):
    """Combined CASE query matches expected pipeline counts."""
    user = await _create_user(db_session)

    # Create companies with different statuses
    await _create_company(db_session, user.id, domain="s1.com", status="suggested", research_status="pending")
    await _create_company(db_session, user.id, domain="s2.com", status="suggested", research_status="pending")
    await _create_company(db_session, user.id, domain="a1.com", status="approved", research_status="completed")
    await _create_company(db_session, user.id, domain="r1.com", status="rejected", research_status="pending")

    stats = await analytics_service.get_pipeline_stats(db_session, user.id)

    assert stats["suggested"] == 2
    assert stats["approved"] == 1
    assert stats["rejected"] == 1
    assert stats["researched"] == 1
    assert stats["contacted"] == 0


# ---------------------------------------------------------------------------
# 3. Concurrent broadcast tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_concurrent_sending(db_session: AsyncSession):
    """Broadcast sends to all eligible recipients via asyncio.gather."""
    admin = await _create_user(db_session, is_admin=True, full_name="Broadcast Admin")
    # Create 5 active users
    for i in range(5):
        await _create_user(db_session, full_name=f"User {i}")

    email_client = AsyncMock()
    email_client.send = AsyncMock(return_value={"id": "test"})

    result = await admin_service.broadcast_email(
        db_session, admin.id, "Test Subject", "Test Body", email_client,
    )

    # At least our 6 users should receive emails (DB may have more from other tests)
    assert result.sent_count >= 6
    assert email_client.send.call_count >= 6


@pytest.mark.asyncio
async def test_broadcast_handles_failures(db_session: AsyncSession):
    """Individual send failures don't crash the whole broadcast."""
    admin = await _create_user(db_session, is_admin=True, full_name="Broadcast Admin 2")
    for i in range(3):
        await _create_user(db_session, full_name=f"Fail User {i}")

    call_count = 0

    async def _flaky_send(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            raise Exception("Simulated failure")
        return {"id": "ok"}

    email_client = AsyncMock()
    email_client.send = _flaky_send

    result = await admin_service.broadcast_email(
        db_session, admin.id, "Test", "Body", email_client,
    )

    # Some should succeed, some should fail; total = sent + skipped
    total = result.sent_count + result.skipped_count
    assert total >= 4  # at least our 4 users
    assert result.sent_count > 0
    assert result.skipped_count > 0


# ---------------------------------------------------------------------------
# 4. NumPy cosine similarity tests
# ---------------------------------------------------------------------------

def test_cosine_similarity_numpy_basic():
    """Orthogonal vectors → 0.0."""
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(cosine_similarity(a, b) - 0.0) < 1e-9


def test_cosine_similarity_numpy_identical():
    """Identical vectors → 1.0."""
    a = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(a, a) - 1.0) < 1e-9


def test_cosine_similarity_numpy_zero_vector():
    """Zero vector → 0.0."""
    a = [1.0, 2.0, 3.0]
    b = [0.0, 0.0, 0.0]
    assert cosine_similarity(a, b) == 0.0


def test_cosine_similarity_numpy_known_value():
    """Known dot product matches expected cosine similarity."""
    import numpy as np
    a = [1.0, 0.0]
    b = [1.0, 1.0]
    # cos(45°) ≈ 0.7071
    expected = 1.0 / np.sqrt(2.0)
    assert abs(cosine_similarity(a, b) - expected) < 1e-9


# ---------------------------------------------------------------------------
# 5. Redis caching for admin overview
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overview_caching(db_session: AsyncSession, redis):
    """Redis cache miss → DB hit → cache set → cache hit on second call."""
    # Ensure cache is empty
    await redis.delete(admin_service.OVERVIEW_CACHE_KEY)

    # First call should hit DB and populate cache
    result1 = await admin_service.get_system_overview(db_session)
    assert result1 is not None

    # Verify cache was set
    cached = await redis.get(admin_service.OVERVIEW_CACHE_KEY)
    assert cached is not None

    # Second call should return from cache (same result)
    result2 = await admin_service.get_system_overview(db_session)
    assert result2.total_users == result1.total_users
    assert result2.total_companies == result1.total_companies
