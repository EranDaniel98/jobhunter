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
from app.models.outreach import MessageEvent, OutreachMessage
from app.models.suppression import EmailSuppression

logger = structlog.get_logger()

DAILY_LIMIT_KEY = "email_limit:{candidate_id}:{date}"


async def send_outreach(db: AsyncSession, outreach_id: uuid.UUID) -> OutreachMessage:
    """Send an outreach email with full compliance checks."""
    result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == outreach_id))
    message = result.scalar_one_or_none()
    if not message:
        raise ValueError("Message not found")

    # Duplicate send prevention
    if message.status not in ("draft", "approved"):
        raise ValueError(f"Cannot send message with status '{message.status}' — already sent or processing")

    # Enforce outreach sequence: followups require the previous message to be sent
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
        if prev_msg and prev_msg.status not in ("sent", "delivered", "opened", "replied"):
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

    # 2. Check daily limit (atomic Redis INCR to avoid race conditions)
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_key = DAILY_LIMIT_KEY.format(candidate_id=message.candidate_id, date=today)
    daily_count = await redis.incr(daily_key)
    if daily_count == 1:
        await redis.expire(daily_key, 86400)
    if daily_count > settings.DAILY_EMAIL_LIMIT:
        await redis.decr(daily_key)  # Roll back the increment
        raise ValueError(f"Daily email limit ({settings.DAILY_EMAIL_LIMIT}) reached")

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

    # 5. Send via email client
    email_client = get_email_client()
    from_email = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"

    try:
        result = await email_client.send(
            to=contact.email,
            from_email=from_email,
            subject=message.subject or "Reaching out",
            body=body_with_footer,
            tags=["outreach", message.message_type],
            headers={
                "List-Unsubscribe": f"<{unsubscribe_link}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        )

        # 6. Update message
        message.external_message_id = result.get("id")
        message.status = "sent"
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
        logger.info("outreach_email_sent", message_id=str(message.id), to=contact.email)
        return message

    except Exception as e:
        message.status = "failed"
        await db.commit()
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
    already_seen = await redis.set(dedup_key, "1", ex=86400, nx=True)
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
        message.status = "delivered"
    elif mapped_type == "opened":
        message.status = "opened"
        message.opened_at = now
    elif mapped_type == "bounced":
        message.status = "bounced"
        # Auto-suppress bounced emails
        await _auto_suppress(db, data.get("to", [None])[0] if isinstance(data.get("to"), list) else data.get("to"), "bounce")
    elif mapped_type == "complained":
        message.status = "failed"
        await _auto_suppress(db, data.get("to", [None])[0] if isinstance(data.get("to"), list) else data.get("to"), "complaint")

    await db.commit()
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
    """Create an HMAC signature for email unsubscribe verification."""
    return hmac.new(
        settings.UNSUBSCRIBE_SECRET.encode(),
        email.encode(),
        hashlib.sha256,
    ).hexdigest() + ":" + email


def verify_unsubscribe_token(token: str) -> str | None:
    """Verify an unsubscribe token and return the email if valid."""
    if ":" not in token:
        return None
    signature, email = token.split(":", 1)
    expected = hmac.new(
        settings.UNSUBSCRIBE_SECRET.encode(),
        email.encode(),
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(signature, expected):
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
