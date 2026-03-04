import json
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.rate_limit import limiter
from app.models.candidate import Candidate
from app.models.enums import JobPostingStatus
from app.models.job_posting import JobPosting
from app.schemas.apply import (
    ApplyAnalysisResponse,
    JobPostingCreateRequest,
    JobPostingListResponse,
    JobPostingResponse,
    ResumeTipItem,
    ScrapeUrlRequest,
    ScrapeUrlResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/apply", tags=["apply"])

EXTRACT_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "company_name": {"type": "string"},
    },
    "required": ["title", "company_name"],
    "additionalProperties": False,
}


@router.post("/scrape-url", response_model=ScrapeUrlResponse)
@limiter.limit("20/day")
async def scrape_url(
    request: Request,
    req: ScrapeUrlRequest,
    candidate: Candidate = Depends(get_current_candidate),
):
    """Scrape a job posting URL and return the extracted text."""
    from app.infrastructure.url_scraper import scrape_job_url

    try:
        raw_text = await scrape_job_url(req.url)
    except Exception as e:
        logger.warning("scrape_url_failed", url=req.url, error=str(e))
        raise HTTPException(
            status_code=422,
            detail="Could not fetch job posting from URL. Please paste the description manually.",
        )

    # Try to extract title and company name via LLM (best-effort)
    title = None
    company_name = None
    try:
        from app.dependencies import get_openai

        client = get_openai()
        snippet = raw_text[:2000]
        meta = await client.parse_structured(
            "Extract the job title and company name from this job posting snippet.",
            snippet,
            EXTRACT_METADATA_SCHEMA,
        )
        title = meta.get("title") or None
        company_name = meta.get("company_name") or None
    except Exception:
        pass  # Metadata extraction is best-effort

    return ScrapeUrlResponse(raw_text=raw_text, title=title, company_name=company_name)


async def _run_apply_pipeline(candidate_id: str, job_posting_id: str):
    """Background task to run the apply pipeline (Redis caching happens inside the pipeline)."""
    from app.graphs.apply_pipeline import get_apply_pipeline

    thread_id = f"apply-{uuid.uuid4()}"
    state = {
        "candidate_id": candidate_id,
        "job_posting_id": job_posting_id,
        "parsed_requirements": None,
        "candidate_skills": None,
        "matching_skills": None,
        "missing_skills": None,
        "resume_tips": None,
        "readiness_score": None,
        "cover_letter": None,
        "ats_keywords": None,
        "context": None,
        "status": "pending",
        "error": None,
    }

    try:
        graph = get_apply_pipeline()
        await graph.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
    except Exception as e:
        logger.error("apply_pipeline_bg_failed", error=str(e))
        try:
            from app.infrastructure.database import async_session_factory
            async with async_session_factory() as err_db:
                result = await err_db.execute(
                    select(JobPosting).where(JobPosting.id == uuid.UUID(job_posting_id))
                )
                posting = result.scalar_one_or_none()
                if posting:
                    posting.status = JobPostingStatus.FAILED
                    await err_db.commit()
        except Exception:
            pass


@router.post("/analyze", response_model=JobPostingResponse)
@limiter.limit("20/day")
async def analyze_job_posting(
    request: Request,
    req: JobPostingCreateRequest,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Submit a job posting for analysis."""
    company_id = uuid.UUID(req.company_id) if req.company_id else None

    posting = JobPosting(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        company_id=company_id,
        title=req.title,
        company_name=req.company_name,
        url=req.url,
        raw_text=req.raw_text,
        status=JobPostingStatus.PENDING,
    )
    db.add(posting)
    await db.commit()

    background_tasks.add_task(_run_apply_pipeline, str(candidate.id), str(posting.id))

    return JobPostingResponse.model_validate(posting)


@router.get("/postings", response_model=JobPostingListResponse)
async def list_postings(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List job postings for the authenticated candidate."""
    result = await db.execute(
        select(JobPosting)
        .where(JobPosting.candidate_id == candidate.id)
        .order_by(JobPosting.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    postings = result.scalars().all()

    count_result = await db.execute(
        select(func.count(JobPosting.id)).where(JobPosting.candidate_id == candidate.id)
    )
    total = count_result.scalar() or 0

    return JobPostingListResponse(
        postings=[JobPostingResponse.model_validate(p) for p in postings],
        total=total,
    )


@router.get("/postings/{posting_id}/analysis", response_model=ApplyAnalysisResponse)
async def get_analysis(
    posting_id: uuid.UUID,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Get the analysis results for a job posting."""
    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == posting_id,
            JobPosting.candidate_id == candidate.id,
        )
    )
    posting = result.scalar_one_or_none()
    if not posting:
        raise HTTPException(status_code=404, detail="Job posting not found")

    if posting.status == JobPostingStatus.PENDING:
        return JSONResponse(
            status_code=202,
            content={"status": "pending", "detail": "Analysis still in progress"},
        )

    # Retrieve from Redis
    from app.infrastructure.redis_client import get_redis
    redis = get_redis()
    cached = await redis.get(f"apply:analysis:{posting_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Analysis not found — may have expired")

    analysis = json.loads(cached)
    return ApplyAnalysisResponse(
        id=str(posting_id),
        job_posting_id=str(posting_id),
        readiness_score=analysis.get("readiness_score", 0),
        resume_tips=[ResumeTipItem(**t) for t in analysis.get("resume_tips", [])],
        cover_letter=analysis.get("cover_letter", ""),
        ats_keywords=analysis.get("ats_keywords", []),
        missing_skills=analysis.get("missing_skills", []),
        matching_skills=analysis.get("matching_skills", []),
        status=analysis.get("status", "completed"),
    )
