import json
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_openai
from app.models.candidate import CandidateDNA
from app.models.company import Company, CompanyDossier
from app.models.contact import Contact
from app.models.outreach import OutreachMessage

logger = structlog.get_logger()

MESSAGE_SEQUENCE = ["initial", "followup_1", "followup_2", "breakup"]

OUTREACH_PROMPT = """You are a career outreach specialist. Draft a personalized {message_type} email from a job candidate to a potential contact at a target company.

CANDIDATE PROFILE:
{candidate_summary}

COMPANY DOSSIER:
Company: {company_name} ({domain})
Industry: {industry}
Tech Stack: {tech_stack}
Culture: {culture_summary}
Why I'm a fit: {why_hire_me}
Recent news: {recent_news}

CONTACT:
Name: {contact_name}
Title: {contact_title}
Role: {contact_role}

INSTRUCTIONS:
- Reference the candidate's REAL experience — do not fabricate achievements
- Reference specific details about the company (recent news, tech stack, culture)
- Keep it concise: 100-150 words for initial, 50-80 for follow-ups
- Professional but warm tone — not robotic, not overly casual
- Include a clear, low-pressure call to action
- {message_type_instructions}

Return a JSON object with:
- subject: email subject line
- body: email body (plain text, no HTML)
- personalization_points: array of strings explaining what was personalized"""

OUTREACH_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
        "personalization_points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject", "body", "personalization_points"],
    "additionalProperties": False,
}

MESSAGE_TYPE_INSTRUCTIONS = {
    "initial": "This is the first outreach. Make a strong first impression. Reference something specific about the company.",
    "followup_1": "This is a follow-up to an unanswered initial email. Add new value — share a relevant insight or accomplishment. Don't guilt-trip.",
    "followup_2": "Second follow-up. Keep it very brief. Reference a new angle or recent company news. Last chance before the breakup.",
    "breakup": "Final message. Very short. Let them know this is the last email. Leave the door open with grace.",
}

LINKEDIN_PROMPT = """Draft a short LinkedIn message (max 300 characters for connection request, or ~100 words for InMail) from a job candidate to a contact.

CANDIDATE: {candidate_summary}
COMPANY: {company_name} — {culture_summary}
CONTACT: {contact_name}, {contact_title}

Keep it casual, specific, and ask to connect. Reference one specific thing about them or the company.

Return JSON with subject (for InMail, null for connection) and body."""


async def draft_message(
    db: AsyncSession, candidate_id: uuid.UUID, contact_id: uuid.UUID
) -> OutreachMessage:
    """Draft a personalized outreach email."""
    # Load all context
    contact = await _get_contact(db, contact_id)
    company = await _get_company(db, contact.company_id)
    dossier = await _get_dossier(db, company.id)
    dna = await _get_dna(db, candidate_id)

    # Determine message type (check existing messages for this contact)
    existing = await db.execute(
        select(OutreachMessage).where(
            OutreachMessage.contact_id == contact_id,
            OutreachMessage.candidate_id == candidate_id,
            OutreachMessage.channel == "email",
        ).order_by(OutreachMessage.created_at.desc())
    )
    existing_messages = existing.scalars().all()
    message_type = _next_message_type(existing_messages)

    client = get_openai()
    prompt = OUTREACH_PROMPT.format(
        message_type=message_type,
        candidate_summary=dna.experience_summary if dna else "No candidate profile",
        company_name=company.name,
        domain=company.domain,
        industry=company.industry or "Unknown",
        tech_stack=", ".join(company.tech_stack or []),
        culture_summary=dossier.culture_summary if dossier else "Unknown",
        why_hire_me=dossier.why_hire_me if dossier else "Strong candidate fit",
        recent_news=json.dumps(dossier.recent_news) if dossier and dossier.recent_news else "None",
        contact_name=contact.full_name,
        contact_title=contact.title or "Unknown",
        contact_role=contact.role_type or "Unknown",
        message_type_instructions=MESSAGE_TYPE_INSTRUCTIONS.get(message_type, ""),
    )

    result = await client.parse_structured(prompt, "", OUTREACH_SCHEMA)

    message = OutreachMessage(
        id=uuid.uuid4(),
        contact_id=contact_id,
        candidate_id=candidate_id,
        channel="email",
        message_type=message_type,
        subject=result["subject"],
        body=result["body"],
        personalization_data={"points": result.get("personalization_points", [])},
        status="draft",
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    logger.info("outreach_drafted", message_id=str(message.id), type=message_type)
    return message


async def draft_followup(db: AsyncSession, outreach_id: uuid.UUID) -> OutreachMessage:
    """Draft the next follow-up in the sequence."""
    result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == outreach_id))
    original = result.scalar_one_or_none()
    if not original:
        raise ValueError("Original message not found")

    return await draft_message(db, original.candidate_id, original.contact_id)


async def draft_linkedin_message(
    db: AsyncSession, candidate_id: uuid.UUID, contact_id: uuid.UUID
) -> OutreachMessage:
    """Draft a LinkedIn connection/InMail message."""
    contact = await _get_contact(db, contact_id)
    company = await _get_company(db, contact.company_id)
    dossier = await _get_dossier(db, company.id)
    dna = await _get_dna(db, candidate_id)

    client = get_openai()
    prompt = LINKEDIN_PROMPT.format(
        candidate_summary=dna.experience_summary if dna else "Experienced professional",
        company_name=company.name,
        culture_summary=dossier.culture_summary if dossier else "Great company",
        contact_name=contact.full_name,
        contact_title=contact.title or "Professional",
    )

    result = await client.parse_structured(prompt, "", OUTREACH_SCHEMA)

    message = OutreachMessage(
        id=uuid.uuid4(),
        contact_id=contact_id,
        candidate_id=candidate_id,
        channel="linkedin",
        message_type="initial",
        subject=result.get("subject"),
        body=result["body"],
        personalization_data={"points": result.get("personalization_points", [])},
        status="draft",
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    logger.info("linkedin_message_drafted", message_id=str(message.id))
    return message


def _next_message_type(existing_messages: list[OutreachMessage]) -> str:
    """Determine the next message type in the sequence."""
    if not existing_messages:
        return "initial"
    last_type = existing_messages[0].message_type
    try:
        idx = MESSAGE_SEQUENCE.index(last_type)
        if idx + 1 < len(MESSAGE_SEQUENCE):
            return MESSAGE_SEQUENCE[idx + 1]
    except ValueError:
        pass
    return "breakup"


async def _get_contact(db: AsyncSession, contact_id: uuid.UUID) -> Contact:
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise ValueError("Contact not found")
    return contact


async def _get_company(db: AsyncSession, company_id: uuid.UUID) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise ValueError("Company not found")
    return company


async def _get_dossier(db: AsyncSession, company_id: uuid.UUID) -> CompanyDossier | None:
    result = await db.execute(select(CompanyDossier).where(CompanyDossier.company_id == company_id))
    return result.scalar_one_or_none()


async def _get_dna(db: AsyncSession, candidate_id: uuid.UUID) -> CandidateDNA | None:
    result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
    return result.scalar_one_or_none()
