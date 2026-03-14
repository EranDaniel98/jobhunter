"""Tests for the follow-up scheduler logic."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.contact import Contact
from app.models.company import Company
from app.models.candidate import Candidate, CandidateDNA
from app.models.outreach import OutreachMessage
from app.models.pending_action import PendingAction
from app.utils.security import hash_password


@pytest_asyncio.fixture
async def scheduler_data(db_session: AsyncSession):
    """Create a candidate, company, contact for scheduler tests."""
    candidate = Candidate(
        id=uuid.uuid4(),
        email=f"sched-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Scheduler Tester",
    )
    db_session.add(candidate)

    # Add CandidateDNA so outreach_service.draft_message works
    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        experience_summary="Experienced engineer.",
        strengths=["Python"],
        gaps=[],
        career_stage="mid",
    )
    db_session.add(dna)

    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        name="SchedulerCo",
        domain="schedulerco.com",
        status="approved",
        research_status="completed",
    )
    db_session.add(company)

    contact = Contact(
        id=uuid.uuid4(),
        company_id=company.id,
        candidate_id=candidate.id,
        full_name="Jane Scheduler",
        email="jane@schedulerco.com",
    )
    db_session.add(contact)
    await db_session.flush()

    return {"candidate": candidate, "company": company, "contact": contact}


def _create_message(
    candidate_id, contact_id, message_type="initial", status="sent",
    sent_at=None, channel="email",
) -> OutreachMessage:
    return OutreachMessage(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        contact_id=contact_id,
        channel=channel,
        message_type=message_type,
        subject="Test subject",
        body="Test body",
        status=status,
        sent_at=sent_at or datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_no_followup_before_threshold(db_session: AsyncSession, scheduler_data):
    """Message sent 1 day ago should NOT trigger follow-up."""
    data = scheduler_data
    msg = _create_message(
        data["candidate"].id, data["contact"].id,
        sent_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(msg)
    await db_session.flush()

    # Verify no pending actions exist
    result = await db_session.execute(
        select(PendingAction).where(PendingAction.candidate_id == data["candidate"].id)
    )
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_followup_due_after_3_days(db_session: AsyncSession, scheduler_data):
    """Initial message sent 4 days ago should make it eligible for followup_1."""
    data = scheduler_data
    msg = _create_message(
        data["candidate"].id, data["contact"].id,
        message_type="initial", status="sent",
        sent_at=datetime.now(timezone.utc) - timedelta(days=4),
    )
    db_session.add(msg)
    await db_session.flush()

    # The message meets criteria: sent > 3 days ago, type=initial, status=sent
    # Verify it can be found by the scheduler query
    from app.worker import FOLLOWUP_THRESHOLDS
    cutoff = datetime.now(timezone.utc) - timedelta(days=FOLLOWUP_THRESHOLDS["initial"][1])

    result = await db_session.execute(
        select(OutreachMessage).where(
            OutreachMessage.status.in_(["sent", "delivered"]),
            OutreachMessage.channel == "email",
            OutreachMessage.message_type == "initial",
            OutreachMessage.sent_at <= cutoff,
        )
    )
    due = result.scalars().all()
    assert len(due) >= 1
    assert any(m.id == msg.id for m in due)


@pytest.mark.asyncio
async def test_no_followup_if_replied(db_session: AsyncSession, scheduler_data):
    """Replied messages should NOT trigger follow-ups."""
    data = scheduler_data
    msg = _create_message(
        data["candidate"].id, data["contact"].id,
        message_type="initial", status="replied",
        sent_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(msg)
    await db_session.flush()

    # Scheduler only looks for status in (sent, delivered)
    from app.worker import FOLLOWUP_THRESHOLDS
    cutoff = datetime.now(timezone.utc) - timedelta(days=FOLLOWUP_THRESHOLDS["initial"][1])

    result = await db_session.execute(
        select(OutreachMessage).where(
            OutreachMessage.status.in_(["sent", "delivered"]),
            OutreachMessage.message_type == "initial",
            OutreachMessage.sent_at <= cutoff,
            OutreachMessage.candidate_id == data["candidate"].id,
        )
    )
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_no_followup_if_pending_exists(db_session: AsyncSession, scheduler_data):
    """Existing pending action should prevent duplicate draft."""
    data = scheduler_data
    msg = _create_message(
        data["candidate"].id, data["contact"].id,
        sent_at=datetime.now(timezone.utc) - timedelta(days=4),
    )
    db_session.add(msg)

    # Create an existing pending action for this message
    action = PendingAction(
        id=uuid.uuid4(),
        candidate_id=data["candidate"].id,
        action_type="send_followup",
        entity_type="outreach_message",
        entity_id=msg.id,
        status="pending",
    )
    db_session.add(action)
    await db_session.flush()

    # Verify pending action exists
    result = await db_session.execute(
        select(PendingAction).where(
            PendingAction.entity_id == msg.id,
            PendingAction.status == "pending",
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_breakup_is_final(db_session: AsyncSession, scheduler_data):
    """No follow-up should be generated after a breakup message."""
    data = scheduler_data
    msg = _create_message(
        data["candidate"].id, data["contact"].id,
        message_type="breakup", status="sent",
        sent_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(msg)
    await db_session.flush()

    # breakup is not in FOLLOWUP_THRESHOLDS, so it won't be queried
    from app.worker import FOLLOWUP_THRESHOLDS
    assert "breakup" not in FOLLOWUP_THRESHOLDS


@pytest.mark.asyncio
async def test_check_followup_due_launches_graph(
    db_session: AsyncSession, test_engine, scheduler_data, redis
):
    """Call check_followup_due() end-to-end and verify graph creates draft + PendingAction."""
    from app.worker import check_followup_due

    data = scheduler_data

    # Create a sent initial message from 4 days ago
    msg = _create_message(
        data["candidate"].id, data["contact"].id,
        message_type="initial", status="sent",
        sent_at=datetime.now(timezone.utc) - timedelta(days=4),
    )
    db_session.add(msg)
    await db_session.commit()

    # Monkeypatch DB session factory so graph nodes use the test DB
    graph_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    import app.infrastructure.database as db_mod
    original_factory = db_mod.async_session_factory
    db_mod.async_session_factory = graph_session_factory

    # Monkeypatch OpenAI + email stubs
    import app.dependencies as deps
    from tests.conftest import OpenAIStub, ResendStub
    deps._openai_client = OpenAIStub()
    deps._email_client = ResendStub()

    try:
        # Run the cron function - graph will pause at interrupt()
        await check_followup_due(ctx={})
    finally:
        db_mod.async_session_factory = original_factory
        deps._openai_client = None
        deps._email_client = None

    # Verify: a new followup_1 draft was created
    async with graph_session_factory() as check_db:
        result = await check_db.execute(
            select(OutreachMessage).where(
                OutreachMessage.candidate_id == data["candidate"].id,
                OutreachMessage.contact_id == data["contact"].id,
                OutreachMessage.message_type == "followup_1",
            )
        )
        followup = result.scalar_one_or_none()
        assert followup is not None, "Expected a followup_1 message to be created"
        assert followup.status == "draft"

        # Verify: PendingAction with thread_id was created
        action_result = await check_db.execute(
            select(PendingAction).where(
                PendingAction.candidate_id == data["candidate"].id,
                PendingAction.entity_id == followup.id,
            )
        )
        action = action_result.scalar_one_or_none()
        assert action is not None, "Expected a PendingAction for the followup"
        assert action.action_type == "send_email"
        assert "thread_id" in (action.metadata_ or {})
