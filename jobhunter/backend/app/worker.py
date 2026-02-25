"""ARQ async worker for background job processing.

Handles:
- Follow-up scheduling: scans for due follow-ups every 15 min
- Approved message sending: sends outreach after approval
- Stale action expiration: expires old pending actions daily
"""
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import and_, exists, select

from app.config import settings

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
    now = datetime.now(timezone.utc)
    drafted_count = 0

    async with async_session_factory() as db:
        for prev_type, (next_type, days_threshold) in FOLLOWUP_THRESHOLDS.items():
            cutoff = now - timedelta(days=days_threshold)

            # Find sent/delivered messages of this type that are old enough
            # and have no newer message for the same contact+candidate+channel
            query = (
                select(OutreachMessage)
                .where(
                    OutreachMessage.status.in_(["sent", "delivered"]),
                    OutreachMessage.channel == "email",
                    OutreachMessage.message_type == prev_type,
                    OutreachMessage.sent_at <= cutoff,
                    # No newer message exists for this contact+candidate+channel
                    ~exists(
                        select(OutreachMessage.id).where(
                            OutreachMessage.contact_id == OutreachMessage.contact_id,
                            OutreachMessage.candidate_id == OutreachMessage.candidate_id,
                            OutreachMessage.channel == OutreachMessage.channel,
                            OutreachMessage.created_at > OutreachMessage.created_at,
                        )
                    ),
                    # No pending action already exists for this entity
                    ~exists(
                        select(PendingAction.id).where(
                            and_(
                                PendingAction.entity_id == OutreachMessage.id,
                                PendingAction.status == "pending",
                            )
                        )
                    ),
                )
            )

            result = await db.execute(query)
            due_messages = result.scalars().all()

            for msg in due_messages:
                try:
                    # Check there's no newer message for this contact (proper subquery)
                    newer_check = await db.execute(
                        select(OutreachMessage.id).where(
                            OutreachMessage.contact_id == msg.contact_id,
                            OutreachMessage.candidate_id == msg.candidate_id,
                            OutreachMessage.channel == "email",
                            OutreachMessage.created_at > msg.created_at,
                        ).limit(1)
                    )
                    if newer_check.scalar_one_or_none():
                        continue  # Skip — newer message exists

                    # Draft the follow-up
                    from app.services.outreach_service import draft_message

                    followup = await draft_message(db, msg.candidate_id, msg.contact_id)

                    # Create PendingAction
                    from app.services.approval_service import create_pending_action

                    await create_pending_action(
                        db,
                        msg.candidate_id,
                        action_type="send_followup",
                        entity_id=followup.id,
                        ai_reasoning=f"Auto-drafted {next_type} after {days_threshold} days with no reply",
                        metadata={"prev_message_id": str(msg.id), "followup_type": next_type},
                    )

                    # Notify via WebSocket
                    from app.infrastructure.websocket_manager import ws_manager

                    await ws_manager.broadcast(
                        str(msg.candidate_id),
                        "followup_drafted",
                        {
                            "message_id": str(followup.id),
                            "contact_id": str(msg.contact_id),
                            "followup_type": next_type,
                        },
                    )

                    drafted_count += 1
                    logger.info(
                        "followup_drafted",
                        prev_message_id=str(msg.id),
                        followup_type=next_type,
                        candidate_id=str(msg.candidate_id),
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
            from app.models.outreach import OutreachMessage
            from app.models.candidate import Candidate
            result = await db.execute(
                select(OutreachMessage).where(OutreachMessage.id == uuid.UUID(outreach_id))
            )
            outreach_msg = result.scalar_one_or_none()
            plan_tier = "free"
            if outreach_msg:
                cand_result = await db.execute(
                    select(Candidate).where(Candidate.id == outreach_msg.candidate_id)
                )
                cand = cand_result.scalar_one_or_none()
                if cand:
                    plan_tier = cand.plan_tier
            msg = await send_outreach(db, uuid.UUID(outreach_id), plan_tier=plan_tier)
            logger.info("approved_message_sent", message_id=outreach_id)
        except Exception as e:
            logger.error("approved_message_send_failed", message_id=outreach_id, error=str(e))


async def expire_stale_actions(ctx):
    """Expire pending actions older than 30 days."""
    from app.infrastructure.database import async_session_factory
    from app.services.approval_service import expire_stale_actions as _expire

    async with async_session_factory() as db:
        count = await _expire(db)
        if count:
            logger.info("stale_actions_expired_by_cron", count=count)


class WorkerSettings:
    functions = [send_approved_message]
    cron_jobs = [
        cron(check_followup_due, minute={0, 15, 30, 45}),
        cron(expire_stale_actions, hour={3}, minute={0}),  # Daily at 3 AM
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
