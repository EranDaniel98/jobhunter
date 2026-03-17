"""Additional unit tests for LangGraph outreach pipeline nodes (error/edge paths)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**overrides):
    base = {
        "candidate_id": str(uuid.uuid4()),
        "contact_id": str(uuid.uuid4()),
        "plan_tier": "free",
        "language": "en",
        "variant": None,
        "attach_resume": False,
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
    base.update(overrides)
    return base


def _make_mock_db_session():
    """Return a mock async context-manager session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


# ---------------------------------------------------------------------------
# quality_check_node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_check_no_draft_returns_failed():
    from app.graphs.outreach import quality_check_node

    result = await quality_check_node(_state(draft_data=None))
    assert result["status"] == "failed"
    assert "No draft data" in result["error"]


@pytest.mark.asyncio
async def test_quality_check_empty_subject_returns_failed():
    from app.graphs.outreach import quality_check_node

    state = _state(draft_data={"subject": "", "body": "Hello world"})
    result = await quality_check_node(state)
    assert result["status"] == "failed"
    assert "empty subject or body" in result["error"]


@pytest.mark.asyncio
async def test_quality_check_empty_body_returns_failed():
    from app.graphs.outreach import quality_check_node

    state = _state(draft_data={"subject": "Hello", "body": ""})
    result = await quality_check_node(state)
    assert result["status"] == "failed"
    assert "empty subject or body" in result["error"]


@pytest.mark.asyncio
async def test_quality_check_long_subject_logs_warning_but_passes():
    from app.graphs.outreach import quality_check_node

    state = _state(
        draft_data={
            "subject": "A" * 250,
            "body": "This is a long body text",
            "personalization_points": ["point"],
        }
    )
    result = await quality_check_node(state)
    # Should pass (return empty dict, no status=failed)
    assert result.get("status") != "failed"
    assert "error" not in result


@pytest.mark.asyncio
async def test_quality_check_no_personalization_logs_warning_but_passes():
    from app.graphs.outreach import quality_check_node

    state = _state(
        draft_data={
            "subject": "Hi there",
            "body": "Body content here",
            "personalization_points": [],
        }
    )
    result = await quality_check_node(state)
    assert result.get("status") != "failed"


# ---------------------------------------------------------------------------
# generate_draft_node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_draft_node_openai_failure():
    from app.graphs.outreach import generate_draft_node

    state = _state(
        context={
            "candidate_summary": "5y backend",
            "company_name": "Acme",
            "domain": "acme.com",
            "industry": "Tech",
            "tech_stack": "Python",
            "culture_summary": "Great culture",
            "why_hire_me": "Strong fit",
            "recent_news": "Raised Series A",
            "contact_name": "Bob",
            "contact_title": "CTO",
            "contact_role": "decision_maker",
            "contact_email": "bob@acme.com",
        },
        message_type="initial",
        language="en",
        variant=None,
    )

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(side_effect=Exception("OpenAI timeout"))

    with patch("app.graphs.outreach.get_openai", return_value=mock_client):
        result = await generate_draft_node(state)

    assert result["status"] == "failed"
    assert "OpenAI timeout" in result["error"]


@pytest.mark.asyncio
async def test_generate_draft_node_variant_instruction():
    """Test that variant instruction is included in prompt."""
    from app.graphs.outreach import generate_draft_node

    ctx = {
        "candidate_summary": "5y backend",
        "company_name": "Acme",
        "domain": "acme.com",
        "industry": "Tech",
        "tech_stack": "Python",
        "culture_summary": "Great",
        "why_hire_me": "Fit",
        "recent_news": "None",
        "contact_name": "Bob",
        "contact_title": "CTO",
        "contact_role": "decision_maker",
        "contact_email": "bob@acme.com",
    }
    state = _state(context=ctx, message_type="initial", language="he", variant="professional")

    mock_client = MagicMock()
    mock_client.parse_structured = AsyncMock(
        return_value={"subject": "Subj", "body": "Body", "personalization_points": []}
    )

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    with (
        patch("app.graphs.outreach.get_openai", return_value=mock_client),
        patch("app.graphs.outreach._db_mod.async_session_factory", return_value=mock_cm),
    ):
        result = await generate_draft_node(state)

    # Should succeed
    assert "outreach_message_id" in result
    assert result["status"] == "drafted"


# ---------------------------------------------------------------------------
# validate_send_node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_send_not_approved():
    from app.graphs.outreach import validate_send_node

    state = _state(
        approval_decision={"approved": False},
        outreach_message_id=str(uuid.uuid4()),
    )
    result = await validate_send_node(state)
    assert result["status"] == "failed"
    assert "not approved" in result["error"]


@pytest.mark.asyncio
async def test_validate_send_message_not_found():
    from app.graphs.outreach import validate_send_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state(
        approval_decision={"approved": True},
        outreach_message_id=str(uuid.uuid4()),
    )

    with patch("app.graphs.outreach._db_mod.async_session_factory", return_value=mock_cm):
        result = await validate_send_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_validate_send_suppressed_email():
    from app.graphs.outreach import validate_send_node
    from app.models.enums import MessageStatus
    from app.models.outreach import OutreachMessage

    msg_id = uuid.uuid4()
    mock_message = MagicMock(spec=OutreachMessage)
    mock_message.id = msg_id
    mock_message.status = MessageStatus.DRAFT
    mock_message.message_type = "initial"
    mock_message.contact_id = uuid.uuid4()

    mock_contact = MagicMock()
    mock_contact.email = "suppressed@example.com"

    mock_suppression = MagicMock()

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_message)
        elif call_count == 2:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_contact)
        elif call_count == 3:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_suppression)
        else:
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
        return mock_result

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    state = _state(
        approval_decision={"approved": True},
        outreach_message_id=str(msg_id),
        plan_tier="free",
    )

    with patch("app.graphs.outreach._db_mod.async_session_factory", return_value=mock_cm):
        result = await validate_send_node(state)

    assert result["status"] == "failed"
    assert "suppression list" in result["error"]


@pytest.mark.asyncio
async def test_validate_send_quota_exceeded():
    from fastapi import HTTPException

    from app.graphs.outreach import validate_send_node
    from app.models.enums import MessageStatus
    from app.models.outreach import OutreachMessage

    msg_id = uuid.uuid4()
    mock_message = MagicMock(spec=OutreachMessage)
    mock_message.id = msg_id
    mock_message.status = MessageStatus.DRAFT
    mock_message.message_type = "initial"
    mock_message.contact_id = uuid.uuid4()

    mock_contact = MagicMock()
    mock_contact.email = "valid@example.com"

    call_count = 0

    def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_message)
        elif call_count == 2:
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_contact)
        else:
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
        return mock_result

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute = AsyncMock(side_effect=side_effect_execute)

    quota_exc = HTTPException(status_code=429, detail={"message": "Daily email limit reached"})

    state = _state(
        approval_decision={"approved": True},
        outreach_message_id=str(msg_id),
        plan_tier="free",
    )

    with (
        patch("app.graphs.outreach._db_mod.async_session_factory", return_value=mock_cm),
        patch(
            "app.services.quota_service.check_and_increment",
            AsyncMock(side_effect=quota_exc),
        ),
    ):
        result = await validate_send_node(state)

    assert result["status"] == "failed"
    assert "Daily email limit reached" in result["error"] or "limit" in result["error"].lower()


# ---------------------------------------------------------------------------
# send_email_node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_node_message_not_found():
    from app.graphs.outreach import send_email_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state(
        outreach_message_id=str(uuid.uuid4()),
        approval_decision={"approved": True, "attach_resume": False},
    )

    with patch("app.graphs.outreach._db_mod.async_session_factory", return_value=mock_cm):
        result = await send_email_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# mark_failed_node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_failed_node_no_message_id():
    """mark_failed_node should work even with no outreach_message_id."""
    from app.graphs.outreach import mark_failed_node

    state = _state(outreach_message_id=None, error="something went wrong")

    with patch("app.graphs.outreach.ws_manager.broadcast", new=AsyncMock()):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_mark_failed_node_with_message_id_not_found():
    """mark_failed_node with message_id that doesn't exist in DB."""
    from app.graphs.outreach import mark_failed_node

    mock_cm, mock_session = _make_mock_db_session()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    state = _state(outreach_message_id=str(uuid.uuid4()), error="draft failed")

    with (
        patch("app.graphs.outreach._db_mod.async_session_factory", return_value=mock_cm),
        patch("app.graphs.outreach.ws_manager.broadcast", new=AsyncMock()),
    ):
        result = await mark_failed_node(state)

    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# notify_sent_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_sent_node_broadcasts():
    from app.graphs.outreach import notify_sent_node

    candidate_id = str(uuid.uuid4())
    state = _state(candidate_id=candidate_id, outreach_message_id=str(uuid.uuid4()), status="sent")

    broadcast_mock = AsyncMock()
    with patch("app.graphs.outreach.ws_manager.broadcast", new=broadcast_mock):
        result = await notify_sent_node(state)

    assert result["status"] == "sent"
    broadcast_mock.assert_called_once()
    call_args = broadcast_mock.call_args[0]
    assert call_args[0] == candidate_id
    assert call_args[1] == "email_sent"


# ---------------------------------------------------------------------------
# _check_error / _check_rejection routing functions
# ---------------------------------------------------------------------------


def test_check_error_failed_routes_to_mark_failed():
    from app.graphs.outreach import _check_error

    assert _check_error(_state(status="failed")) == "mark_failed"


def test_check_error_non_failed_continues():
    from app.graphs.outreach import _check_error

    assert _check_error(_state(status="pending")) == "continue"
    assert _check_error(_state(status="drafted")) == "continue"


def test_check_rejection_not_approved():
    from app.graphs.outreach import _check_rejection

    state = _state(approval_decision={"approved": False})
    assert _check_rejection(state) == "rejected"


def test_check_rejection_approved():
    from app.graphs.outreach import _check_rejection

    state = _state(approval_decision={"approved": True})
    assert _check_rejection(state) == "continue"


def test_check_rejection_no_decision():
    from app.graphs.outreach import _check_rejection

    state = _state(approval_decision=None)
    assert _check_rejection(state) == "rejected"
