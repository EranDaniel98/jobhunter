import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.rate_limit import limiter
from app.models.candidate import Candidate
from app.models.company import Company, CompanyDossier
from app.models.contact import Contact
from app.schemas.company import (
    CompanyAddRequest,
    CompanyDiscoverRequest,
    CompanyDossierResponse,
    CompanyListResponse,
    CompanyRejectRequest,
    CompanyResponse,
)
from app.schemas.contact import ContactResponse
from app.services import company_service
from app.services.quota_service import check_and_increment

router = APIRouter(prefix="/companies", tags=["companies"])
logger = structlog.get_logger()


def _company_to_response(c: Company) -> CompanyResponse:
    return CompanyResponse(
        id=str(c.id),
        name=c.name,
        domain=c.domain,
        industry=c.industry,
        size_range=c.size_range,
        location_hq=c.location_hq,
        description=c.description,
        tech_stack=c.tech_stack,
        funding_stage=c.funding_stage,
        fit_score=c.fit_score,
        status=c.status,
        research_status=c.research_status,
    )


@router.post("/discover", response_model=CompanyListResponse)
@limiter.limit("3/hour")
async def discover_companies(
    request: Request,
    data: CompanyDiscoverRequest | None = None,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    await check_and_increment(str(candidate.id), "discovery", candidate.plan_tier)
    companies = await company_service.discover_companies(
        db,
        candidate.id,
        industries=data.industries if data else None,
        locations=data.locations if data else None,
        company_size=data.company_size if data else None,
        keywords=data.keywords if data else None,
    )
    return CompanyListResponse(
        companies=[_company_to_response(c) for c in companies],
        total=len(companies),
    )


@router.post("/add", response_model=CompanyResponse, status_code=201)
async def add_company(
    data: CompanyAddRequest,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    await check_and_increment(str(candidate.id), "hunter", candidate.plan_tier)
    try:
        company = await company_service.add_company_manual(db, candidate.id, data.domain)

        # Research in background
        background_tasks.add_task(_research_background, company.id)
        return _company_to_response(company)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    status: str | None = None,
    skip: int = 0,
    limit: int = Query(default=50, le=100),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    query = select(Company).where(Company.candidate_id == candidate.id)
    if status:
        query = query.where(Company.status == status)
    query = query.order_by(Company.fit_score.desc().nulls_last()).offset(skip).limit(limit)

    result = await db.execute(query)
    companies = result.scalars().all()
    return CompanyListResponse(
        companies=[_company_to_response(c) for c in companies],
        total=len(companies),
    )


@router.get("/suggested", response_model=CompanyListResponse)
async def get_suggested(
    skip: int = 0,
    limit: int = Query(default=50, le=100),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Company)
        .where(Company.candidate_id == candidate.id, Company.status == "suggested")
        .order_by(Company.fit_score.desc().nulls_last())
        .offset(skip).limit(limit)
    )
    companies = result.scalars().all()
    return CompanyListResponse(
        companies=[_company_to_response(c) for c in companies],
        total=len(companies),
    )


@router.post("/{company_id}/approve", response_model=CompanyResponse)
async def approve_company(
    company_id: str,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_candidate_company(db, company_id, candidate.id)
    company = await company_service.approve_company(db, company.id)

    # Research in background
    background_tasks.add_task(_research_background, company.id)
    # Auto-trigger interview prep for key types
    background_tasks.add_task(
        _auto_interview_prep, str(company.candidate_id), str(company.id)
    )
    return _company_to_response(company)


@router.post("/{company_id}/reject", response_model=CompanyResponse)
async def reject_company(
    company_id: str,
    data: CompanyRejectRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_candidate_company(db, company_id, candidate.id)
    company = await company_service.reject_company(db, company.id, data.reason)
    return _company_to_response(company)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_candidate_company(db, company_id, candidate.id)
    return _company_to_response(company)


@router.get("/{company_id}/dossier", response_model=CompanyDossierResponse)
async def get_dossier(
    company_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_candidate_company(db, company_id, candidate.id)
    result = await db.execute(
        select(CompanyDossier).where(CompanyDossier.company_id == company.id)
    )
    dossier = result.scalar_one_or_none()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not yet generated. Approve the company first.")

    return CompanyDossierResponse(
        id=str(dossier.id),
        culture_summary=dossier.culture_summary,
        culture_score=dossier.culture_score,
        red_flags=dossier.red_flags,
        interview_format=dossier.interview_format,
        interview_questions=dossier.interview_questions,
        compensation_data=dossier.compensation_data,
        key_people=dossier.key_people,
        why_hire_me=dossier.why_hire_me,
        recent_news=dossier.recent_news,
    )


@router.get("/{company_id}/contacts", response_model=list[ContactResponse])
async def get_contacts(
    company_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_candidate_company(db, company_id, candidate.id)
    result = await db.execute(
        select(Contact)
        .where(Contact.company_id == company.id)
        .order_by(Contact.outreach_priority.desc())
    )
    contacts = result.scalars().all()
    return [
        ContactResponse(
            id=str(c.id),
            company_id=str(c.company_id),
            full_name=c.full_name,
            email=c.email,
            email_verified=c.email_verified,
            email_confidence=c.email_confidence,
            title=c.title,
            role_type=c.role_type,
            is_decision_maker=c.is_decision_maker,
            outreach_priority=c.outreach_priority,
        )
        for c in contacts
    ]


async def _get_candidate_company(
    db: AsyncSession, company_id: str, candidate_id
) -> Company:
    import uuid as _uuid
    result = await db.execute(
        select(Company).where(
            Company.id == _uuid.UUID(company_id),
            Company.candidate_id == candidate_id,
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


async def _auto_interview_prep(candidate_id: str, company_id: str):
    """Auto-generate interview prep (company_qa, behavioral, technical) on company approval."""
    import uuid as _uuid
    from app.graphs.interview_prep import get_interview_prep_pipeline

    for prep_type in ("company_qa", "behavioral", "technical"):
        try:
            thread_id = f"interview-auto-{_uuid.uuid4()}"
            graph = get_interview_prep_pipeline()
            await graph.ainvoke(
                {
                    "candidate_id": candidate_id,
                    "company_id": company_id,
                    "prep_type": prep_type,
                    "session_id": None,
                    "context": None,
                    "content": None,
                    "status": "pending",
                    "error": None,
                },
                config={"configurable": {"thread_id": thread_id}},
            )
        except Exception as e:
            logger.warning("auto_interview_prep_failed", prep_type=prep_type, error=str(e))


async def _research_background(company_id):
    from app.infrastructure.database import async_session_factory

    # Phase 1: Check quotas before running the graph
    async with async_session_factory() as db:
        try:
            result = await db.execute(select(Company).where(Company.id == company_id))
            company = result.scalar_one_or_none()
            if not company:
                logger.error("background_research_company_not_found", company_id=str(company_id))
                return

            candidate_id = str(company.candidate_id)
            from app.models.candidate import Candidate as _Candidate
            cand_result = await db.execute(
                select(_Candidate).where(_Candidate.id == company.candidate_id)
            )
            cand = cand_result.scalar_one_or_none()
            tier = cand.plan_tier if cand else "free"

            await check_and_increment(candidate_id, "research", tier)
            await check_and_increment(candidate_id, "openai", tier)
        except Exception as e:
            logger.error("background_research_quota_failed", error=str(e), company_id=str(company_id))
            try:
                result = await db.execute(select(Company).where(Company.id == company_id))
                c = result.scalar_one_or_none()
                if c:
                    c.research_status = "failed"
                    await db.commit()
            except Exception:
                pass
            return

    # Phase 2: Run the LangGraph company research pipeline
    try:
        from app.graphs.company_research import (
            CompanyResearchState,
            get_company_research_pipeline,
        )

        pipeline = get_company_research_pipeline()
        initial_state: CompanyResearchState = {
            "company_id": str(company_id),
            "candidate_id": candidate_id,
            "plan_tier": tier,
            "hunter_data": None,
            "web_context": None,
            "dossier_data": None,
            "contacts_created": 0,
            "embedding_set": False,
            "status": "pending",
            "error": None,
        }

        await pipeline.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": f"company-research-{company_id}"}},
        )
    except Exception as e:
        logger.error("background_research_graph_failed", error=str(e), company_id=str(company_id))
        async with async_session_factory() as db:
            try:
                result = await db.execute(select(Company).where(Company.id == company_id))
                company = result.scalar_one_or_none()
                if company and company.research_status != "failed":
                    company.research_status = "failed"
                    await db.commit()
            except Exception:
                pass
