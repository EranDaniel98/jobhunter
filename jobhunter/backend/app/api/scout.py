import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.rate_limit import limiter
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.signal import CompanySignal
from app.schemas.scout import CompanySignalResponse, ScoutRunResponse, ScoutSignalListResponse

router = APIRouter(prefix="/scout", tags=["scout"])
logger = structlog.get_logger()


async def _run_scout_graph(candidate_id: str, plan_tier: str) -> None:
    """Background task to run the scout pipeline."""
    from app.graphs.scout_pipeline import get_scout_pipeline

    thread_id = f"scout-{uuid.uuid4()}"
    state = {
        "candidate_id": candidate_id,
        "plan_tier": plan_tier,
        "search_queries": None,
        "raw_articles": None,
        "parsed_companies": None,
        "scored_companies": None,
        "companies_created": 0,
        "status": "pending",
        "error": None,
    }

    try:
        graph = get_scout_pipeline()
        await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": thread_id}},
        )
        logger.info("scout_graph_completed", candidate_id=candidate_id, thread_id=thread_id)
    except Exception as e:
        logger.error("scout_graph_error", candidate_id=candidate_id, error=str(e))


@router.post("/run", response_model=ScoutRunResponse)
@limiter.limit("2/day")
async def run_scout(
    request: Request,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
) -> ScoutRunResponse:
    """Trigger the scout agent to discover companies from funding news."""
    thread_id = f"scout-{uuid.uuid4()}"
    background_tasks.add_task(_run_scout_graph, str(candidate.id), candidate.plan_tier)
    logger.info("scout_run_triggered", candidate_id=str(candidate.id))
    return ScoutRunResponse(status="scouting", thread_id=thread_id)


@router.get("/signals", response_model=ScoutSignalListResponse)
async def list_signals(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ScoutSignalListResponse:
    """List company signals discovered by the scout agent."""
    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(CompanySignal).where(
            CompanySignal.candidate_id == candidate.id
        )
    )
    total = count_result.scalar() or 0

    # Fetch signals with company name
    query = (
        select(CompanySignal, Company.name)
        .join(Company, CompanySignal.company_id == Company.id)
        .where(CompanySignal.candidate_id == candidate.id)
        .order_by(CompanySignal.detected_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()

    signals = []
    for signal, company_name in rows:
        meta = signal.metadata_ or {}
        signals.append(CompanySignalResponse(
            id=str(signal.id),
            company_id=str(signal.company_id),
            company_name=company_name,
            signal_type=signal.signal_type,
            title=signal.title,
            description=signal.description,
            source_url=signal.source_url,
            signal_strength=signal.signal_strength,
            detected_at=signal.detected_at,
            funding_round=meta.get("funding_round"),
            amount=meta.get("amount"),
        ))

    return ScoutSignalListResponse(signals=signals, total=total)
