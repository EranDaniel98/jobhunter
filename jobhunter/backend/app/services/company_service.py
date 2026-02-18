import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_hunter, get_openai
from app.models.candidate import CandidateDNA
from app.models.company import Company, CompanyDossier
from app.models.contact import Contact
from app.services.embedding_service import cosine_similarity, embed_text

logger = structlog.get_logger()

DOSSIER_PROMPT = """You are a company research analyst. Based on the following company data, generate a comprehensive dossier.

Company: {company_name} ({domain})
Industry: {industry}
Size: {size}
Location: {location}
Description: {description}
Tech Stack: {tech_stack}

Also consider this candidate's background when generating "why_hire_me":
{candidate_summary}

Generate a JSON dossier with:
- culture_summary: 2-3 sentences about company culture
- culture_score: 1-10 rating
- red_flags: array of potential concerns (empty if none)
- interview_format: typical interview process
- interview_questions: array of likely questions
- compensation_data: object with range, equity, benefits
- key_people: array of {{name, title}} for leadership
- why_hire_me: 2-3 sentences explaining why THIS candidate would be valuable to THIS company
- recent_news: array of {{title, date}} for notable events"""

DOSSIER_SCHEMA = {
    "type": "object",
    "properties": {
        "culture_summary": {"type": "string"},
        "culture_score": {"type": "number"},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "interview_format": {"type": "string"},
        "interview_questions": {"type": "array", "items": {"type": "string"}},
        "compensation_data": {
            "type": "object",
            "properties": {
                "range": {"type": "string"},
                "equity": {"type": "string"},
                "benefits": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["range", "equity", "benefits"],
            "additionalProperties": False,
        },
        "key_people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["name", "title"],
                "additionalProperties": False,
            },
        },
        "why_hire_me": {"type": "string"},
        "recent_news": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["title", "date"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["culture_summary", "culture_score", "red_flags", "interview_format", "interview_questions", "compensation_data", "key_people", "why_hire_me", "recent_news"],
    "additionalProperties": False,
}


async def discover_companies(
    db: AsyncSession, candidate_id: uuid.UUID
) -> list[Company]:
    """Proactively discover companies based on candidate DNA and targets."""
    from app.models.candidate import Candidate

    # Get candidate profile and DNA
    cand_result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        raise ValueError("Candidate not found")

    dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
    dna = dna_result.scalar_one_or_none()

    hunter = get_hunter()

    # Build search queries from candidate targets
    domains_to_search = set()
    industries = candidate.target_industries or ["technology"]

    # Search Hunter.io for companies in target industries
    # In production, this would use more sophisticated discovery
    # For MVP, we search a curated set of domains per industry
    INDUSTRY_DOMAINS = {
        "fintech": ["stripe.com", "plaid.com", "brex.com"],
        "saas": ["notion.so", "linear.app", "vercel.com"],
        "cloud": ["datadog.com", "cloudflare.com"],
        "developer tools": ["vercel.com", "linear.app"],
        "technology": ["stripe.com", "vercel.com", "notion.so", "datadog.com", "linear.app"],
    }

    for industry in industries:
        domains = INDUSTRY_DOMAINS.get(industry.lower(), INDUSTRY_DOMAINS["technology"])
        domains_to_search.update(domains)

    companies = []
    for domain in domains_to_search:
        # Check if already exists for this candidate
        existing = await db.execute(
            select(Company).where(
                Company.candidate_id == candidate_id, Company.domain == domain
            )
        )
        if existing.scalar_one_or_none():
            continue

        try:
            data = await hunter.domain_search(domain)
            company = await _create_company_from_hunter(db, candidate_id, domain, data, dna)
            companies.append(company)
        except Exception as e:
            logger.error("company_discovery_failed", domain=domain, error=str(e))

    await db.commit()

    # Sort by fit score
    companies.sort(key=lambda c: c.fit_score or 0, reverse=True)
    logger.info("companies_discovered", candidate_id=str(candidate_id), count=len(companies))
    return companies


async def add_company_manual(
    db: AsyncSession, candidate_id: uuid.UUID, domain: str
) -> Company:
    """Manually add a company by domain."""
    # Check if already exists
    existing = await db.execute(
        select(Company).where(
            Company.candidate_id == candidate_id, Company.domain == domain
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Company {domain} already exists")

    dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
    dna = dna_result.scalar_one_or_none()

    hunter = get_hunter()
    data = await hunter.domain_search(domain)
    company = await _create_company_from_hunter(db, candidate_id, domain, data, dna)
    company.status = "approved"  # Manual adds are auto-approved

    # Also create contacts from Hunter data
    await _create_contacts_from_hunter(db, candidate_id, company.id, data)

    await db.commit()
    await db.refresh(company)
    logger.info("company_added_manually", domain=domain, candidate_id=str(candidate_id))
    return company


async def approve_company(db: AsyncSession, company_id: uuid.UUID) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise ValueError("Company not found")

    company.status = "approved"
    await db.commit()
    await db.refresh(company)
    logger.info("company_approved", company_id=str(company_id))
    return company


async def reject_company(
    db: AsyncSession, company_id: uuid.UUID, reason: str
) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise ValueError("Company not found")

    company.status = "rejected"
    # Store reason in hunter_data for learning
    company.hunter_data = {**(company.hunter_data or {}), "rejection_reason": reason}
    await db.commit()
    await db.refresh(company)
    logger.info("company_rejected", company_id=str(company_id), reason=reason)
    return company


async def research_company(db: AsyncSession, company_id: uuid.UUID) -> CompanyDossier:
    """Generate full research dossier for a company."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise ValueError("Company not found")

    company.research_status = "in_progress"
    await db.commit()

    try:
        # Get candidate DNA for personalized dossier
        dna_result = await db.execute(
            select(CandidateDNA).where(CandidateDNA.candidate_id == company.candidate_id)
        )
        dna = dna_result.scalar_one_or_none()
        candidate_summary = dna.experience_summary if dna else "No candidate DNA available"

        # Enrich company data via Hunter
        hunter = get_hunter()
        hunter_data = await hunter.domain_search(company.domain)

        # Generate dossier via GPT-4o
        client = get_openai()
        prompt_filled = DOSSIER_PROMPT.format(
            company_name=company.name,
            domain=company.domain,
            industry=company.industry or "Unknown",
            size=company.size_range or "Unknown",
            location=company.location_hq or "Unknown",
            description=company.description or "No description available",
            tech_stack=", ".join(company.tech_stack or []),
            candidate_summary=candidate_summary,
        )

        dossier_data = await client.parse_structured(
            prompt_filled, json.dumps(hunter_data), DOSSIER_SCHEMA
        )

        # Create or update dossier
        existing = await db.execute(
            select(CompanyDossier).where(CompanyDossier.company_id == company_id)
        )
        dossier = existing.scalar_one_or_none()
        if not dossier:
            dossier = CompanyDossier(id=uuid.uuid4(), company_id=company_id)
            db.add(dossier)

        dossier.culture_summary = dossier_data.get("culture_summary")
        dossier.culture_score = dossier_data.get("culture_score")
        dossier.red_flags = dossier_data.get("red_flags")
        dossier.interview_format = dossier_data.get("interview_format")
        dossier.interview_questions = dossier_data.get("interview_questions")
        dossier.compensation_data = dossier_data.get("compensation_data")
        dossier.key_people = dossier_data.get("key_people")
        dossier.why_hire_me = dossier_data.get("why_hire_me")
        dossier.recent_news = dossier_data.get("recent_news")

        # Create contacts from Hunter data
        await _create_contacts_from_hunter(db, company.candidate_id, company_id, hunter_data)

        # Embed company for vector search
        embed_text_content = f"{company.name} {company.description or ''} {company.industry or ''}"
        company.embedding = await embed_text(embed_text_content)
        company.research_status = "completed"
        company.last_enriched = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(dossier)
        logger.info("company_research_completed", company_id=str(company_id))
        return dossier

    except Exception as e:
        company.research_status = "failed"
        await db.commit()
        logger.error("company_research_failed", company_id=str(company_id), error=str(e))
        raise


async def _create_company_from_hunter(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    domain: str,
    hunter_data: dict,
    dna: CandidateDNA | None,
) -> Company:
    """Create a Company record from Hunter.io data."""
    description = hunter_data.get("description", "")
    company_text = f"{hunter_data.get('organization', domain)} {description}"

    # Compute fit score if DNA exists
    fit_score = None
    embedding = None
    if dna and dna.embedding is not None:
        embedding = await embed_text(company_text)
        fit_score = cosine_similarity([float(x) for x in dna.embedding], embedding)

    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=hunter_data.get("organization", domain),
        domain=domain,
        industry=hunter_data.get("industry"),
        size_range=hunter_data.get("size"),
        location_hq=hunter_data.get("location"),
        description=description,
        tech_stack=hunter_data.get("technologies"),
        hunter_data=hunter_data,
        fit_score=fit_score,
        embedding=embedding,
        status="suggested",
        research_status="pending",
    )
    db.add(company)
    return company


async def _create_contacts_from_hunter(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
    hunter_data: dict,
) -> list[Contact]:
    """Create Contact records from Hunter.io emails data."""
    contacts = []
    for email_data in hunter_data.get("emails", []):
        # Check if contact already exists
        existing = await db.execute(
            select(Contact).where(
                Contact.company_id == company_id,
                Contact.email == email_data.get("value"),
            )
        )
        if existing.scalar_one_or_none():
            continue

        position = (email_data.get("position") or "").lower()
        role_type = "recruiter"
        is_decision_maker = False
        priority = 0

        if any(t in position for t in ["vp", "director", "head", "cto", "ceo"]):
            role_type = "hiring_manager"
            is_decision_maker = True
            priority = 3
        elif any(t in position for t in ["manager", "lead"]):
            role_type = "team_lead"
            priority = 2
        elif "recruit" in position:
            role_type = "recruiter"
            priority = 1

        contact = Contact(
            id=uuid.uuid4(),
            company_id=company_id,
            candidate_id=candidate_id,
            full_name=f"{email_data.get('first_name', '')} {email_data.get('last_name', '')}".strip(),
            email=email_data.get("value"),
            email_confidence=email_data.get("confidence"),
            title=email_data.get("position"),
            role_type=role_type,
            is_decision_maker=is_decision_maker,
            outreach_priority=priority,
            hunter_data=email_data,
        )
        db.add(contact)
        contacts.append(contact)

    return contacts
