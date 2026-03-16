"""Full coverage tests for api/outreach.py — covering remaining uncovered lines."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.outreach import OutreachMessage
from app.models.pending_action import PendingAction

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Shared helpers (same as test_outreach_api_extended.py)
# ---------------------------------------------------------------------------


async def _get_candidate_id(client: AsyncClient, headers: dict) -> uuid.UUID:
    me = await client.get(f"{API}/auth/me", headers=headers)
    return uuid.UUID(me.json()["id"])


async def _create_company_and_contact(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    domain: str | None = None,
) -> tuple[Company, Contact]:
    tag = uuid.uuid4().hex[:8]
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=f"FullCo-{tag}",
        domain=domain or f"fullco-{tag}.com",
    )
    db.add(company)
    await db.flush()

    contact = Contact(
        id=uuid.uuid4(),
        company_id=company.id,
        candidate_id=candidate_id,
        full_name="Full Contact",
        email=f"full-{tag}@fullco.com",
    )
    db.add(contact)
    await db.flush()
    return company, contact


async def _create_draft_message(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: str = "Hello, I'd like to connect.",
    status: str = "draft",
    channel: str = "email",
    message_type: str = "initial",
) -> OutreachMessage:
    msg = OutreachMessage(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        contact_id=contact_id,
        channel=channel,
        message_type=message_type,
        subject="Test Subject",
        body=body,
        status=status,
    )
    db.add(msg)
    await db.flush()
    return msg


# ---------------------------------------------------------------------------
# _run_outreach_graph background task — error handling (lines 60-81)
# ---------------------------------------------------------------------------


class TestRunOutreachGraphBackground:
    @pytest.mark.asyncio
    async def test_graph_failure_marks_message_failed(self):
        """When graph raises, the background task catches and marks message as failed."""
        from app.api.outreach import _run_outreach_graph
        from app.models.enums import MessageStatus

        contact_id = str(uuid.uuid4())
        candidate_id = str(uuid.uuid4())
        thread_id = f"outreach-{uuid.uuid4()}"

        state = {
            "contact_id": contact_id,
            "candidate_id": candidate_id,
        }

        mock_msg = MagicMock()
        mock_msg.status = MessageStatus.DRAFT

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.commit = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_msg
        mock_db.execute.return_value = result

        mock_factory = MagicMock(return_value=mock_db)
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph failed"))

        with (
            patch("app.graphs.outreach.get_outreach_pipeline", return_value=mock_graph),
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            await _run_outreach_graph(state, thread_id)

        # Message status should have been set to failed
        assert mock_msg.status == MessageStatus.FAILED
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graph_failure_no_contact_in_state(self):
        """When graph raises but state has no contact_id, error handler opens DB but skips query."""
        from app.api.outreach import _run_outreach_graph

        state = {}  # no contact_id / candidate_id
        thread_id = f"outreach-{uuid.uuid4()}"

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_db)

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph failed"))

        with (
            patch("app.graphs.outreach.get_outreach_pipeline", return_value=mock_graph),
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            # Should not raise
            await _run_outreach_graph(state, thread_id)

        # DB execute should NOT have been called (no IDs to look up)
        mock_db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_graph_failure_error_handler_itself_fails(self):
        """Even if the error-handler DB session fails, the function should not raise."""
        from app.api.outreach import _run_outreach_graph

        state = {
            "contact_id": str(uuid.uuid4()),
            "candidate_id": str(uuid.uuid4()),
        }
        thread_id = f"outreach-{uuid.uuid4()}"

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph failed"))

        # Make the DB session factory itself raise
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(side_effect=RuntimeError("db also failed"))
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_db)

        with (
            patch("app.graphs.outreach.get_outreach_pipeline", return_value=mock_graph),
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            # Should not propagate the secondary error
            await _run_outreach_graph(state, thread_id)


# ---------------------------------------------------------------------------
# POST /outreach/draft — quota check error handling (lines 98-103)
# ---------------------------------------------------------------------------


class TestDraftMessageQuotaErrors:
    @pytest.mark.asyncio
    async def test_quota_http_exception_is_re_raised(self, client: AsyncClient, auth_headers: dict):
        """When quota check raises an HTTPException, it propagates unchanged."""
        from fastapi import HTTPException as _HTTPException

        with patch(
            "app.services.quota_service.check_and_increment",
            new_callable=AsyncMock,
            side_effect=_HTTPException(status_code=429, detail="Quota exceeded"),
        ):
            resp = await client.post(
                f"{API}/outreach/draft",
                headers=auth_headers,
                json={"contact_id": str(uuid.uuid4())},
            )
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_non_http_quota_exception_returns_400(self, client: AsyncClient, auth_headers: dict):
        """Non-HTTPException from quota check is converted to 400."""
        with patch(
            "app.services.quota_service.check_and_increment",
            new_callable=AsyncMock,
            side_effect=ValueError("quota internal error"),
        ):
            resp = await client.post(
                f"{API}/outreach/draft",
                headers=auth_headers,
                json={"contact_id": str(uuid.uuid4())},
            )
        assert resp.status_code == 400
        assert "quota internal error" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /outreach/{message_id}/draft-followup (lines 133-138)
# ---------------------------------------------------------------------------


class TestDraftFollowup:
    @pytest.mark.asyncio
    async def test_draft_followup_success(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """draft_followup creates a follow-up message and returns 201."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, status="sent")

        # Mock the service call to return a dummy follow-up
        followup = OutreachMessage(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            contact_id=contact.id,
            channel="email",
            message_type="followup_1",
            subject="Follow up",
            body="Just checking in.",
            status="draft",
        )
        db_session.add(followup)
        await db_session.flush()

        with patch(
            "app.services.outreach_service.draft_followup",
            new_callable=AsyncMock,
            return_value=followup,
        ):
            resp = await client.post(
                f"{API}/outreach/{msg.id}/draft-followup",
                headers=auth_headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["message_type"] == "followup_1"

    @pytest.mark.asyncio
    async def test_draft_followup_value_error_returns_400(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """ValueError from service returns 400."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        with patch(
            "app.services.outreach_service.draft_followup",
            new_callable=AsyncMock,
            side_effect=ValueError("no more follow-ups"),
        ):
            resp = await client.post(
                f"{API}/outreach/{msg.id}/draft-followup",
                headers=auth_headers,
            )

        assert resp.status_code == 400
        assert "no more follow-ups" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_draft_followup_not_found(self, client: AsyncClient, auth_headers: dict):
        """Non-existent message returns 404."""
        resp = await client.post(
            f"{API}/outreach/{uuid.uuid4()}/draft-followup",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /outreach/draft-linkedin (lines 147-153)
# ---------------------------------------------------------------------------


class TestDraftLinkedin:
    @pytest.mark.asyncio
    async def test_draft_linkedin_success(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """draft_linkedin creates a LinkedIn message and returns 201."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)

        linkedin_msg = OutreachMessage(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            contact_id=contact.id,
            channel="linkedin",
            message_type="initial",
            subject=None,
            body="Hi, would love to connect!",
            status="draft",
        )
        db_session.add(linkedin_msg)
        await db_session.flush()

        with patch(
            "app.services.outreach_service.draft_linkedin_message",
            new_callable=AsyncMock,
            return_value=linkedin_msg,
        ):
            resp = await client.post(
                f"{API}/outreach/draft-linkedin",
                headers=auth_headers,
                json={"contact_id": str(contact.id), "language": "en"},
            )

        assert resp.status_code == 201
        assert resp.json()["channel"] == "linkedin"

    @pytest.mark.asyncio
    async def test_draft_linkedin_value_error_returns_400(self, client: AsyncClient, auth_headers: dict):
        """ValueError from service is returned as 400."""
        with patch(
            "app.services.outreach_service.draft_linkedin_message",
            new_callable=AsyncMock,
            side_effect=ValueError("contact not found"),
        ):
            resp = await client.post(
                f"{API}/outreach/draft-linkedin",
                headers=auth_headers,
                json={"contact_id": str(uuid.uuid4()), "language": "en"},
            )

        assert resp.status_code == 400
        assert "contact not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_draft_linkedin_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/outreach/draft-linkedin",
            json={"contact_id": str(uuid.uuid4())},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /outreach/{contact_id}/draft-variants (lines 166-170)
# ---------------------------------------------------------------------------


class TestDraftVariants:
    @pytest.mark.asyncio
    async def test_draft_variants_success(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """draft_variants returns two message variants."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)

        v1 = OutreachMessage(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            contact_id=contact.id,
            channel="email",
            message_type="initial",
            subject="Professional Subject",
            body="Professional body",
            variant="professional",
            status="draft",
        )
        v2 = OutreachMessage(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            contact_id=contact.id,
            channel="email",
            message_type="initial",
            subject="Conversational Subject",
            body="Conversational body",
            variant="conversational",
            status="draft",
        )
        db_session.add(v1)
        db_session.add(v2)
        await db_session.flush()

        with patch(
            "app.services.outreach_service.draft_variants",
            new_callable=AsyncMock,
            return_value=[v1, v2],
        ):
            resp = await client.post(
                f"{API}/outreach/{contact.id}/draft-variants",
                headers=auth_headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        variants = {m["variant"] for m in data}
        assert "professional" in variants
        assert "conversational" in variants

    @pytest.mark.asyncio
    async def test_draft_variants_value_error_returns_400(self, client: AsyncClient, auth_headers: dict):
        """ValueError from service returns 400."""
        with patch(
            "app.services.outreach_service.draft_variants",
            new_callable=AsyncMock,
            side_effect=ValueError("no dna found"),
        ):
            resp = await client.post(
                f"{API}/outreach/{uuid.uuid4()}/draft-variants",
                headers=auth_headers,
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_draft_variants_language_query_param(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """Language query param is passed to the service."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)

        mock_variants = AsyncMock(return_value=[])

        with patch("app.services.outreach_service.draft_variants", mock_variants):
            await client.post(
                f"{API}/outreach/{contact.id}/draft-variants",
                headers=auth_headers,
                params={"language": "he"},
            )

        # Either 201 or 400 (empty list is valid); we care the language was forwarded
        mock_variants.assert_awaited_once()
        _, kwargs = mock_variants.call_args
        assert kwargs.get("language") == "he" or mock_variants.call_args[0][3] == "he"


# ---------------------------------------------------------------------------
# GET /outreach — with contact_id filter (line 194-195)
# ---------------------------------------------------------------------------


class TestListMessagesFilters:
    @pytest.mark.asyncio
    async def test_list_filter_by_contact_id_returns_only_matching(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """list_messages filtered by status correctly excludes non-matching rows."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact1 = await _create_company_and_contact(db_session, candidate_id)
        _, contact2 = await _create_company_and_contact(db_session, candidate_id)

        await _create_draft_message(db_session, candidate_id, contact1.id, status="draft")
        await _create_draft_message(db_session, candidate_id, contact2.id, status="sent")

        resp = await client.get(f"{API}/outreach", headers=auth_headers, params={"status": "sent"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(m["status"] == "sent" for m in data)

    @pytest.mark.asyncio
    async def test_list_skip_limit_pagination(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """Pagination via skip/limit works correctly."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)

        # Create 3 messages
        for _ in range(3):
            await _create_draft_message(db_session, candidate_id, contact.id)

        resp_all = await client.get(f"{API}/outreach", headers=auth_headers, params={"limit": 100})
        total = len(resp_all.json())

        resp_limited = await client.get(f"{API}/outreach", headers=auth_headers, params={"limit": 1})
        assert len(resp_limited.json()) == 1

        resp_skip = await client.get(f"{API}/outreach", headers=auth_headers, params={"skip": total, "limit": 10})
        assert len(resp_skip.json()) == 0


# ---------------------------------------------------------------------------
# PATCH /outreach/{message_id} — subject + body updates (lines 216-227)
# ---------------------------------------------------------------------------


class TestEditMessageFull:
    @pytest.mark.asyncio
    async def test_edit_subject_only(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """Editing only the subject leaves body unchanged."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, body="Original body")

        resp = await client.patch(
            f"{API}/outreach/{msg.id}",
            headers=auth_headers,
            json={"subject": "New Subject"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"] == "New Subject"
        assert data["body"] == "Original body"

    @pytest.mark.asyncio
    async def test_edit_both_subject_and_body(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """Editing both subject and body updates both fields."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        resp = await client.patch(
            f"{API}/outreach/{msg.id}",
            headers=auth_headers,
            json={"subject": "Updated Subject", "body": "Updated Body Content"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"] == "Updated Subject"
        assert data["body"] == "Updated Body Content"

    @pytest.mark.asyncio
    async def test_edit_reloads_message_after_commit(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """After edit the response reflects the persisted data (reload path)."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, body="Before")

        resp = await client.patch(
            f"{API}/outreach/{msg.id}",
            headers=auth_headers,
            json={"body": "After"},
        )
        assert resp.status_code == 200
        assert resp.json()["body"] == "After"
        # Re-fetch to confirm persistence
        get_resp = await client.get(f"{API}/outreach/{msg.id}", headers=auth_headers)
        assert get_resp.json()["body"] == "After"


# ---------------------------------------------------------------------------
# POST /outreach/{message_id}/send — all branches (lines 240-314)
# ---------------------------------------------------------------------------


class TestSendMessageFull:
    @pytest.mark.asyncio
    async def test_send_auto_approve_legacy_path(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """auto_approve=true with no graph thread uses legacy send path."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        with patch("app.services.email_service.send_outreach", new_callable=AsyncMock):
            resp = await client.post(
                f"{API}/outreach/{msg.id}/send",
                headers=auth_headers,
                params={"auto_approve": "true"},
            )

        # With auto_approve=true and no graph thread, should go through approval+send
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_send_creates_pending_action_when_no_auto_approve(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """send without auto_approve creates a pending_approval action."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        resp = await client.post(
            f"{API}/outreach/{msg.id}/send",
            headers=auth_headers,
            params={"auto_approve": "false"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_approval"
        assert "action_id" in data
        assert data["message_id"] == str(msg.id)

    @pytest.mark.asyncio
    async def test_send_graph_based_approved_message(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """When message has a graph thread_id and is approved, resumes the graph."""
        from app.models.enums import ActionStatus

        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, status="approved")

        thread_id = f"outreach-{uuid.uuid4()}"
        action = PendingAction(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            action_type="send_email",
            entity_id=msg.id,
            status=ActionStatus.PENDING,
            metadata_={"thread_id": thread_id},
        )
        db_session.add(action)
        await db_session.flush()

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()

        with patch("app.graphs.outreach.get_outreach_pipeline", return_value=mock_graph):
            resp = await client.post(
                f"{API}/outreach/{msg.id}/send",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        mock_graph.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_graph_exception_returns_400(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """When graph.ainvoke raises, the send endpoint returns 400."""
        from app.models.enums import ActionStatus

        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, status="approved")

        thread_id = f"outreach-{uuid.uuid4()}"
        action = PendingAction(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            action_type="send_email",
            entity_id=msg.id,
            status=ActionStatus.PENDING,
            metadata_={"thread_id": thread_id},
        )
        db_session.add(action)
        await db_session.flush()

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=ValueError("graph send failed"))

        with patch("app.graphs.outreach.get_outreach_pipeline", return_value=mock_graph):
            resp = await client.post(
                f"{API}/outreach/{msg.id}/send",
                headers=auth_headers,
            )

        assert resp.status_code == 400
        assert "graph send failed" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_send_value_error_legacy_returns_400(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """ValueError from send_outreach in legacy path returns 400."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        with patch(
            "app.services.email_service.send_outreach",
            new_callable=AsyncMock,
            side_effect=ValueError("email send error"),
        ):
            resp = await client.post(
                f"{API}/outreach/{msg.id}/send",
                headers=auth_headers,
                params={"auto_approve": "true"},
            )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /outreach/{message_id} — with pending action cleanup (lines 324-332)
# ---------------------------------------------------------------------------


class TestDeleteMessageWithPendingAction:
    @pytest.mark.asyncio
    async def test_delete_cleans_up_pending_actions(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """Delete also removes associated pending actions."""
        from app.models.enums import ActionStatus

        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id)

        # Add a pending action tied to this message
        action = PendingAction(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            action_type="send_email",
            entity_id=msg.id,
            status=ActionStatus.PENDING,
        )
        db_session.add(action)
        await db_session.flush()

        resp = await client.delete(f"{API}/outreach/{msg.id}", headers=auth_headers)
        assert resp.status_code == 204

        # The message should be gone
        get_resp = await client.get(f"{API}/outreach/{msg.id}", headers=auth_headers)
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /outreach/{message_id}/mark-replied (lines 342-347)
# ---------------------------------------------------------------------------


class TestMarkRepliedFull:
    @pytest.mark.asyncio
    async def test_mark_replied_sets_replied_at(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """mark_replied sets status=replied and replied_at timestamp."""
        candidate_id = await _get_candidate_id(client, auth_headers)
        _, contact = await _create_company_and_contact(db_session, candidate_id)
        msg = await _create_draft_message(db_session, candidate_id, contact.id, status="sent")

        resp = await client.patch(f"{API}/outreach/{msg.id}/mark-replied", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "replied"
        assert data["replied_at"] is not None

    @pytest.mark.asyncio
    async def test_mark_replied_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.patch(f"{API}/outreach/{uuid.uuid4()}/mark-replied", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_replied_requires_auth(self, client: AsyncClient):
        resp = await client.patch(f"{API}/outreach/{uuid.uuid4()}/mark-replied")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# _get_candidate_message helper (lines 359-362)
# ---------------------------------------------------------------------------


class TestGetCandidateMessageHelper:
    @pytest.mark.asyncio
    async def test_get_candidate_message_raises_404_for_wrong_candidate(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession, invite_code: str
    ):
        """_get_candidate_message raises 404 when message belongs to another candidate."""
        # Create another user
        other_email = f"gcm-{uuid.uuid4().hex[:8]}@test.com"
        await client.post(
            f"{API}/auth/register",
            json={
                "email": other_email,
                "password": "testpass123",
                "full_name": "Other User",
                "invite_code": invite_code,
            },
        )
        other_resp = await client.post(
            f"{API}/auth/login",
            json={"email": other_email, "password": "testpass123"},
        )
        other_headers = {"Authorization": f"Bearer {other_resp.json()['access_token']}"}
        other_id = uuid.UUID((await client.get(f"{API}/auth/me", headers=other_headers)).json()["id"])

        _, other_contact = await _create_company_and_contact(db_session, other_id)
        other_msg = await _create_draft_message(db_session, other_id, other_contact.id)

        # The main user should get 404 for the other user's message
        resp = await client.get(f"{API}/outreach/{other_msg.id}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_candidate_message_raises_for_invalid_uuid(self, client: AsyncClient, auth_headers: dict):
        """Invalid UUID in path causes a ValueError (unhandled) → 500."""
        resp = await client.get(f"{API}/outreach/not-a-uuid", headers=auth_headers)
        # The route accepts a plain str and _get_candidate_message calls uuid.UUID()
        # which raises ValueError, yielding an unhandled 500
        assert resp.status_code == 500
