"""Tests for the LangGraph outreach email pipeline."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candidate import Candidate, CandidateDNA
from app.models.company import Company, CompanyDossier
from app.models.contact import Contact
from app.models.outreach import OutreachMessage
from app.models.pending_action import PendingAction
from app.utils.security import hash_password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def graph_session_factory(test_engine):
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def patch_graph_db(graph_session_factory, monkeypatch):
    import app.infrastructure.database as db_mod
    monkeypatch.setattr(db_mod, "async_session_factory", graph_session_factory)


@pytest_asyncio.fixture
async def patch_openai_stub(monkeypatch):
    import app.dependencies as deps
    from tests.conftest import OpenAIStub
    deps._openai_client = OpenAIStub()
    yield
    deps._openai_client = None


@pytest_asyncio.fixture
async def patch_email_stub(monkeypatch):
    import app.dependencies as deps
    from tests.conftest import ResendStub
    deps._email_client = ResendStub()
    yield
    deps._email_client = None


@pytest_asyncio.fixture
async def outreach_context(db_session: AsyncSession):
    """Create candidate + DNA + company + dossier + contact for outreach tests."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"outreach-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Outreach Test User",
    )
    db_session.add(candidate)
    await db_session.flush()

    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="Senior backend engineer with 5 years Python experience.",
        strengths=["Python", "FastAPI"],
        gaps=[],
        career_stage="mid",
    )
    db_session.add(dna)

    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        candidate_id=candidate_id,
        name="TestCorp",
        domain="testcorp.com",
        industry="Technology",
        tech_stack=["Python", "React"],
    )
    db_session.add(company)
    await db_session.flush()

    dossier = CompanyDossier(
        id=uuid.uuid4(),
        company_id=company_id,
        culture_summary="Innovative engineering culture.",
        why_hire_me="Strong backend experience.",
        recent_news=[{"title": "Series B", "date": "2025-01-01"}],
    )
    db_session.add(dossier)

    contact_id = uuid.uuid4()
    contact = Contact(
        id=contact_id,
        company_id=company_id,
        candidate_id=candidate_id,
        full_name="Jane Doe",
        email="jane@testcorp.com",
        title="Engineering Manager",
        role_type="hiring_manager",
    )
    db_session.add(contact)
    await db_session.commit()

    return {
        "candidate_id": candidate_id,
        "contact_id": contact_id,
        "company_id": company_id,
    }


def _initial_state(candidate_id: uuid.UUID, contact_id: uuid.UUID) -> dict:
    return {
        "candidate_id": str(candidate_id),
        "contact_id": str(contact_id),
        "plan_tier": "free",
        "language": "en",
        "variant": None,
        "attach_resume": True,
        "context": None,
        "message_type": None,
        "outreach_message_id": None,
        "draft_data": None,
        "action_id": None,
        "approval_decision": None,
        "external_message_id": None,
        "status": "pending",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_graph_builds_and_compiles():
    """Graph builds, compiles, and has all 8 node names."""
    from app.graphs.outreach import build_outreach_pipeline

    builder = build_outreach_pipeline()
    graph = builder.compile()

    node_names = set(graph.nodes.keys())
    expected = {
        "gather_context", "generate_draft", "quality_check", "create_approval",
        "validate_send", "send_email", "notify_sent", "mark_failed",
    }
    # LangGraph adds __start__ and __end__ pseudo-nodes
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


async def test_gather_context_missing_contact(
    db_session, patch_graph_db, patch_openai_stub
):
    """Returns status=failed for nonexistent contact."""
    from app.graphs.outreach import gather_context_node

    fake_state = _initial_state(uuid.uuid4(), uuid.uuid4())
    result = await gather_context_node(fake_state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


async def test_full_draft_pipeline(
    db_session, outreach_context, patch_graph_db, patch_openai_stub
):
    """Runs gather → generate → quality_check → create_approval (interrupt pauses)."""
    from langgraph.checkpoint.memory import MemorySaver
    from app.graphs.outreach import _builder

    checkpointer = MemorySaver()
    graph = _builder.compile(checkpointer=checkpointer)

    ctx = outreach_context
    state = _initial_state(ctx["candidate_id"], ctx["contact_id"])
    thread_id = f"test-outreach-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    # Run the graph - it should pause at interrupt()
    result = await graph.ainvoke(state, config=config)

    # Verify OutreachMessage was created in DB
    msg_result = await db_session.execute(
        select(OutreachMessage).where(
            OutreachMessage.candidate_id == ctx["candidate_id"],
            OutreachMessage.contact_id == ctx["contact_id"],
        )
    )
    message = msg_result.scalar_one_or_none()
    assert message is not None
    assert message.status == "draft"
    assert message.subject is not None
    assert message.body is not None

    # Verify PendingAction was created
    action_result = await db_session.execute(
        select(PendingAction).where(
            PendingAction.candidate_id == ctx["candidate_id"],
            PendingAction.entity_id == message.id,
        )
    )
    action = action_result.scalar_one_or_none()
    assert action is not None
    assert action.action_type == "send_email"
    assert action.metadata_ is not None
    assert "thread_id" in action.metadata_


async def test_resume_after_approval(
    db_session, outreach_context, patch_graph_db, patch_openai_stub, patch_email_stub, redis
):
    """Run first half, resume with approved=True, verify message sent."""
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command
    from app.graphs.outreach import _builder

    checkpointer = MemorySaver()
    graph = _builder.compile(checkpointer=checkpointer)

    ctx = outreach_context
    state = _initial_state(ctx["candidate_id"], ctx["contact_id"])
    thread_id = f"test-outreach-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    # First half - pauses at interrupt
    await graph.ainvoke(state, config=config)

    # Resume with approval
    result = await graph.ainvoke(
        Command(resume={"approved": True, "attach_resume": False}),
        config=config,
    )

    assert result["status"] == "sent"
    assert result["external_message_id"] is not None

    # Verify DB: message marked as sent
    msg_result = await db_session.execute(
        select(OutreachMessage).where(
            OutreachMessage.candidate_id == ctx["candidate_id"],
            OutreachMessage.contact_id == ctx["contact_id"],
        )
    )
    message = msg_result.scalar_one()
    assert message.status == "sent"
    assert message.sent_at is not None


async def test_rejection_skips_send(
    db_session, outreach_context, patch_graph_db, patch_openai_stub
):
    """Resume with approved=False, verify message stays draft and no send."""
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command
    from app.graphs.outreach import _builder

    checkpointer = MemorySaver()
    graph = _builder.compile(checkpointer=checkpointer)

    ctx = outreach_context
    state = _initial_state(ctx["candidate_id"], ctx["contact_id"])
    thread_id = f"test-outreach-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    # First half - pauses at interrupt
    await graph.ainvoke(state, config=config)

    # Resume with rejection
    result = await graph.ainvoke(
        Command(resume={"approved": False}),
        config=config,
    )

    # Rejection routes to END - status stays "awaiting_approval" (not "sent")
    assert result.get("status") != "sent"

    # Verify DB: message stays draft (not sent)
    msg_result = await db_session.execute(
        select(OutreachMessage).where(
            OutreachMessage.candidate_id == ctx["candidate_id"],
            OutreachMessage.contact_id == ctx["contact_id"],
        )
    )
    message = msg_result.scalar_one()
    assert message.status == "draft"
    assert message.sent_at is None
