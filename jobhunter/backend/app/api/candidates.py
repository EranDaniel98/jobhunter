import uuid as _uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate, CandidateDNA, Resume, Skill
from app.models.enums import ParseStatus
from app.rate_limit import limiter
from app.schemas.candidate import CandidateDNAResponse, ResumeListItem, ResumeUploadResponse, SkillResponse
from app.services import resume_service
from app.services.quota_service import get_usage

router = APIRouter(prefix="/candidates", tags=["candidates"])
logger = structlog.get_logger()


@router.post("/resume", response_model=ResumeUploadResponse, status_code=201)
@limiter.limit("5/hour")
async def upload_resume(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    # Validate MIME type
    allowed_mimes = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if file.content_type not in allowed_mimes.values():
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF and DOCX files are supported")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Validate magic bytes
    if ext == "pdf" and not contents[:4] == b"%PDF":
        raise HTTPException(status_code=400, detail="File content does not match PDF format")
    if ext == "docx" and not contents[:2] == b"PK":
        raise HTTPException(status_code=400, detail="File content does not match DOCX format")

    resume = await resume_service.upload_resume(db, candidate.id, contents, file.filename)

    # Parse and generate DNA in background
    background_tasks.add_task(_run_async_background, resume.id, candidate.id)

    return ResumeUploadResponse(
        id=str(resume.id),
        file_path=resume.file_path,
        is_primary=resume.is_primary,
        parsed_data=resume.parsed_data,
    )


async def _run_async_background(resume_id, candidate_id):
    """Run the LangGraph resume processing pipeline."""
    from app.config import settings
    from app.graphs.resume_pipeline import get_resume_pipeline
    from app.loadtest_guard import AIBudgetExceeded, enforce_ai_budget

    # Load-test safety: hard cap on expensive AI pipeline runs. No-op in production.
    if settings.LOADTEST_MODE:
        from app.infrastructure.redis_client import get_redis

        try:
            await enforce_ai_budget(get_redis(), settings.LOADTEST_AI_BUDGET)
        except AIBudgetExceeded as e:
            logger.warning("loadtest.ai_budget_exceeded", error=str(e), resume_id=str(resume_id))
            # Mark the resume as failed with a distinct error_message so the k6
            # polling scenario still sees a terminal state. We reuse
            # ParseStatus.FAILED rather than adding a new 'skipped' enum value to
            # avoid an Alembic migration just for load-testing.
            from app.infrastructure.database import async_session_factory

            async with async_session_factory() as db:
                try:
                    r = await db.execute(select(Resume).where(Resume.id == resume_id))
                    resume = r.scalar_one_or_none()
                    if resume:
                        resume.parse_status = ParseStatus.FAILED
                        resume.parsed_data = {"_error": "loadtest_budget_exceeded"}
                        await db.commit()
                except Exception as inner:
                    logger.error(
                        "loadtest.skipped_status_update_failed",
                        resume_id=str(resume_id),
                        error=str(inner),
                    )
            return

    graph = get_resume_pipeline()
    config = {"configurable": {"thread_id": f"resume:{resume_id}"}}

    try:
        result = await graph.ainvoke(
            {
                "resume_id": str(resume_id),
                "candidate_id": str(candidate_id),
                "parsed_data": None,
                "raw_text": None,
                "skills_data": None,
                "dna_data": None,
                "embedding": None,
                "skills_vector": None,
                "fit_scores_updated": 0,
                "status": "pending",
                "error": None,
            },
            config,
        )
        if result.get("status") == "failed":
            logger.error("resume_pipeline_failed", resume_id=str(resume_id), error=result.get("error"))
        else:
            logger.info("resume_pipeline_completed", resume_id=str(resume_id))
    except Exception as e:
        logger.error("resume_pipeline_exception", resume_id=str(resume_id), error=str(e))
        # Fallback: mark resume as failed
        from app.infrastructure.database import async_session_factory

        async with async_session_factory() as db:
            try:
                result = await db.execute(select(Resume).where(Resume.id == resume_id))
                resume = result.scalar_one_or_none()
                if resume:
                    resume.parse_status = "failed"
                    await db.commit()
            except Exception as e:
                logger.error("resume_pipeline_status_update_failed", resume_id=str(resume_id), error=str(e))


@router.get("/me/usage")
async def get_my_usage(
    candidate: Candidate = Depends(get_current_candidate),
):
    return await get_usage(str(candidate.id), candidate.plan_tier, is_admin=candidate.is_admin)


@router.get("/me/dna", response_model=CandidateDNAResponse)
async def get_dna(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate.id))
    dna = result.scalar_one_or_none()
    if not dna:
        raise HTTPException(status_code=404, detail="DNA not generated yet. Upload a resume first.")

    skills_result = await db.execute(select(Skill).where(Skill.candidate_id == candidate.id))
    skills = skills_result.scalars().all()

    return CandidateDNAResponse(
        id=str(dna.id),
        experience_summary=dna.experience_summary,
        strengths=dna.strengths,
        gaps=dna.gaps,
        career_stage=dna.career_stage,
        transferable_skills=dna.transferable_skills,
        skills=[
            SkillResponse(
                id=str(s.id),
                name=s.name,
                category=s.category,
                proficiency=s.proficiency,
                years_experience=s.years_experience,
                evidence=s.evidence,
            )
            for s in skills
        ],
    )


@router.get("/me/skills", response_model=list[SkillResponse])
async def get_skills(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Skill).where(Skill.candidate_id == candidate.id))
    skills = result.scalars().all()
    return [
        SkillResponse(
            id=str(s.id),
            name=s.name,
            category=s.category,
            proficiency=s.proficiency,
            years_experience=s.years_experience,
            evidence=s.evidence,
        )
        for s in skills
    ]


@router.get("/me/resumes", response_model=list[ResumeListItem])
async def list_resumes(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.candidate_id == candidate.id).order_by(Resume.created_at.desc())
    )
    resumes = result.scalars().all()
    return [
        ResumeListItem(
            id=str(r.id),
            file_path=r.file_path,
            is_primary=r.is_primary,
            parse_status=r.parse_status,
            parse_error=(
                r.parsed_data.get("_error")
                if candidate.is_admin and r.parsed_data and "_error" in r.parsed_data
                else None
            ),
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in resumes
    ]


@router.delete("/me/resumes/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(
            Resume.id == _uuid.UUID(resume_id),
            Resume.candidate_id == candidate.id,
        )
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.is_primary:
        raise HTTPException(status_code=400, detail="Cannot delete the primary resume")
    await db.delete(resume)
    await db.commit()
    logger.info("resume_deleted", resume_id=resume_id)
