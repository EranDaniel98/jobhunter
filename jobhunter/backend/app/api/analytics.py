import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.models.insight import AnalyticsInsight
from app.rate_limit import limiter
from app.schemas.analytics import (
    AnalyticsDashboardResponse,
    AnalyticsInsightListResponse,
    AnalyticsInsightResponse,
    FunnelResponse,
    OutreachStatsResponse,
    PipelineStatsResponse,
)
from app.services import analytics_service

logger = structlog.get_logger()

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/funnel", response_model=FunnelResponse)
async def get_funnel(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    data = await analytics_service.get_funnel(db, candidate.id)
    return FunnelResponse(**data)


@router.get("/outreach", response_model=OutreachStatsResponse)
async def get_outreach_stats(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    data = await analytics_service.get_outreach_stats(db, candidate.id)
    return OutreachStatsResponse(**data)


@router.get("/pipeline", response_model=PipelineStatsResponse)
async def get_pipeline_stats(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    data = await analytics_service.get_pipeline_stats(db, candidate.id)
    return PipelineStatsResponse(**data)


@router.get("/insights", response_model=AnalyticsInsightListResponse)
async def list_insights(
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """List AI-generated analytics insights."""
    query = (
        select(AnalyticsInsight)
        .where(AnalyticsInsight.candidate_id == candidate.id)
        .order_by(AnalyticsInsight.created_at.desc())
    )
    if unread_only:
        query = query.where(AnalyticsInsight.is_read == False)

    result = await db.execute(query.offset(skip).limit(limit))
    insights = result.scalars().all()

    count_query = select(func.count(AnalyticsInsight.id)).where(
        AnalyticsInsight.candidate_id == candidate.id
    )
    if unread_only:
        count_query = count_query.where(AnalyticsInsight.is_read == False)
    total = (await db.execute(count_query)).scalar() or 0

    return AnalyticsInsightListResponse(
        insights=[AnalyticsInsightResponse.model_validate(i) for i in insights],
        total=total,
    )


@router.post("/insights/refresh")
@limiter.limit("5/day")
async def refresh_insights(
    request: Request,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
):
    """Trigger analytics pipeline to generate fresh insights."""
    import uuid as _uuid

    async def _run_analytics(candidate_id: str):
        from app.graphs.analytics_pipeline import get_analytics_pipeline
        thread_id = f"analytics-{_uuid.uuid4()}"
        state = {
            "candidate_id": candidate_id,
            "include_email": False,
            "raw_data": None,
            "insights": None,
            "insights_saved": 0,
            "status": "pending",
            "error": None,
        }
        try:
            graph = get_analytics_pipeline()
            await graph.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
        except Exception as e:
            logger.error("analytics_refresh_failed", error=str(e))

    background_tasks.add_task(_run_analytics, str(candidate.id))
    return {"status": "refreshing"}


@router.patch("/insights/{insight_id}/read")
async def mark_insight_read(
    insight_id: uuid.UUID,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Mark an insight as read."""
    result = await db.execute(
        select(AnalyticsInsight).where(
            AnalyticsInsight.id == insight_id,
            AnalyticsInsight.candidate_id == candidate.id,
        )
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    insight.is_read = True
    await db.commit()
    return {"status": "ok"}


@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
async def get_dashboard(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Combined dashboard endpoint returning funnel + outreach + pipeline + latest insights."""
    funnel = await analytics_service.get_funnel(db, candidate.id)
    outreach = await analytics_service.get_outreach_stats(db, candidate.id)
    pipeline = await analytics_service.get_pipeline_stats(db, candidate.id)

    result = await db.execute(
        select(AnalyticsInsight)
        .where(AnalyticsInsight.candidate_id == candidate.id)
        .order_by(AnalyticsInsight.created_at.desc())
        .limit(10)
    )
    insights = result.scalars().all()

    return AnalyticsDashboardResponse(
        funnel=FunnelResponse(**funnel),
        outreach=OutreachStatsResponse(**outreach),
        pipeline=PipelineStatsResponse(**pipeline),
        insights=[AnalyticsInsightResponse.model_validate(i) for i in insights],
    )
