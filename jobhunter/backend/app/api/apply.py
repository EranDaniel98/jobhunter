import json
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.rate_limit import limiter
from app.models.candidate import Candidate
from app.models.job_posting import JobPosting
from app.schemas.apply import (
    ApplyAnalysisResponse,
    JobPostingCreateRequest,
    JobPostingListResponse,
    JobPostingResponse,
    ResumeTipItem,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/apply", tags=["apply"])


async def _run_apply_pipeline(candidate_id: str, job_posting_id: str):
    """Background task to run the apply pipeline and cache results in Redis."""
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
        result = await graph.ainvoke(state, config={"configurable": {"thread_id": thread_id}})

        # Cache analysis results in Redis for retrieval (7 days TTL)
        from app.infrastructure.redis_client import get_redis
        redis = get_redis()
        analysis = {
            "job_posting_id": job_posting_id,
            "readiness_score": result.get("readiness_score", 0),
            "resume_tips": result.get("resume_tips", []),
            "cover_letter": result.get("cover_letter", ""),
            "ats_keywords": result.get("ats_keywords", []),
            "missing_skills": result.get("missing_skills", []),
            "matching_skills": result.get("matching_skills", []),
            "status": result.get("status", "completed"),
        }
        await redis.set(f"apply:analysis:{job_posting_id}", json.dumps(analysis), ex=86400 * 7)
    except Exception as e:
        logger.error("apply_pipeline_bg_failed", error=str(e))


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
        status="pending",
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
    posting_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Get the analysis results for a job posting."""
    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == uuid.UUID(posting_id),
            JobPosting.candidate_id == candidate.id,
        )
    )
    posting = result.scalar_one_or_none()
    if not posting:
        raise HTTPException(status_code=404, detail="Job posting not found")

    if posting.status == "pending":
        raise HTTPException(status_code=202, detail="Analysis still in progress")

    # Retrieve from Redis
    from app.infrastructure.redis_client import get_redis
    redis = get_redis()
    cached = await redis.get(f"apply:analysis:{posting_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Analysis not found — may have expired")

    analysis = json.loads(cached)
    return ApplyAnalysisResponse(
        id=posting_id,
        job_posting_id=posting_id,
        readiness_score=analysis.get("readiness_score", 0),
        resume_tips=[ResumeTipItem(**t) for t in analysis.get("resume_tips", [])],
        cover_letter=analysis.get("cover_letter", ""),
        ats_keywords=analysis.get("ats_keywords", []),
        missing_skills=analysis.get("missing_skills", []),
        matching_skills=analysis.get("matching_skills", []),
        status=analysis.get("status", "completed"),
    )
