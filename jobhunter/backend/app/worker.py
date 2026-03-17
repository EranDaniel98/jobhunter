"""ARQ async worker for background job processing.

Handles:
- Follow-up scheduling: scans for due follow-ups every 15 min
- Approved message sending: sends outreach after approval
- Stale action expiration: expires old pending actions daily
- Daily scout: runs scout pipeline for all active candidates
- Weekly analytics: generates analytics insights for all active candidates
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import structlog
from arq import cron, func
from arq.connections import RedisSettings
from sqlalchemy import exists, select

from app.config import settings
from app.middleware.tenant import current_tenant_id
from app.models.enums import ActionStatus, MessageStatus

logger = structlog.get_logger()


def _chunk_list(items: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of chunk_size."""
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


async def _process_chunk(
    items: list,
    processor,
    concurrency: int,
    job_name: str,
) -> dict:
    """Process items concurrently with error isolation."""
    sem = asyncio.Semaphore(concurrency)
    results = {"succeeded": 0, "failed": 0}

    logger.info(
        "chunk.started",
        extra={
            "feature": "arq_batch",
            "action": job_name,
            "detail": {"chunk_size": len(items)},
        },
    )

    async def _run(item_id):
        async with sem:
            try:
                await processor(item_id)
                results["succeeded"] += 1
            except Exception as e:
                results["failed"] += 1
                logger.error(
                    "chunk.item_failed",
                    extra={
                        "feature": "arq_batch",
                        "action": job_name,
                        "item_id": str(item_id),
                        "status": "failure",
                        "detail": {"error": str(e), "type": type(e).__name__},
                    },
                )

    await asyncio.gather(*[_run(item) for item in items])
    logger.info(
        "chunk.complete",
        extra={
            "feature": "arq_batch",
            "action": job_name,
            "detail": results,
        },
    )
    return results


async def _acquire_run_lock(job_name: str, ttl: int) -> bool:
    """Acquire a Redis-based run lock for cron deduplication."""
    from app.infrastructure.redis_client import get_redis

    redis = get_redis()
    lock_key = f"lock:cron:{job_name}"
    return await redis.set(lock_key, "1", nx=True, ex=ttl)


# Follow-up timing thresholds (days since last sent message)
FOLLOWUP_THRESHOLDS = {
    "initial": ("followup_1", 3),
    "followup_1": ("followup_2", 5),
    "followup_2": ("breakup", 7),
}


async def startup(ctx):
    """Initialize DB and Redis for worker context."""
    from app.infrastructure.database import async_session_factory
    from app.infrastructure.redis_client import init_redis

    ctx["db_factory"] = async_session_factory
    await init_redis()
    logger.info("arq_worker_started")


async def shutdown(ctx):
    from app.infrastructure.redis_client import close_redis

    await close_redis()
    logger.info("arq_worker_stopped")


# ---------------------------------------------------------------------------
# Follow-up cron: coordinator + chunk worker
# ---------------------------------------------------------------------------


async def check_followup_due(ctx):
    """Coordinator: find all due follow-ups and enqueue chunks for processing."""
    if not await _acquire_run_lock("followup_due", ttl=300):
        logger.info("cron.skipped_overlap", extra={"feature": "arq_batch", "action": "check_followup_due"})
        return

    from app.infrastructure.database import async_session_factory
    from app.models.outreach import OutreachMessage

    now = datetime.now(UTC)
    all_message_ids: list = []

    async with async_session_factory() as db:
        for prev_type, (_next_type, days_threshold) in FOLLOWUP_THRESHOLDS.items():
            cutoff = now - timedelta(days=days_threshold)

            query = select(OutreachMessage.id).where(
                OutreachMessage.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED]),
                OutreachMessage.channel == "email",
                OutreachMessage.message_type == prev_type,
                OutreachMessage.sent_at <= cutoff,
            )
            result = await db.execute(query)
            all_message_ids.extend(result.scalars().all())

    total = len(all_message_ids)
    max_items = settings.ARQ_MAX_CHUNKS_PER_RUN * settings.ARQ_CHUNK_SIZE
    processing_ids = all_message_ids[:max_items]
    deferred = total - len(processing_ids)

    if deferred > 0:
        logger.warning(
            "cron.overflow",
            extra={
                "feature": "arq_batch",
                "action": "check_followup_due",
                "detail": {"total": total, "processing": len(processing_ids), "deferred": deferred},
            },
        )

    chunks = _chunk_list(processing_ids, settings.ARQ_CHUNK_SIZE)
    for chunk in chunks:
        await ctx["redis"].enqueue_job("process_followup_chunk", chunk)

    logger.info(
        "cron.started",
        extra={
            "feature": "arq_batch",
            "action": "check_followup_due",
            "detail": {"items_found": total, "chunks_enqueued": len(chunks)},
        },
    )


async def process_followup_chunk(ctx, message_ids: list):
    """Worker: process a chunk of follow-up message IDs."""

    async def process_one_message(message_id):
        from app.infrastructure.database import async_session_factory as sf
        from app.models.candidate import Candidate
        from app.models.outreach import OutreachMessage
        from app.models.pending_action import PendingAction

        token = current_tenant_id.set(None)
        try:
            async with sf() as db:
                result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == message_id))
                msg = result.scalar_one_or_none()
                if msg is None:
                    return

                # Check there's no newer message for this contact
                newer_check = await db.execute(
                    select(OutreachMessage.id)
                    .where(
                        OutreachMessage.contact_id == msg.contact_id,
                        OutreachMessage.candidate_id == msg.candidate_id,
                        OutreachMessage.channel == "email",
                        OutreachMessage.created_at > msg.created_at,
                    )
                    .limit(1)
                )
                if newer_check.scalar_one_or_none():
                    return  # Skip - newer message exists

                # Skip if a pending action already exists for this message
                pending_check = await db.execute(
                    select(PendingAction.id)
                    .where(
                        PendingAction.entity_id == msg.id,
                        PendingAction.status == ActionStatus.PENDING,
                    )
                    .limit(1)
                )
                if pending_check.scalar_one_or_none():
                    return  # Skip - pending action already exists

                # Look up candidate plan_tier
                cand_result = await db.execute(select(Candidate).where(Candidate.id == msg.candidate_id))
                cand = cand_result.scalar_one_or_none()
                plan_tier = cand.plan_tier if cand else "free"

            # Launch the outreach graph for follow-up drafting
            # Graph handles: context → draft → quality check → approval → interrupt
            from app.graphs.outreach import get_outreach_pipeline

            # Determine next_type from FOLLOWUP_THRESHOLDS for logging
            _next_type, _days = FOLLOWUP_THRESHOLDS.get(msg.message_type, (None, 0))

            thread_id = f"outreach-followup-{uuid.uuid4()}"
            state = {
                "candidate_id": str(msg.candidate_id),
                "contact_id": str(msg.contact_id),
                "plan_tier": plan_tier,
                "language": "en",
                "variant": None,
                "attach_resume": True,
                "context": None,
                "message_type": None,
                "outreach_message_id": None,
                "draft_data": None,
                "action_id": None,
                "approval_decision": None,
                "external_message_id": None,
                "status": "pending",
                "error": None,
            }

            graph = get_outreach_pipeline()
            await graph.ainvoke(
                state,
                config={"configurable": {"thread_id": thread_id}},
            )

            logger.info(
                "followup_graph_launched",
                prev_message_id=str(msg.id),
                followup_type=_next_type,
                candidate_id=str(msg.candidate_id),
                thread_id=thread_id,
            )
        finally:
            current_tenant_id.reset(token)

    await _process_chunk(
        message_ids,
        process_one_message,
        settings.ARQ_CHUNK_CONCURRENCY,
        "process_followup_chunk",
    )


# ---------------------------------------------------------------------------
# Daily scout cron: coordinator + chunk worker
# ---------------------------------------------------------------------------


async def run_daily_scout(ctx):
    """Coordinator: find active candidates with DNA and enqueue scout chunks."""
    if not await _acquire_run_lock("daily_scout", ttl=82800):
        logger.info("cron.skipped_overlap", extra={"feature": "arq_batch", "action": "run_daily_scout"})
        return

    from app.infrastructure.database import async_session_factory
    from app.models.candidate import Candidate, CandidateDNA

    async with async_session_factory() as db:
        result = await db.execute(
            select(Candidate.id).where(
                Candidate.is_active,
                exists(select(CandidateDNA.id).where(CandidateDNA.candidate_id == Candidate.id)),
            )
        )
        all_candidate_ids = result.scalars().all()

    total = len(all_candidate_ids)
    max_items = settings.ARQ_MAX_CHUNKS_PER_RUN * settings.ARQ_CHUNK_SIZE
    processing_ids = list(all_candidate_ids)[:max_items]
    deferred = total - len(processing_ids)

    if deferred > 0:
        logger.warning(
            "cron.overflow",
            extra={
                "feature": "arq_batch",
                "action": "run_daily_scout",
                "detail": {"total": total, "processing": len(processing_ids), "deferred": deferred},
            },
        )

    chunks = _chunk_list(processing_ids, settings.ARQ_CHUNK_SIZE)
    for chunk in chunks:
        await ctx["redis"].enqueue_job("process_scout_chunk", chunk)

    logger.info(
        "cron.started",
        extra={
            "feature": "arq_batch",
            "action": "run_daily_scout",
            "detail": {"items_found": total, "chunks_enqueued": len(chunks)},
        },
    )


async def process_scout_chunk(ctx, candidate_ids: list):
    """Worker: run scout pipeline for a chunk of candidate IDs."""

    async def process_one_candidate(candidate_id):
        from app.graphs.scout_pipeline import get_scout_pipeline
        from app.infrastructure.database import async_session_factory as sf
        from app.models.candidate import Candidate

        token = current_tenant_id.set(None)
        try:
            async with sf() as db:
                cand_result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
                cand = cand_result.scalar_one_or_none()
                plan_tier = cand.plan_tier if cand else "free"

            thread_id = f"scout-cron-{uuid.uuid4()}"
            state = {
                "candidate_id": str(candidate_id),
                "plan_tier": plan_tier,
                "search_queries": None,
                "raw_articles": None,
                "parsed_companies": None,
                "scored_companies": None,
                "companies_created": 0,
                "status": "pending",
                "error": None,
            }

            graph = get_scout_pipeline()
            await graph.ainvoke(
                state,
                config={"configurable": {"thread_id": thread_id}},
            )
            logger.info("daily_scout_candidate_done", candidate_id=str(candidate_id), thread_id=thread_id)
        finally:
            current_tenant_id.reset(token)

    await _process_chunk(
        candidate_ids,
        process_one_candidate,
        settings.ARQ_CHUNK_CONCURRENCY,
        "process_scout_chunk",
    )


# ---------------------------------------------------------------------------
# Weekly analytics cron: coordinator + chunk worker
# ---------------------------------------------------------------------------


async def run_weekly_analytics(ctx):
    """Coordinator: find active candidates with DNA and enqueue analytics chunks."""
    if not await _acquire_run_lock("weekly_analytics", ttl=590400):
        logger.info("cron.skipped_overlap", extra={"feature": "arq_batch", "action": "run_weekly_analytics"})
        return

    from app.infrastructure.database import async_session_factory
    from app.models.candidate import Candidate, CandidateDNA

    async with async_session_factory() as db:
        result = await db.execute(
            select(Candidate.id).where(
                Candidate.is_active,
                exists(select(CandidateDNA.id).where(CandidateDNA.candidate_id == Candidate.id)),
            )
        )
        all_candidate_ids = result.scalars().all()

    total = len(all_candidate_ids)
    max_items = settings.ARQ_MAX_CHUNKS_PER_RUN * settings.ARQ_CHUNK_SIZE
    processing_ids = list(all_candidate_ids)[:max_items]
    deferred = total - len(processing_ids)

    if deferred > 0:
        logger.warning(
            "cron.overflow",
            extra={
                "feature": "arq_batch",
                "action": "run_weekly_analytics",
                "detail": {"total": total, "processing": len(processing_ids), "deferred": deferred},
            },
        )

    chunks = _chunk_list(processing_ids, settings.ARQ_CHUNK_SIZE)
    for chunk in chunks:
        await ctx["redis"].enqueue_job("process_analytics_chunk", chunk)

    logger.info(
        "cron.started",
        extra={
            "feature": "arq_batch",
            "action": "run_weekly_analytics",
            "detail": {"items_found": total, "chunks_enqueued": len(chunks)},
        },
    )


async def process_analytics_chunk(ctx, candidate_ids: list):
    """Worker: run analytics pipeline for a chunk of candidate IDs."""

    async def process_one_candidate(candidate_id):
        from app.graphs.analytics_pipeline import get_analytics_pipeline

        token = current_tenant_id.set(None)
        try:
            thread_id = f"analytics-weekly-{uuid.uuid4()}"
            graph = get_analytics_pipeline()
            await graph.ainvoke(
                {
                    "candidate_id": str(candidate_id),
                    "include_email": True,
                    "raw_data": None,
                    "insights": None,
                    "insights_saved": 0,
                    "status": "pending",
                    "error": None,
                },
                config={"configurable": {"thread_id": thread_id}},
            )
            logger.info("weekly_analytics_candidate_done", candidate_id=str(candidate_id), thread_id=thread_id)
        finally:
            current_tenant_id.reset(token)

    await _process_chunk(
        candidate_ids,
        process_one_candidate,
        settings.ARQ_CHUNK_CONCURRENCY,
        "process_analytics_chunk",
    )


# ---------------------------------------------------------------------------
# Unchanged: stale-action expiration and approved message sender
# ---------------------------------------------------------------------------


async def expire_stale_actions(ctx):
    """Expire pending actions older than 30 days."""
    from app.infrastructure.database import async_session_factory
    from app.services.approval_service import expire_stale_actions as _expire

    async with async_session_factory() as db:
        count = await _expire(db)
        if count:
            logger.info("stale_actions_expired_by_cron", count=count)


async def send_approved_message(ctx, outreach_id: str):
    """Send an approved outreach message."""
    from app.infrastructure.database import async_session_factory
    from app.services.email_service import send_outreach

    token = current_tenant_id.set(None)
    try:
        async with async_session_factory() as db:
            from sqlalchemy import select

            from app.models.candidate import Candidate
            from app.models.outreach import OutreachMessage

            result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == uuid.UUID(outreach_id)))
            outreach_msg = result.scalar_one_or_none()
            plan_tier = "free"
            if outreach_msg:
                cand_result = await db.execute(select(Candidate).where(Candidate.id == outreach_msg.candidate_id))
                cand = cand_result.scalar_one_or_none()
                if cand:
                    plan_tier = cand.plan_tier
            await send_outreach(db, uuid.UUID(outreach_id), plan_tier=plan_tier)
            logger.info("approved_message_sent", message_id=outreach_id)
    except Exception as e:
        logger.error("approved_message_send_failed", message_id=outreach_id, error=str(e))
        raise  # Let ARQ mark as failed and retry
    finally:
        current_tenant_id.reset(token)


class WorkerSettings:
    functions: ClassVar[list] = [
        func(send_approved_message, timeout=120),
        func(process_followup_chunk, timeout=600),
        func(process_scout_chunk, timeout=600),
        func(process_analytics_chunk, timeout=600),
    ]
    cron_jobs: ClassVar[list] = [
        cron(check_followup_due, minute={0, 15, 30, 45}),
        cron(expire_stale_actions, hour={3}, minute={0}),  # Daily at 3 AM
        cron(run_daily_scout, hour={9}, minute={0}),  # Daily at 9 AM UTC
        cron(run_weekly_analytics, weekday={0}, hour={8}, minute={0}),  # Mondays 8 AM UTC
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
