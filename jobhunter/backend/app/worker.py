"""ARQ async worker for background job processing.

Handles:
- Follow-up scheduling: scans for due follow-ups every 15 min
- Approved message sending: sends outreach after approval
- Stale action expiration: expires old pending actions daily
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import structlog
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import exists, select

from app.config import settings
from app.models.enums import ActionStatus, MessageStatus

logger = structlog.get_logger()

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


async def check_followup_due(ctx):
    """Scan for messages needing follow-up and auto-draft them."""
    from app.infrastructure.database import async_session_factory
    from app.models.outreach import OutreachMessage
    from app.models.pending_action import PendingAction

    logger.info("followup_check_started")
    now = datetime.now(UTC)
    drafted_count = 0

    async with async_session_factory() as db:
        for prev_type, (next_type, days_threshold) in FOLLOWUP_THRESHOLDS.items():
            cutoff = now - timedelta(days=days_threshold)

            # Find sent/delivered messages of this type that are old enough
            # and have no newer message for the same contact+candidate+channel
            # Find sent/delivered messages of this type that are old enough.
            # Per-message dedup (newer message check, pending action check)
            # happens in the loop below — kept out of the query to avoid
            # a broken self-join that compared columns to themselves.
            query = select(OutreachMessage).where(
                OutreachMessage.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED]),
                OutreachMessage.channel == "email",
                OutreachMessage.message_type == prev_type,
                OutreachMessage.sent_at <= cutoff,
            )

            result = await db.execute(query)
            due_messages = result.scalars().all()

            for msg in due_messages:
                try:
                    # Check there's no newer message for this contact (proper subquery)
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
                        continue  # Skip — newer message exists

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
                        continue  # Skip — pending action already exists

                    # Launch the outreach graph for follow-up drafting
                    # Graph handles: context → draft → quality check → approval → interrupt
                    from app.graphs.outreach import get_outreach_pipeline

                    # Look up candidate plan_tier
                    from app.models.candidate import Candidate

                    cand_result = await db.execute(select(Candidate).where(Candidate.id == msg.candidate_id))
                    cand = cand_result.scalar_one_or_none()
                    plan_tier = cand.plan_tier if cand else "free"

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

                    drafted_count += 1
                    logger.info(
                        "followup_graph_launched",
                        prev_message_id=str(msg.id),
                        followup_type=next_type,
                        candidate_id=str(msg.candidate_id),
                        thread_id=thread_id,
                    )
                except Exception as e:
                    logger.error(
                        "followup_draft_failed",
                        message_id=str(msg.id),
                        error=str(e),
                    )

    logger.info("followup_check_completed", drafted=drafted_count)


async def send_approved_message(ctx, outreach_id: str):
    """Send an approved outreach message."""
    from app.infrastructure.database import async_session_factory
    from app.services.email_service import send_outreach

    async with async_session_factory() as db:
        try:
            # Look up candidate plan_tier for quota enforcement
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


async def run_daily_scout(ctx):
    """Run the scout agent for all active candidates with CandidateDNA."""
    from app.infrastructure.database import async_session_factory
    from app.models.candidate import Candidate, CandidateDNA

    logger.info("daily_scout_started")
    processed = 0
    failed = 0

    async with async_session_factory() as db:
        # Find all active candidates that have DNA
        result = await db.execute(
            select(Candidate).where(
                Candidate.is_active,
                exists(select(CandidateDNA.id).where(CandidateDNA.candidate_id == Candidate.id)),
            )
        )
        candidates = result.scalars().all()

    for cand in candidates:
        try:
            from app.graphs.scout_pipeline import get_scout_pipeline

            thread_id = f"scout-cron-{uuid.uuid4()}"
            state = {
                "candidate_id": str(cand.id),
                "plan_tier": cand.plan_tier,
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
            processed += 1
            logger.info("daily_scout_candidate_done", candidate_id=str(cand.id), thread_id=thread_id)
        except Exception as e:
            failed += 1
            logger.error("daily_scout_candidate_failed", candidate_id=str(cand.id), error=str(e))

    logger.info("daily_scout_completed", processed=processed, failed=failed)


async def expire_stale_actions(ctx):
    """Expire pending actions older than 30 days."""
    from app.infrastructure.database import async_session_factory
    from app.services.approval_service import expire_stale_actions as _expire

    async with async_session_factory() as db:
        count = await _expire(db)
        if count:
            logger.info("stale_actions_expired_by_cron", count=count)


async def run_weekly_analytics(ctx):
    """Generate weekly analytics insights for all active candidates."""
    from app.infrastructure.database import async_session_factory
    from app.models.candidate import Candidate, CandidateDNA

    logger.info("weekly_analytics_started")

    async with async_session_factory() as db:
        result = await db.execute(
            select(Candidate).where(
                Candidate.is_active,
                exists(select(CandidateDNA.id).where(CandidateDNA.candidate_id == Candidate.id)),
            )
        )
        candidates = result.scalars().all()

    for cand in candidates:
        try:
            from app.graphs.analytics_pipeline import get_analytics_pipeline

            thread_id = f"analytics-weekly-{uuid.uuid4()}"
            graph = get_analytics_pipeline()
            await graph.ainvoke(
                {
                    "candidate_id": str(cand.id),
                    "include_email": True,
                    "raw_data": None,
                    "insights": None,
                    "insights_saved": 0,
                    "status": "pending",
                    "error": None,
                },
                config={"configurable": {"thread_id": thread_id}},
            )
        except Exception as e:
            logger.error("weekly_analytics_failed", candidate_id=str(cand.id), error=str(e))

    logger.info("weekly_analytics_completed")


class WorkerSettings:
    functions: ClassVar[list] = [send_approved_message]
    cron_jobs: ClassVar[list] = [
        cron(check_followup_due, minute={0, 15, 30, 45}),
        cron(expire_stale_actions, hour={3}, minute={0}),  # Daily at 3 AM
        cron(run_daily_scout, hour={9}, minute={0}),  # Daily at 9 AM UTC
        cron(run_weekly_analytics, weekday={0}, hour={8}, minute={0}),  # Mondays 8 AM UTC
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
