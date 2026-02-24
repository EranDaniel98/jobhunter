import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, status
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
- recent_news: array of {{title, date}} for notable events
- resume_bullets: array of 3-5 specific bullet points the candidate should add or emphasize on their resume to be a stronger match for THIS company. Reference specific skills, technologies, or experiences that align with the company's needs. Each bullet should be actionable (e.g. "Highlight your experience with distributed systems — their tech stack relies heavily on microservices")."""

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
        "resume_bullets": {
            "type": "array",
            "items": {"type": "string"},
        },
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
    "required": ["culture_summary", "culture_score", "red_flags", "interview_format", "interview_questions", "compensation_data", "key_people", "why_hire_me", "resume_bullets", "recent_news"],
    "additionalProperties": False,
}


DISCOVERY_PROMPT = """You are a company discovery assistant for job seekers. Based on the candidate's profile, suggest 5-8 real companies they should target.

CANDIDATE PROFILE:
{candidate_summary}

TARGET INDUSTRIES: {industries}
TARGET ROLES: {roles}

{location_constraint}

EXISTING COMPANIES (do NOT suggest these again): {existing_domains}

{filter_instructions}

INSTRUCTIONS:
- Suggest REAL companies with valid domain names
- Focus on companies that match the candidate's skills and experience
- Prefer companies that are actively hiring or growing
- Include a mix of well-known and emerging companies
- Each suggestion must have a real, working company website domain
- For each company include its primary industry, approximate employee size range (e.g. "51-200", "201-500"), and known tech stack
- Strictly follow the LOCATION REQUIREMENT above"""

DISCOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "name": {"type": "string"},
                    "reason": {"type": "string"},
                    "industry": {"type": "string"},
                    "size": {"type": "string"},
                    "tech_stack": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["domain", "name", "reason", "industry", "size", "tech_stack"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["companies"],
    "additionalProperties": False,
}


async def discover_companies(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    industries: list[str] | None = None,
    locations: list[str] | None = None,
    company_size: str | None = None,
    keywords: str | None = None,
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

    if not dna:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload and process a resume before discovering companies",
        )

    hunter = get_hunter()

    # Gather existing company domains to exclude
    existing_result = await db.execute(
        select(Company.domain).where(Company.candidate_id == candidate_id)
    )
    existing_domains = [row[0] for row in existing_result.all()]

    # Use filter overrides or fall back to candidate profile
    target_industries = industries or candidate.target_industries or ["technology"]
    target_roles = candidate.target_roles or ["software engineer"]
    target_locations = locations or candidate.target_locations or []

    # Separate "Remote" from physical locations
    physical_locations = [loc for loc in target_locations if loc.lower() != "remote"]
    includes_remote = any(loc.lower() == "remote" for loc in target_locations)

    # Build location constraint
    if physical_locations and includes_remote:
        location_constraint = (
            f"LOCATION REQUIREMENT (STRICT): Every company you suggest MUST either "
            f"have a physical office in one of these locations: {', '.join(physical_locations)}, "
            f"OR be a well-known remote-friendly company. Do NOT suggest companies that only "
            f"have offices in other locations."
        )
    elif physical_locations:
        location_constraint = (
            f"LOCATION REQUIREMENT (STRICT): Every company you suggest MUST have a physical "
            f"office or headquarters in one of these locations: {', '.join(physical_locations)}. "
            f"Do NOT suggest companies that only have offices elsewhere."
        )
    elif includes_remote:
        location_constraint = (
            "LOCATION REQUIREMENT: Prefer remote-friendly companies or companies known for "
            "supporting remote work. Location is flexible."
        )
    else:
        location_constraint = "LOCATION: No location preference specified."

    # Build filter instructions for additional filters
    filter_parts = []
    if company_size:
        filter_parts.append(f"COMPANY SIZE PREFERENCE: {company_size}")
    if keywords:
        filter_parts.append(f"ADDITIONAL PREFERENCES: {keywords}")
    filter_instructions = "\n".join(filter_parts)

    client = get_openai()
    prompt = DISCOVERY_PROMPT.format(
        candidate_summary=dna.experience_summary if dna else "No detailed profile available",
        industries=", ".join(target_industries),
        roles=", ".join(target_roles),
        location_constraint=location_constraint,
        existing_domains=", ".join(existing_domains) if existing_domains else "None",
        filter_instructions=filter_instructions,
    )

    suggestions = await client.parse_structured(prompt, "", DISCOVERY_SCHEMA)

    companies = []
    seen_domains = set(existing_domains)
    for suggestion in suggestions.get("companies", []):
        domain = suggestion["domain"].strip().lower()

        # Skip if already exists or already processed in this batch
        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        try:
            data = await hunter.domain_search(domain)
            company = await _create_company_from_hunter(db, candidate_id, domain, data, dna)
            # Backfill empty fields from OpenAI suggestion
            if not company.industry and suggestion.get("industry"):
                company.industry = suggestion["industry"]
            if not company.size_range and suggestion.get("size"):
                company.size_range = suggestion["size"]
            if not company.tech_stack and suggestion.get("tech_stack"):
                company.tech_stack = suggestion["tech_stack"]
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
        dossier.resume_bullets = dossier_data.get("resume_bullets")
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
    description = hunter_data.get("description") or ""
    org_name = hunter_data.get("organization") or domain
    company_text = f"{org_name} {description}"

    # Compute fit score if DNA exists
    fit_score = None
    embedding = None
    if dna and dna.embedding is not None:
        embedding = await embed_text(company_text)
        fit_score = cosine_similarity([float(x) for x in dna.embedding], embedding)

    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=org_name,
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
