"""Unit tests for outreach_service helper functions - no real DB or OpenAI required."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.outreach_service import (
    _get_company,
    _get_contact,
    _get_dna,
    _next_message_type,
    draft_followup,
)

# ---------------------------------------------------------------------------
# _next_message_type
# ---------------------------------------------------------------------------


class TestNextMessageType:
    def test_next_message_type_no_existing(self):
        """Empty list → returns 'initial'."""
        assert _next_message_type([]) == "initial"

    def test_next_message_type_after_initial(self):
        """Last message is 'initial' → returns 'followup_1'."""
        msg = MagicMock()
        msg.message_type = "initial"
        assert _next_message_type([msg]) == "followup_1"

    def test_next_message_type_after_followup_1(self):
        """Last message is 'followup_1' → returns 'followup_2'."""
        msg = MagicMock()
        msg.message_type = "followup_1"
        assert _next_message_type([msg]) == "followup_2"

    def test_next_message_type_after_followup_2(self):
        """Last message is 'followup_2' → returns 'breakup'."""
        msg = MagicMock()
        msg.message_type = "followup_2"
        assert _next_message_type([msg]) == "breakup"

    def test_next_message_type_after_breakup(self):
        """Last message is 'breakup' → stays 'breakup'."""
        msg = MagicMock()
        msg.message_type = "breakup"
        assert _next_message_type([msg]) == "breakup"

    def test_next_message_type_unknown(self):
        """Unknown message type → returns 'breakup' as safe fallback."""
        msg = MagicMock()
        msg.message_type = "mystery_type"
        assert _next_message_type([msg]) == "breakup"

    def test_next_message_type_uses_first_message(self):
        """Uses messages[0] (most recent) not the last element."""
        msg_recent = MagicMock()
        msg_recent.message_type = "followup_1"
        msg_old = MagicMock()
        msg_old.message_type = "initial"
        # Most recent first → should advance from followup_1
        assert _next_message_type([msg_recent, msg_old]) == "followup_2"


# ---------------------------------------------------------------------------
# draft_followup
# ---------------------------------------------------------------------------


class TestDraftFollowup:
    @pytest.mark.asyncio
    async def test_draft_followup_not_found(self):
        """Outreach ID not found → raises ValueError."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="Original message not found"):
            await draft_followup(db, uuid.uuid4())


# ---------------------------------------------------------------------------
# _get_contact
# ---------------------------------------------------------------------------


class TestGetContact:
    @pytest.mark.asyncio
    async def test_get_contact_found(self):
        """Returns contact when it exists."""
        contact = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contact

        db = AsyncMock()
        db.execute.return_value = result_mock

        result = await _get_contact(db, uuid.uuid4(), uuid.uuid4())
        assert result is contact

    @pytest.mark.asyncio
    async def test_get_contact_not_found(self):
        """Raises ValueError when contact does not exist."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="Contact not found"):
            await _get_contact(db, uuid.uuid4(), uuid.uuid4())


# ---------------------------------------------------------------------------
# _get_company
# ---------------------------------------------------------------------------


class TestGetCompany:
    @pytest.mark.asyncio
    async def test_get_company_found(self):
        """Returns company when it exists."""
        company = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = company

        db = AsyncMock()
        db.execute.return_value = result_mock

        result = await _get_company(db, uuid.uuid4())
        assert result is company

    @pytest.mark.asyncio
    async def test_get_company_not_found(self):
        """Raises ValueError when company does not exist."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="Company not found"):
            await _get_company(db, uuid.uuid4())


# ---------------------------------------------------------------------------
# _get_dna
# ---------------------------------------------------------------------------


class TestGetDna:
    @pytest.mark.asyncio
    async def test_get_dna_found(self):
        """Returns DNA when it exists."""
        dna = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = dna

        db = AsyncMock()
        db.execute.return_value = result_mock

        result = await _get_dna(db, uuid.uuid4())
        assert result is dna

    @pytest.mark.asyncio
    async def test_get_dna_not_found_returns_none(self):
        """Returns None (does NOT raise) when DNA does not exist."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.return_value = result_mock

        result = await _get_dna(db, uuid.uuid4())
        assert result is None
