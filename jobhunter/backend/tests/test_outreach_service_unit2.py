"""Additional unit tests for outreach_service - covers draft_message (variant
instruction), draft_linkedin_message, draft_variants, and
_get_contact_with_company (company not found)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.outreach_service import (
    _get_contact_with_company,
    draft_linkedin_message,
    draft_message,
    draft_variants,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    return r


def _make_contact(company_id=None, full_name="Alice", title="Engineer", role_type="tech"):
    contact = MagicMock()
    contact.id = uuid.uuid4()
    contact.full_name = full_name
    contact.title = title
    contact.role_type = role_type
    contact.company_id = company_id or uuid.uuid4()
    contact.company = MagicMock(
        id=uuid.uuid4(),
        name="Acme Corp",
        domain="acme.com",
        industry="Tech",
        tech_stack=["Python", "FastAPI"],
    )
    return contact


def _make_db_for_draft_message(contact, dna, dossier, existing_msgs=None):
    """Set up a mock DB that serves the draft_message call pattern."""
    db = AsyncMock()

    # draft_message does asyncio.gather(_get_contact_with_company, _get_dna)
    # then _get_dossier, then existing messages query, all via db.execute

    contact_result = _scalar_result(contact)
    dna_result = _scalar_result(dna)
    dossier_result = _scalar_result(dossier)

    existing_result = MagicMock()
    existing_result.scalars.return_value = MagicMock(all=MagicMock(return_value=existing_msgs or []))

    db.execute.side_effect = [
        contact_result,  # _get_contact_with_company
        dna_result,  # _get_dna
        dossier_result,  # _get_dossier
        existing_result,  # existing messages
    ]
    return db


def _make_openai_stub():
    stub = AsyncMock()
    stub.parse_structured = AsyncMock(
        return_value={
            "subject": "Test Subject",
            "body": "Test body text",
            "personalization_points": ["point1"],
        }
    )
    return stub


# ---------------------------------------------------------------------------
# draft_message with variant instruction (line 131)
# ---------------------------------------------------------------------------


class TestDraftMessageVariant:
    @pytest.mark.asyncio
    async def test_draft_message_with_professional_variant(self):
        """draft_message with variant='professional' sets variant_instruction."""
        contact = _make_contact()
        dna = MagicMock(experience_summary="5 years Python")
        dossier = MagicMock(
            culture_summary="Fast-paced",
            why_hire_me="Strong fit",
            recent_news=None,
        )

        db = _make_db_for_draft_message(contact, dna, dossier)
        openai_stub = _make_openai_stub()

        with patch("app.services.outreach_service.get_openai", return_value=openai_stub):
            msg = await draft_message(db, uuid.uuid4(), contact.id, variant="professional")

        assert msg.variant == "professional"
        assert msg.subject == "Test Subject"
        assert msg.body == "Test body text"
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_draft_message_with_conversational_variant(self):
        """draft_message with variant='conversational' includes tone instruction."""
        contact = _make_contact()
        dna = MagicMock(experience_summary="Full stack dev")
        dossier = MagicMock(
            culture_summary="Remote-first",
            why_hire_me="Culture fit",
            recent_news=[{"title": "News item"}],
        )

        db = _make_db_for_draft_message(contact, dna, dossier)
        openai_stub = _make_openai_stub()

        with patch("app.services.outreach_service.get_openai", return_value=openai_stub):
            msg = await draft_message(db, uuid.uuid4(), contact.id, variant="conversational")

        assert msg.variant == "conversational"

    @pytest.mark.asyncio
    async def test_draft_message_unknown_variant_ignored(self):
        """Unknown variant is not applied (falls through the if-check)."""
        contact = _make_contact()
        dna = MagicMock(experience_summary="Developer")
        dossier = None  # no dossier → uses defaults

        db = _make_db_for_draft_message(contact, dna, dossier)
        openai_stub = _make_openai_stub()

        with patch("app.services.outreach_service.get_openai", return_value=openai_stub):
            msg = await draft_message(db, uuid.uuid4(), contact.id, variant="nonexistent")

        # variant stored as-is, but no TONE instruction added
        assert msg.variant == "nonexistent"

    @pytest.mark.asyncio
    async def test_draft_followup_calls_draft_message(self):
        """draft_message for followup uses correct message_type based on existing."""
        contact = _make_contact()
        dna = MagicMock(experience_summary="Developer")
        dossier = None

        existing_msg = MagicMock()
        existing_msg.message_type = "initial"

        db = _make_db_for_draft_message(contact, dna, dossier, existing_msgs=[existing_msg])
        openai_stub = _make_openai_stub()

        with patch("app.services.outreach_service.get_openai", return_value=openai_stub):
            msg = await draft_message(db, uuid.uuid4(), contact.id)

        assert msg.message_type == "followup_1"


# ---------------------------------------------------------------------------
# draft_linkedin_message (lines 185-219)
# ---------------------------------------------------------------------------


class TestDraftLinkedinMessage:
    @pytest.mark.asyncio
    async def test_draft_linkedin_message_success(self):
        """draft_linkedin_message creates a linkedin OutreachMessage."""
        contact_id = uuid.uuid4()
        company_id = uuid.uuid4()

        contact = MagicMock()
        contact.id = contact_id
        contact.company_id = company_id
        contact.full_name = "Bob Builder"
        contact.title = "CTO"

        company = MagicMock()
        company.id = company_id
        company.name = "BuildCo"

        dossier = MagicMock()
        dossier.culture_summary = "Build great things"

        dna = MagicMock()
        dna.experience_summary = "Senior engineer"

        db = AsyncMock()
        db.execute.side_effect = [
            _scalar_result(contact),  # _get_contact
            _scalar_result(company),  # _get_company
            _scalar_result(dossier),  # _get_dossier
            _scalar_result(dna),  # _get_dna
        ]

        openai_stub = _make_openai_stub()
        openai_stub.parse_structured = AsyncMock(
            return_value={
                "subject": None,
                "body": "Would love to connect!",
                "personalization_points": [],
            }
        )

        with patch("app.services.outreach_service.get_openai", return_value=openai_stub):
            msg = await draft_linkedin_message(db, uuid.uuid4(), contact_id)

        assert msg.channel == "linkedin"
        assert msg.message_type == "initial"
        assert msg.body == "Would love to connect!"
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_draft_linkedin_message_no_dna(self):
        """Works with no DNA (uses default summary)."""
        contact_id = uuid.uuid4()
        company_id = uuid.uuid4()

        contact = MagicMock()
        contact.id = contact_id
        contact.company_id = company_id
        contact.full_name = "Carol Dev"
        contact.title = "VP Engineering"

        company = MagicMock()
        company.id = company_id
        company.name = "StartupXYZ"

        db = AsyncMock()
        db.execute.side_effect = [
            _scalar_result(contact),
            _scalar_result(company),
            _scalar_result(None),  # no dossier
            _scalar_result(None),  # no dna
        ]

        openai_stub = _make_openai_stub()

        with patch("app.services.outreach_service.get_openai", return_value=openai_stub):
            msg = await draft_linkedin_message(db, uuid.uuid4(), contact_id, language="he")

        assert msg.channel == "linkedin"

    @pytest.mark.asyncio
    async def test_draft_linkedin_message_contact_not_found(self):
        """Raises ValueError when contact not found."""
        db = AsyncMock()
        db.execute.return_value = _scalar_result(None)

        with pytest.raises(ValueError, match="Contact not found"):
            await draft_linkedin_message(db, uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_draft_linkedin_message_company_not_found(self):
        """Raises ValueError when company not found."""
        contact_id = uuid.uuid4()

        contact = MagicMock()
        contact.id = contact_id
        contact.company_id = uuid.uuid4()

        db = AsyncMock()
        db.execute.side_effect = [
            _scalar_result(contact),  # _get_contact OK
            _scalar_result(None),  # _get_company → not found
        ]

        with pytest.raises(ValueError, match="Company not found"):
            await draft_linkedin_message(db, uuid.uuid4(), contact_id)


# ---------------------------------------------------------------------------
# draft_variants (lines 226-230)
# ---------------------------------------------------------------------------


class TestDraftVariants:
    @pytest.mark.asyncio
    async def test_draft_variants_returns_two_messages(self):
        """draft_variants calls draft_message twice and returns two messages."""
        contact = _make_contact()
        dna = MagicMock(experience_summary="Dev")
        dossier = None

        db = AsyncMock()

        # Each draft_message call needs: contact, dna, dossier, existing_msgs
        def make_db_side_effects():
            """4 execute calls per draft_message call, 2 calls = 8 total."""
            contact_r = _scalar_result(contact)
            dna_r = _scalar_result(dna)
            dossier_r = _scalar_result(dossier)
            existing_r = MagicMock()
            existing_r.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
            return [contact_r, dna_r, dossier_r, existing_r]

        db.execute.side_effect = make_db_side_effects() + make_db_side_effects()
        openai_stub = _make_openai_stub()

        with patch("app.services.outreach_service.get_openai", return_value=openai_stub):
            variants = await draft_variants(db, uuid.uuid4(), contact.id)

        assert len(variants) == 2
        assert variants[0].variant == "professional"
        assert variants[1].variant == "conversational"


# ---------------------------------------------------------------------------
# _get_contact_with_company (lines 259, 261)
# ---------------------------------------------------------------------------


class TestGetContactWithCompany:
    @pytest.mark.asyncio
    async def test_raises_when_contact_not_found(self):
        """Raises ValueError when contact is missing."""
        db = AsyncMock()
        db.execute.return_value = _scalar_result(None)

        with pytest.raises(ValueError, match="Contact not found"):
            await _get_contact_with_company(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_company_not_loaded(self):
        """Raises ValueError when contact has no company (selectinload returns None)."""
        contact = MagicMock()
        contact.company = None  # company relationship not loaded / doesn't exist

        db = AsyncMock()
        db.execute.return_value = _scalar_result(contact)

        with pytest.raises(ValueError, match="Company not found"):
            await _get_contact_with_company(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_returns_contact_with_company(self):
        """Returns contact when both contact and company are present."""
        company = MagicMock()
        company.name = "Stripe"

        contact = MagicMock()
        contact.company = company

        db = AsyncMock()
        db.execute.return_value = _scalar_result(contact)

        result = await _get_contact_with_company(db, uuid.uuid4())

        assert result is contact
        assert result.company.name == "Stripe"
