import hashlib
import hmac
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_email_client
from app.infrastructure.redis_client import get_redis
from app.models.analytics import AnalyticsEvent
from app.models.contact import Contact
from app.models.enums import MessageStatus
from app.models.outreach import MessageEvent, OutreachMessage
from app.models.candidate import Candidate, Resume
from app.models.suppression import EmailSuppression

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Email warm-up tracking
# ---------------------------------------------------------------------------
# New sending domains need gradual ramp-up to build reputation with ISPs.
# Redis keys:
#   email_warmup:{domain}:start_date  — ISO date when sending started
#   email_warmup:{domain}:daily:{date} — send count for that date
# ---------------------------------------------------------------------------

WARMUP_START_KEY = "email_warmup:{domain}:start_date"
WARMUP_DAILY_KEY = "email_warmup:{domain}:daily:{date}"

# Ramp-up schedule: (day_threshold, max_sends_per_day)
WARMUP_SCHEDULE = [
    (3, 5),    # Day 1-3:  max 5 emails/day
    (7, 15),   # Day 4-7:  max 15 emails/day
    (14, 30),  # Day 8-14: max 30 emails/day
]
WARMUP_GRADUATED_LIMIT = 50  # Day 15+: full limit (or plan limit, whichever is lower)


async def get_warmup_limit(domain: str) -> int:
    """Return the current max daily sends for *domain* based on warm-up age.

    If this is the first time we see the domain, the start date is recorded
    automatically and the most conservative limit is returned.
    """
    redis = get_redis()
    today = datetime.now(timezone.utc).date()
    start_key = WARMUP_START_KEY.format(domain=domain)

    start_date_str = await redis.get(start_key)
    if start_date_str is None:
        # First send ever for this domain — record today as day-0
        await redis.set(start_key, today.isoformat())
        start_date_str = today.isoformat()
        logger.info("warmup_domain_registered", domain=domain, start_date=start_date_str)

    start_date = datetime.fromisoformat(start_date_str).date()
    domain_age_days = (today - start_date).days + 1  # day 1 = first day

    for threshold, limit in WARMUP_SCHEDULE:
        if domain_age_days <= threshold:
            return limit

    return WARMUP_GRADUATED_LIMIT


async def check_warmup_quota(domain: str) -> None:
    """Raise ValueError if the domain has hit its warm-up daily limit."""
    redis = get_redis()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_key = WARMUP_DAILY_KEY.format(domain=domain, date=today_str)

    current = await redis.get(daily_key)
    current_count = int(current) if current else 0

    limit = await get_warmup_limit(domain)

    if current_count >= limit:
        logger.warning(
            "warmup_limit_reached",
            domain=domain,
            current=current_count,
            limit=limit,
        )
        raise ValueError(
            f"Domain {domain} warm-up limit reached: {current_count}/{limit} emails sent today. "
            f"Limit increases automatically as the domain ages."
        )


async def increment_warmup_count(domain: str) -> None:
    """Increment the daily warm-up counter for *domain*."""
    redis = get_redis()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_key = WARMUP_DAILY_KEY.format(domain=domain, date=today_str)

    await redis.incr(daily_key)
    # Expire after 48 h so old counters don't accumulate
    await redis.expire(daily_key, 48 * 3600)


def _extract_domain(email: str) -> str:
    """Extract the domain part from an email address."""
    return email.rsplit("@", 1)[-1].lower()

async def send_outreach(db: AsyncSession, outreach_id: uuid.UUID, attach_resume: bool = False, plan_tier: str = "free") -> OutreachMessage:
    """Send an outreach email with full compliance checks."""
    result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == outreach_id))
    message = result.scalar_one_or_none()
    if not message:
        raise ValueError("Message not found")

    # Duplicate send prevention
    if message.status not in (MessageStatus.DRAFT, MessageStatus.APPROVED):
        raise ValueError(f"Cannot send message with status '{message.status}' — already sent or processing")

    # Enforce outreach sequence: followups require the previous message to be sent
    prev_msg = None
    if message.message_type != "initial":
        prev_msgs = await db.execute(
            select(OutreachMessage)
            .where(
                OutreachMessage.contact_id == message.contact_id,
                OutreachMessage.candidate_id == message.candidate_id,
                OutreachMessage.channel == message.channel,
                OutreachMessage.created_at < message.created_at,
            )
            .order_by(OutreachMessage.created_at.desc())
            .limit(1)
        )
        prev_msg = prev_msgs.scalar_one_or_none()
        if prev_msg and prev_msg.status not in (MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.OPENED, MessageStatus.REPLIED):
            raise ValueError(
                f"Cannot send followup: previous message (id={prev_msg.id}) has status '{prev_msg.status}'"
            )

    # Get contact email
    contact_result = await db.execute(select(Contact).where(Contact.id == message.contact_id))
    contact = contact_result.scalar_one_or_none()
    if not contact or not contact.email:
        raise ValueError("Contact has no email address")

    # 1. Check suppression list
    suppressed = await db.execute(
        select(EmailSuppression).where(EmailSuppression.email == contact.email)
    )
    if suppressed.scalar_one_or_none():
        raise ValueError(f"Email {contact.email} is on the suppression list")

    # 2. Check daily email limit via unified quota service
    from app.services.quota_service import check_and_increment
    try:
        await check_and_increment(str(message.candidate_id), "email", plan_tier)
    except Exception as e:
        # Convert HTTPException from quota service to ValueError for email service callers
        from fastapi import HTTPException as _HTTPException
        if isinstance(e, _HTTPException) and e.status_code == 429:
            detail = e.detail
            msg_text = detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
            raise ValueError(msg_text)
        raise

    # 2b. Check domain warm-up limit
    sender_domain = _extract_domain(settings.SENDER_EMAIL)
    try:
        await check_warmup_quota(sender_domain)
    except ValueError:
        raise  # Propagate warm-up limit errors as-is
    except Exception as e:
        # Redis failure — log and allow (graceful degradation)
        logger.warning("warmup_check_failed", domain=sender_domain, error=str(e))

    # 3. Warn if unverified (but don't block)
    if not contact.email_verified:
        logger.warning("sending_to_unverified_email", email=contact.email)

    # 4. Append compliance footer
    unsubscribe_link = generate_unsubscribe_link(contact.email)
    body_with_footer = (
        f"{message.body}\n\n"
        f"---\n"
        f"{settings.SENDER_NAME} | {settings.PHYSICAL_ADDRESS}\n"
        f"Unsubscribe: {unsubscribe_link}"
    )

    # 5. Build attachments (resume PDF if requested)
    attachments = None
    if attach_resume:
        resume_result = await db.execute(
            select(Resume).where(
                Resume.candidate_id == message.candidate_id,
                Resume.is_primary == True,
            )
        )
        resume = resume_result.scalar_one_or_none()
        if resume and resume.file_path:
            from app.infrastructure.storage import get_storage
            try:
                storage = get_storage()
                file_data = await storage.download(resume.file_path)
                filename = resume.file_path.rsplit("/", 1)[-1]
                attachments = [{
                    "filename": filename,
                    "content": list(file_data),
                }]
                logger.info("attaching_resume", key=resume.file_path)
            except Exception as e:
                logger.warning("resume_download_failed", key=resume.file_path, error=str(e))

    # 6. Send via email client
    email_client = get_email_client()
    from_email = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"

    # Get candidate's email for Reply-To (so replies go to the actual person)
    candidate_result = await db.execute(
        select(Candidate.email).where(Candidate.id == message.candidate_id)
    )
    candidate_email = candidate_result.scalar_one_or_none()

    # Build headers — threading for follow-ups
    send_headers = {
        "List-Unsubscribe": f"<mailto:unsubscribe@hunter-job.com?subject=unsubscribe>, <{unsubscribe_link}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    if message.message_type != "initial" and prev_msg and prev_msg.external_message_id:
        send_headers["In-Reply-To"] = f"<{prev_msg.external_message_id}>"
        send_headers["References"] = f"<{prev_msg.external_message_id}>"

    if not message.subject:
        raise ValueError("Cannot send email without a subject")

    try:
        result = await email_client.send(
            to=contact.email,
            from_email=from_email,
            subject=message.subject,
            body=body_with_footer,
            tags=["outreach", message.message_type],
            headers=send_headers,
            attachments=attachments,
            reply_to=candidate_email,
        )

        # 6. Update message
        message.external_message_id = result.get("id")
        message.status = MessageStatus.SENT
        message.sent_at = datetime.now(timezone.utc)

        # 7. Create events
        event = MessageEvent(
            id=uuid.uuid4(),
            outreach_message_id=message.id,
            event_type="sent",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(event)

        analytics = AnalyticsEvent(
            id=uuid.uuid4(),
            candidate_id=message.candidate_id,
            event_type="email_sent",
            entity_type="outreach_message",
            entity_id=message.id,
            metadata_={"to": contact.email, "channel": message.channel},
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(analytics)

        await db.commit()
        await db.refresh(message)

        # Notify via WebSocket
        from app.infrastructure.websocket_manager import ws_manager
        await ws_manager.broadcast(
            str(message.candidate_id), "email_sent",
            {"message_id": str(message.id), "contact_email": contact.email},
        )

        from app.events.bus import get_event_bus
        await get_event_bus().publish(
            "outreach_sent",
            {"candidate_id": str(message.candidate_id), "contact_id": str(message.contact_id), "message_id": str(message.id)},
            source="email_service.send_outreach",
        )

        # 8. Increment domain warm-up counter
        try:
            await increment_warmup_count(sender_domain)
        except Exception as e:
            logger.warning("warmup_increment_failed", domain=sender_domain, error=str(e))

        logger.info("outreach_email_sent", message_id=str(message.id), to=contact.email)
        return message

    except Exception as e:
        message.status = MessageStatus.FAILED
        await db.commit()
        # Restore quota — email was never sent
        try:
            from app.services.quota_service import QUOTA_KEY
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            key = QUOTA_KEY.format(candidate_id=str(message.candidate_id), quota_type="email", date=today)
            redis = get_redis()
            await redis.decr(key)
        except Exception as e:
            logger.warning("quota_decr_failed_after_send_error", message_id=str(message.id), error=str(e))
        logger.error("email_send_failed", error=str(e), message_id=str(message.id))
        raise ValueError(f"Failed to send email: {e}")


WEBHOOK_DEDUP_PREFIX = "webhook:seen:"


async def handle_resend_webhook(
    db: AsyncSession, payload: dict
) -> None:
    """Process a Resend webhook event."""
    event_type = payload.get("type", "")
    data = payload.get("data", {})
    external_id = data.get("email_id")

    if not external_id:
        logger.warning("webhook_missing_email_id", payload=payload)
        return

    # Replay protection: deduplicate by event_id
    event_id = data.get("event_id") or f"{external_id}:{event_type}"
    redis = get_redis()
    dedup_key = f"{WEBHOOK_DEDUP_PREFIX}{event_id}"
    from app.config import settings
    already_seen = await redis.set(dedup_key, "1", ex=settings.REDIS_WEBHOOK_DEDUP_TTL, nx=True)
    if not already_seen:
        logger.info("webhook_duplicate_skipped", event_id=event_id)
        return

    # Find the outreach message
    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.external_message_id == external_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        logger.warning("webhook_message_not_found", external_id=external_id)
        return

    now = datetime.now(timezone.utc)

    # Map Resend event types
    event_map = {
        "email.delivered": "delivered",
        "email.opened": "opened",
        "email.clicked": "clicked",
        "email.bounced": "bounced",
        "email.complained": "complained",
    }

    mapped_type = event_map.get(event_type)
    if not mapped_type:
        logger.info("webhook_unknown_event", event_type=event_type)
        return

    # Create MessageEvent
    event = MessageEvent(
        id=uuid.uuid4(),
        outreach_message_id=message.id,
        event_type=mapped_type,
        metadata_=data,
        occurred_at=now,
    )
    db.add(event)

    # Update message status
    if mapped_type == "delivered":
        message.status = MessageStatus.DELIVERED
    elif mapped_type == "opened":
        message.status = MessageStatus.OPENED
        message.opened_at = now
    elif mapped_type == "bounced":
        message.status = MessageStatus.BOUNCED
        # Auto-suppress bounced emails
        await _auto_suppress(db, data.get("to", [None])[0] if isinstance(data.get("to"), list) else data.get("to"), "bounce")
    elif mapped_type == "complained":
        message.status = MessageStatus.FAILED
        await _auto_suppress(db, data.get("to", [None])[0] if isinstance(data.get("to"), list) else data.get("to"), "complaint")

    await db.commit()

    # Notify via WebSocket
    from app.infrastructure.websocket_manager import ws_manager
    ws_event = f"email_{mapped_type}"  # email_delivered, email_opened, etc.
    await ws_manager.broadcast(
        str(message.candidate_id), ws_event,
        {"message_id": str(message.id), "event_type": mapped_type},
    )

    logger.info("webhook_processed", event_type=mapped_type, message_id=str(message.id))


async def _auto_suppress(db: AsyncSession, email: str | None, reason: str) -> None:
    """Auto-add to suppression list on bounce/complaint."""
    if not email:
        return

    existing = await db.execute(
        select(EmailSuppression).where(EmailSuppression.email == email)
    )
    if not existing.scalar_one_or_none():
        suppression = EmailSuppression(
            id=uuid.uuid4(),
            email=email,
            reason=reason,
            suppressed_at=datetime.now(timezone.utc),
        )
        db.add(suppression)
        logger.info("email_auto_suppressed", email=email, reason=reason)


def generate_unsubscribe_link(email: str) -> str:
    """Generate a signed unsubscribe URL."""
    token = _sign_email(email)
    return f"{settings.FRONTEND_URL}/unsubscribe/{token}"


def _sign_email(email: str) -> str:
    """Create an HMAC signature for email unsubscribe verification (with timestamp)."""
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    msg = f"{ts}:{email}"
    sig = hmac.new(
        settings.UNSUBSCRIBE_SECRET.encode(), msg.encode(), hashlib.sha256
    ).hexdigest()
    return f"{sig}:{ts}:{email}"


def verify_unsubscribe_token(token: str) -> str | None:
    """Verify an unsubscribe token and return the email if valid."""
    parts = token.split(":", 2)
    if len(parts) == 3:
        sig, ts, email = parts
        # Reject tokens older than 90 days
        try:
            if int(ts) < int(datetime.now(timezone.utc).timestamp()) - 90 * 86400:
                return None
        except ValueError:
            return None
        expected = hmac.new(
            settings.UNSUBSCRIBE_SECRET.encode(), f"{ts}:{email}".encode(), hashlib.sha256
        ).hexdigest()
        return email if hmac.compare_digest(sig, expected) else None
    elif len(parts) == 2:
        # Legacy format — accept but log deprecation
        sig, email = parts
        expected = hmac.new(
            settings.UNSUBSCRIBE_SECRET.encode(), email.encode(), hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(sig, expected):
            logger.info("legacy_unsubscribe_token_used", email=email)
            return email
    return None


async def process_unsubscribe(db: AsyncSession, token: str) -> bool:
    """Process an unsubscribe request."""
    email = verify_unsubscribe_token(token)
    if not email:
        return False

    existing = await db.execute(
        select(EmailSuppression).where(EmailSuppression.email == email)
    )
    if not existing.scalar_one_or_none():
        suppression = EmailSuppression(
            id=uuid.uuid4(),
            email=email,
            reason="unsubscribe",
            suppressed_at=datetime.now(timezone.utc),
        )
        db.add(suppression)
        await db.commit()
        logger.info("email_unsubscribed", email=email)

    return True
