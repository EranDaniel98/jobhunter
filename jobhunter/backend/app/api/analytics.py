from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.schemas.analytics import FunnelResponse, OutreachStatsResponse, PipelineStatsResponse
from app.services import analytics_service

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
