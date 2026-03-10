"""Unit tests for invite_service – no real DB required."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.invite_service import (
    create_invite,
    list_invites,
    validate_and_consume,
    validate_invite,
)


def _make_candidate(candidate_id=None):
    """Create a mock Candidate object."""
    c = MagicMock()
    c.id = candidate_id or uuid.uuid4()
    c.email = "inviter@example.com"
    c.full_name = "Test Inviter"
    return c


def _make_invite(*, code="abc123", is_used=False, expired=False, invite_id=None):
    """Create a mock InviteCode object."""
    inv = MagicMock()
    inv.id = invite_id or uuid.uuid4()
    inv.code = code
    inv.is_used = is_used
    if expired:
        inv.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        inv.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    inv.invited_by = _make_candidate()
    return inv


# ---------------------------------------------------------------------------
# create_invite
# ---------------------------------------------------------------------------

class TestCreateInvite:
    @pytest.mark.asyncio
    async def test_create_invite_success(self):
        db = AsyncMock()
        candidate = _make_candidate()

        with patch("app.services.invite_service.settings") as mock_s:
            mock_s.INVITE_EXPIRE_DAYS = 7
            invite = await create_invite(db, candidate)

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_invite_sets_invited_by(self):
        db = AsyncMock()
        candidate = _make_candidate()

        with patch("app.services.invite_service.settings") as mock_s:
            mock_s.INVITE_EXPIRE_DAYS = 7
            await create_invite(db, candidate)

        added_obj = db.add.call_args[0][0]
        assert added_obj.invited_by_id == candidate.id


# ---------------------------------------------------------------------------
# validate_invite
# ---------------------------------------------------------------------------

class TestValidateInvite:
    @pytest.mark.asyncio
    async def test_validate_invite_success(self):
        inv = _make_invite()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inv
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await validate_invite(db, "abc123")
        assert result == inv

    @pytest.mark.asyncio
    async def test_validate_invite_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await validate_invite(db, "nonexistent")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_validate_invite_already_used(self):
        inv = _make_invite(is_used=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inv
        db = AsyncMock()
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await validate_invite(db, "abc123")
        assert exc_info.value.status_code == 410
        assert "already been used" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_invite_expired(self):
        inv = _make_invite(expired=True)
        inv.is_used = False
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inv
        db = AsyncMock()
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await validate_invite(db, "abc123")
        assert exc_info.value.status_code == 410
        assert "expired" in exc_info.value.detail


# ---------------------------------------------------------------------------
# validate_and_consume
# ---------------------------------------------------------------------------

class TestValidateAndConsume:
    @pytest.mark.asyncio
    async def test_consume_success(self):
        inv = _make_invite()
        used_by_id = uuid.uuid4()

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = inv

        mock_update_result = MagicMock()
        mock_update_result.rowcount = 1

        db = AsyncMock()
        db.execute.side_effect = [mock_select_result, mock_update_result]

        result = await validate_and_consume(db, "abc123", used_by_id)
        assert result == inv

    @pytest.mark.asyncio
    async def test_consume_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_consume(db, "missing", uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_consume_expired(self):
        inv = _make_invite(expired=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inv
        db = AsyncMock()
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_consume(db, "abc123", uuid.uuid4())
        assert exc_info.value.status_code == 410

    @pytest.mark.asyncio
    async def test_consume_race_condition_double_use(self):
        """Simulates a race condition where the atomic UPDATE finds is_used=True."""
        inv = _make_invite()

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = inv

        mock_update_result = MagicMock()
        mock_update_result.rowcount = 0  # another request consumed it first

        db = AsyncMock()
        db.execute.side_effect = [mock_select_result, mock_update_result]

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_consume(db, "abc123", uuid.uuid4())
        assert exc_info.value.status_code == 410
        assert "already been used" in exc_info.value.detail


# ---------------------------------------------------------------------------
# list_invites
# ---------------------------------------------------------------------------

class TestListInvites:
    @pytest.mark.asyncio
    async def test_list_invites_returns_list(self):
        inv1 = _make_invite(code="a")
        inv2 = _make_invite(code="b")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [inv1, inv2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute.return_value = mock_result

        candidate = _make_candidate()
        result = await list_invites(db, candidate)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_invites_empty(self):
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute.return_value = mock_result

        candidate = _make_candidate()
        result = await list_invites(db, candidate)
        assert result == []
