"""Unit tests for contact_service - no real DB or Hunter.io required."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.contact_service import (
    find_contact,
    prioritize_contacts,
    verify_contact,
)

_UNSET = object()


def _make_db(first_result=None, second_result=_UNSET):
    """Return an AsyncMock DB session with pre-configured execute side_effects."""
    db = AsyncMock()

    def _make_result(val):
        r = MagicMock()
        r.scalar_one_or_none.return_value = val
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = val if isinstance(val, list) else ([val] if val else [])
        r.scalars.return_value = scalars_mock
        return r

    if second_result is not _UNSET:
        db.execute.side_effect = [
            _make_result(first_result),
            _make_result(second_result),
        ]
    else:
        db.execute.return_value = _make_result(first_result)

    return db


# ---------------------------------------------------------------------------
# find_contact
# ---------------------------------------------------------------------------


class TestFindContact:
    @pytest.mark.asyncio
    async def test_find_contact_creates_new(self):
        """Company exists but no existing contact → new Contact is created."""
        company = MagicMock()
        company.id = uuid.uuid4()
        company.domain = "acme.com"
        company.size_range = "11-50"

        # First execute → company, second execute → no existing contact
        db = _make_db(first_result=company, second_result=None)

        hunter = AsyncMock()
        hunter.email_finder.return_value = {
            "email": "john.doe@acme.com",
            "confidence": 85,
            "position": "Engineering Manager",
        }

        candidate_id = uuid.uuid4()
        company_id = company.id

        with (
            patch("app.services.contact_service.get_hunter", return_value=hunter),
            patch("app.services.contact_service.get_company_size_tier", return_value="small"),
            patch(
                "app.services.contact_service.compute_contact_priority",
                return_value=("hiring_manager", True, 80),
            ),
        ):
            await find_contact(db, company_id, candidate_id, "John", "Doe")

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()
        added = db.add.call_args[0][0]
        assert added.full_name == "John Doe"
        assert added.email == "john.doe@acme.com"

    @pytest.mark.asyncio
    async def test_find_contact_updates_existing(self):
        """Contact already exists → updates confidence and title."""
        company = MagicMock()
        company.id = uuid.uuid4()
        company.domain = "acme.com"
        company.size_range = "51-200"

        existing_contact = MagicMock()
        existing_contact.email_confidence = 50
        existing_contact.title = "Engineer"

        db = _make_db(first_result=company, second_result=existing_contact)

        hunter = AsyncMock()
        hunter.email_finder.return_value = {
            "email": "jane.smith@acme.com",
            "confidence": 95,
            "position": "Senior Engineer",
        }

        with patch("app.services.contact_service.get_hunter", return_value=hunter):
            await find_contact(db, company.id, uuid.uuid4(), "Jane", "Smith")

        assert existing_contact.email_confidence == 95
        assert existing_contact.title == "Senior Engineer"
        db.add.assert_not_called()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_find_contact_company_not_found(self):
        """No company → raises ValueError."""
        db = _make_db(first_result=None)

        with pytest.raises(ValueError, match="Company not found"):
            await find_contact(db, uuid.uuid4(), uuid.uuid4(), "Alice", "Jones")


# ---------------------------------------------------------------------------
# verify_contact
# ---------------------------------------------------------------------------


class TestVerifyContact:
    @pytest.mark.asyncio
    async def test_verify_contact_deliverable(self):
        """Verifier returns deliverable → email_verified=True."""
        contact = MagicMock()
        contact.email = "alice@example.com"
        contact.email_verified = False
        contact.email_confidence = 0

        db = _make_db(first_result=contact)

        hunter = AsyncMock()
        hunter.email_verifier.return_value = {"result": "deliverable", "score": 92}

        with patch("app.services.contact_service.get_hunter", return_value=hunter):
            await verify_contact(db, contact.id)

        assert contact.email_verified is True
        assert contact.email_confidence == 92
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_contact_not_deliverable(self):
        """Verifier returns undeliverable → email_verified=False."""
        contact = MagicMock()
        contact.email = "bad@example.com"
        contact.email_verified = True

        db = _make_db(first_result=contact)

        hunter = AsyncMock()
        hunter.email_verifier.return_value = {"result": "undeliverable", "score": 10}

        with patch("app.services.contact_service.get_hunter", return_value=hunter):
            await verify_contact(db, contact.id)

        assert contact.email_verified is False

    @pytest.mark.asyncio
    async def test_verify_contact_not_found(self):
        """No contact → raises ValueError."""
        db = _make_db(first_result=None)

        with pytest.raises(ValueError, match="Contact not found"):
            await verify_contact(db, uuid.uuid4())


# ---------------------------------------------------------------------------
# prioritize_contacts
# ---------------------------------------------------------------------------


class TestPrioritizeContacts:
    @pytest.mark.asyncio
    async def test_prioritize_contacts(self):
        """Returns contacts in priority order."""
        c1 = MagicMock()
        c1.outreach_priority = 90
        c2 = MagicMock()
        c2.outreach_priority = 50

        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [c1, c2]
        result_mock.scalars.return_value = scalars_mock

        db = AsyncMock()
        db.execute.return_value = result_mock

        contacts = await prioritize_contacts(db, uuid.uuid4())

        assert contacts == [c1, c2]
        assert len(contacts) == 2

    @pytest.mark.asyncio
    async def test_prioritize_contacts_empty(self):
        """Returns empty list when no contacts exist."""
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock.scalars.return_value = scalars_mock

        db = AsyncMock()
        db.execute.return_value = result_mock

        contacts = await prioritize_contacts(db, uuid.uuid4())
        assert contacts == []
