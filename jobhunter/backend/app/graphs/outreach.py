"""LangGraph outreach email pipeline with human-in-the-loop approval.

8-node StateGraph:
  gather_context -> generate_draft -> quality_check -> create_approval -> INTERRUPT
  ... user approves ...
  -> validate_send -> send_email -> notify_sent -> END

Uses interrupt() for human-in-the-loop approval. PostgreSQL checkpointing
enables crash recovery at every step. Nothing sends without explicit approval.
"""

import json
import uuid
from datetime import UTC, datetime

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select
from typing_extensions import TypedDict

from app.config import settings
from app.dependencies import get_email_client, get_openai
from app.infrastructure import database as _db_mod
from app.infrastructure.websocket_manager import ws_manager
from app.models.analytics import AnalyticsEvent
from app.models.candidate import CandidateDNA, Resume
from app.models.company import CompanyDossier
from app.models.contact import Contact
from app.models.enums import MessageStatus
from app.models.outreach import MessageEvent, OutreachMessage
from app.models.signal import CompanySignal
from app.models.suppression import EmailSuppression
from app.services.outreach_service import (
    LANGUAGE_NAMES,
    MESSAGE_TYPE_INSTRUCTIONS,
    OUTREACH_PROMPT,
    OUTREACH_SCHEMA,
    VARIANT_INSTRUCTIONS,
    _next_message_type,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class OutreachGraphState(TypedDict):
    # Input
    candidate_id: str
    contact_id: str
    plan_tier: str
    language: str  # "en" or "he"
    variant: str | None  # "professional", "conversational", None
    attach_resume: bool
    # Gathered context
    context: dict | None  # {candidate_summary, company_name, domain, ...}
    message_type: str | None  # "initial", "followup_1", etc.
    # Draft output
    outreach_message_id: str | None
    draft_data: dict | None  # {subject, body, personalization_points}
    # Approval
    action_id: str | None  # PendingAction ID
    approval_decision: dict | None  # What interrupt() returns
    # Send output
    external_message_id: str | None
    # Control
    status: str  # "pending"|"drafted"|"awaiting_approval"|"sent"|"failed"
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


async def gather_context_node(state: OutreachGraphState) -> dict:
    """Load Contact, Company, CompanyDossier, CandidateDNA, determine message_type."""
    import asyncio as _asyncio

    contact_id = uuid.UUID(state["contact_id"])
    candidate_id = uuid.UUID(state["candidate_id"])

    async with _db_mod.async_session_factory() as db:
        # Load contact with company eagerly loaded
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(Contact).where(Contact.id == contact_id).options(selectinload(Contact.company))
        )
        contact = result.scalar_one_or_none()
        if not contact:
            return {"status": "failed", "error": f"Contact {contact_id} not found"}

        company = contact.company
        if not company:
            return {"status": "failed", "error": f"Company for contact {contact_id} not found"}

        # Load dossier, DNA, and existing messages in parallel
        dossier_coro = db.execute(select(CompanyDossier).where(CompanyDossier.company_id == company.id))
        dna_coro = db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id))
        existing_coro = db.execute(
            select(OutreachMessage)
            .where(
                OutreachMessage.contact_id == contact_id,
                OutreachMessage.candidate_id == candidate_id,
                OutreachMessage.channel == "email",
            )
            .order_by(OutreachMessage.created_at.desc())
        )
        dossier_result, dna_result, existing_result = await _asyncio.gather(dossier_coro, dna_coro, existing_coro)

        dossier = dossier_result.scalar_one_or_none()
        dna = dna_result.scalar_one_or_none()
        existing_messages = existing_result.scalars().all()
        message_type = _next_message_type(existing_messages)

        # Build recent_news, injecting funding context for scout-sourced companies
        recent_news = json.dumps(dossier.recent_news) if dossier and dossier.recent_news else "None"
        if company.source == "scout_funding":
            signal_result = await db.execute(
                select(CompanySignal)
                .where(
                    CompanySignal.company_id == company.id,
                    CompanySignal.signal_type == "funding_round",
                )
                .order_by(CompanySignal.detected_at.desc())
                .limit(1)
            )
            signal = signal_result.scalar_one_or_none()
            if signal:
                meta = signal.metadata_ or {}
                funding_context = (
                    f"Recently raised {meta.get('funding_round', 'funding')} ({meta.get('amount', 'undisclosed')})"
                )
                recent_news = f"{funding_context}. {recent_news}" if recent_news != "None" else funding_context

    context = {
        "candidate_summary": dna.experience_summary if dna else "No candidate profile",
        "company_name": company.name,
        "domain": company.domain,
        "industry": company.industry or "Unknown",
        "tech_stack": ", ".join(company.tech_stack or []),
        "culture_summary": dossier.culture_summary if dossier else "Unknown",
        "why_hire_me": dossier.why_hire_me if dossier else "Strong candidate fit",
        "recent_news": recent_news,
        "contact_name": contact.full_name,
        "contact_title": contact.title or "Unknown",
        "contact_role": contact.role_type or "Unknown",
        "contact_email": contact.email,
    }

    logger.info("outreach_graph_context_gathered", contact_id=str(contact_id), message_type=message_type)
    return {"context": context, "message_type": message_type}


async def generate_draft_node(state: OutreachGraphState) -> dict:
    """Build prompt, call OpenAI, create OutreachMessage record with status=draft."""
    candidate_id = uuid.UUID(state["candidate_id"])
    contact_id = uuid.UUID(state["contact_id"])
    ctx = state["context"]
    message_type = state["message_type"]
    language = state.get("language", "en")
    variant = state.get("variant")

    language_name = LANGUAGE_NAMES.get(language, "English")

    variant_instruction = ""
    if variant and variant in VARIANT_INSTRUCTIONS:
        variant_instruction = f"\n- TONE: {VARIANT_INSTRUCTIONS[variant]}"

    prompt = OUTREACH_PROMPT.format(
        message_type=message_type,
        candidate_summary=ctx["candidate_summary"],
        company_name=ctx["company_name"],
        domain=ctx["domain"],
        industry=ctx["industry"],
        tech_stack=ctx["tech_stack"],
        culture_summary=ctx["culture_summary"],
        why_hire_me=ctx["why_hire_me"],
        recent_news=ctx["recent_news"],
        contact_name=ctx["contact_name"],
        contact_title=ctx["contact_title"],
        contact_role=ctx["contact_role"],
        message_type_instructions=MESSAGE_TYPE_INSTRUCTIONS.get(message_type, "") + variant_instruction,
        language_name=language_name,
    )

    try:
        client = get_openai()
        result = await client.parse_structured(prompt, "", OUTREACH_SCHEMA)
    except Exception as e:
        logger.error("outreach_graph_draft_failed", error=str(e))
        return {"status": "failed", "error": f"Draft generation failed: {e}"}

    # Create OutreachMessage in DB
    message_id = uuid.uuid4()
    async with _db_mod.async_session_factory() as db:
        message = OutreachMessage(
            id=message_id,
            contact_id=contact_id,
            candidate_id=candidate_id,
            channel="email",
            message_type=message_type,
            subject=result["subject"],
            body=result["body"],
            personalization_data={"points": result.get("personalization_points", [])},
            variant=variant,
            status=MessageStatus.DRAFT,
        )
        db.add(message)
        await db.commit()

    draft_data = {
        "subject": result["subject"],
        "body": result["body"],
        "personalization_points": result.get("personalization_points", []),
    }

    logger.info("outreach_graph_draft_created", message_id=str(message_id), message_type=message_type)
    return {
        "outreach_message_id": str(message_id),
        "draft_data": draft_data,
        "status": "drafted",
    }


async def quality_check_node(state: OutreachGraphState) -> dict:
    """Validate draft has non-empty subject and body. Soft gate."""
    draft = state.get("draft_data")
    if not draft:
        return {"status": "failed", "error": "No draft data available for quality check"}

    subject = draft.get("subject", "")
    body = draft.get("body", "")

    if not subject or not body:
        return {"status": "failed", "error": "Draft has empty subject or body"}

    # Soft warnings (log but don't fail)
    if len(subject) > 200:
        logger.warning("outreach_draft_subject_long", length=len(subject))
    if not draft.get("personalization_points"):
        logger.warning("outreach_draft_no_personalization")

    return {}  # pass through — no state changes needed


async def create_approval_node(state: OutreachGraphState) -> dict:
    """Create PendingAction and interrupt for human approval."""
    candidate_id = uuid.UUID(state["candidate_id"])
    outreach_message_id = uuid.UUID(state["outreach_message_id"])
    thread_id = f"outreach-{state['outreach_message_id']}"

    async with _db_mod.async_session_factory() as db:
        from app.services.approval_service import create_pending_action

        action = await create_pending_action(
            db,
            candidate_id,
            action_type="send_email",
            entity_id=outreach_message_id,
            metadata={"thread_id": thread_id, "attach_resume": state.get("attach_resume", True)},
        )
        action_id = str(action.id)

    # Notify via WebSocket
    await ws_manager.broadcast(
        str(candidate_id),
        "outreach_drafted",
        {
            "message_id": state["outreach_message_id"],
            "action_id": action_id,
            "thread_id": thread_id,
        },
    )

    logger.info("outreach_graph_awaiting_approval", action_id=action_id)

    # INTERRUPT — graph pauses here until resumed
    approval_decision = interrupt(
        {
            "action_id": action_id,
            "outreach_message_id": state["outreach_message_id"],
        }
    )

    return {
        "action_id": action_id,
        "approval_decision": approval_decision,
        "status": "awaiting_approval",
    }


async def validate_send_node(state: OutreachGraphState) -> dict:
    """Validate approval decision and pre-send checks."""
    decision = state.get("approval_decision") or {}

    # Rejection is handled by conditional edge before this node,
    # but double-check in case routing changes
    if not decision.get("approved", False):
        return {"status": "failed", "error": "Message was not approved"}

    outreach_message_id = uuid.UUID(state["outreach_message_id"])
    candidate_id = uuid.UUID(state["candidate_id"])

    async with _db_mod.async_session_factory() as db:
        # Load message
        result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == outreach_message_id))
        message = result.scalar_one_or_none()
        if not message:
            return {"status": "failed", "error": "OutreachMessage not found"}

        # Duplicate send prevention
        if message.status not in (MessageStatus.DRAFT, MessageStatus.APPROVED):
            return {"status": "failed", "error": f"Cannot send message with status '{message.status}'"}

        # Enforce outreach sequence for followups
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
            if prev_msg and prev_msg.status not in (
                MessageStatus.SENT,
                MessageStatus.DELIVERED,
                MessageStatus.OPENED,
                MessageStatus.REPLIED,
            ):
                return {"status": "failed", "error": f"Previous message has status '{prev_msg.status}'"}

        # Get contact email
        contact_result = await db.execute(select(Contact).where(Contact.id == message.contact_id))
        contact = contact_result.scalar_one_or_none()
        if not contact or not contact.email:
            return {"status": "failed", "error": "Contact has no email address"}

        # Check suppression list
        suppressed = await db.execute(select(EmailSuppression).where(EmailSuppression.email == contact.email))
        if suppressed.scalar_one_or_none():
            return {"status": "failed", "error": f"Email {contact.email} is on the suppression list"}

        # Check daily email quota
        plan_tier = state.get("plan_tier", "free")
        from app.services.quota_service import check_and_increment

        try:
            await check_and_increment(str(candidate_id), "email", plan_tier)
        except Exception as e:
            from fastapi import HTTPException as _HTTPException

            if isinstance(e, _HTTPException) and e.status_code == 429:
                detail = e.detail
                msg_text = detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
                return {"status": "failed", "error": msg_text}
            return {"status": "failed", "error": f"Quota check failed: {e}"}

    logger.info("outreach_graph_validated", message_id=state["outreach_message_id"])
    return {}


async def send_email_node(state: OutreachGraphState) -> dict:
    """Append compliance footer, optionally attach resume, send via Resend."""
    outreach_message_id = uuid.UUID(state["outreach_message_id"])
    candidate_id = uuid.UUID(state["candidate_id"])
    decision = state.get("approval_decision") or {}
    attach_resume = decision.get("attach_resume", state.get("attach_resume", False))

    async with _db_mod.async_session_factory() as db:
        result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == outreach_message_id))
        message = result.scalar_one_or_none()
        if not message:
            return {"status": "failed", "error": "OutreachMessage not found for send"}

        contact_result = await db.execute(select(Contact).where(Contact.id == message.contact_id))
        contact = contact_result.scalar_one_or_none()
        if not contact or not contact.email:
            return {"status": "failed", "error": "Contact has no email for send"}

        # Compliance footer
        from app.services.email_service import generate_unsubscribe_link

        unsubscribe_link = generate_unsubscribe_link(contact.email)
        body_with_footer = (
            f"{message.body}\n\n"
            f"---\n"
            f"{settings.SENDER_NAME} | {settings.PHYSICAL_ADDRESS}\n"
            f"Unsubscribe: {unsubscribe_link}"
        )

        # Attachments (resume PDF if requested)
        attachments = None
        if attach_resume:
            resume_result = await db.execute(
                select(Resume).where(
                    Resume.candidate_id == candidate_id,
                    Resume.is_primary,
                )
            )
            resume = resume_result.scalar_one_or_none()
            if resume and resume.file_path:
                from app.infrastructure.storage import get_storage

                try:
                    storage = get_storage()
                    file_data = await storage.download(resume.file_path)
                    filename = resume.file_path.rsplit("/", 1)[-1]
                    attachments = [{"filename": filename, "content": list(file_data)}]
                    logger.info("outreach_graph_attaching_resume", key=resume.file_path)
                except Exception as e:
                    logger.warning("outreach_graph_resume_download_failed", key=resume.file_path, error=str(e))

        # Send via email client
        email_client = get_email_client()
        from_email = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"

        # Get candidate's email for Reply-To
        from app.models.candidate import Candidate

        candidate_result = await db.execute(select(Candidate.email).where(Candidate.id == candidate_id))
        candidate_email = candidate_result.scalar_one_or_none()

        # Build headers — threading for follow-ups
        send_headers = {
            "List-Unsubscribe": f"<mailto:unsubscribe@hunter-job.com?subject=unsubscribe>, <{unsubscribe_link}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
        # Thread follow-ups under the original email
        if message.message_type != "initial":
            prev_result = await db.execute(
                select(OutreachMessage.external_message_id)
                .where(
                    OutreachMessage.contact_id == message.contact_id,
                    OutreachMessage.candidate_id == candidate_id,
                    OutreachMessage.created_at < message.created_at,
                )
                .order_by(OutreachMessage.created_at.desc())
                .limit(1)
            )
            prev_ext_id = prev_result.scalar_one_or_none()
            if prev_ext_id:
                send_headers["In-Reply-To"] = f"<{prev_ext_id}>"
                send_headers["References"] = f"<{prev_ext_id}>"

        if not message.subject:
            return {"status": "failed", "error": "Cannot send email without a subject"}

        try:
            send_result = await email_client.send(
                to=contact.email,
                from_email=from_email,
                subject=message.subject,
                body=body_with_footer,
                tags=["outreach", message.message_type],
                headers=send_headers,
                attachments=attachments,
                reply_to=candidate_email,
            )
        except Exception as e:
            message.status = MessageStatus.FAILED
            await db.commit()
            logger.error("outreach_graph_send_failed", error=str(e), message_id=str(outreach_message_id))
            return {"status": "failed", "error": f"Failed to send email: {e}"}

        # Update message
        external_id = send_result.get("id")
        message.external_message_id = external_id
        message.status = MessageStatus.SENT
        message.sent_at = datetime.now(UTC)

        # Create events
        event = MessageEvent(
            id=uuid.uuid4(),
            outreach_message_id=message.id,
            event_type="sent",
            occurred_at=datetime.now(UTC),
        )
        db.add(event)

        analytics = AnalyticsEvent(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            event_type="email_sent",
            entity_type="outreach_message",
            entity_id=message.id,
            metadata_={"to": contact.email, "channel": message.channel},
            occurred_at=datetime.now(UTC),
        )
        db.add(analytics)

        await db.commit()

    logger.info("outreach_graph_email_sent", message_id=str(outreach_message_id), to=contact.email)
    return {"external_message_id": external_id, "status": "sent"}


async def notify_sent_node(state: OutreachGraphState) -> dict:
    """Broadcast WebSocket notification and finalize."""
    candidate_id = state["candidate_id"]
    outreach_message_id = state["outreach_message_id"]

    await ws_manager.broadcast(
        str(candidate_id),
        "email_sent",
        {"message_id": outreach_message_id, "status": "sent"},
    )

    logger.info("outreach_graph_notify_sent", message_id=outreach_message_id)
    return {"status": "sent"}


async def mark_failed_node(state: OutreachGraphState) -> dict:
    """Mark OutreachMessage as failed and broadcast failure."""
    candidate_id = state["candidate_id"]
    error = state.get("error", "unknown error")
    outreach_message_id = state.get("outreach_message_id")

    if outreach_message_id:
        async with _db_mod.async_session_factory() as db:
            result = await db.execute(
                select(OutreachMessage).where(OutreachMessage.id == uuid.UUID(outreach_message_id))
            )
            message = result.scalar_one_or_none()
            if message:
                message.status = MessageStatus.FAILED
                await db.commit()

    await ws_manager.broadcast(
        str(candidate_id),
        "outreach_failed",
        {"message_id": outreach_message_id, "error": error},
    )

    logger.error("outreach_graph_failed", message_id=outreach_message_id, error=error)
    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def _check_error(state: OutreachGraphState) -> str:
    if state.get("status") == "failed":
        return "mark_failed"
    return "continue"


def _check_rejection(state: OutreachGraphState) -> str:
    decision = state.get("approval_decision") or {}
    if not decision.get("approved", False):
        return "rejected"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_outreach_pipeline() -> StateGraph:
    """Build (but don't compile) the outreach graph."""
    builder = StateGraph(OutreachGraphState)

    # Add nodes
    builder.add_node("gather_context", gather_context_node)
    builder.add_node("generate_draft", generate_draft_node)
    builder.add_node("quality_check", quality_check_node)
    builder.add_node("create_approval", create_approval_node)
    builder.add_node("validate_send", validate_send_node)
    builder.add_node("send_email", send_email_node)
    builder.add_node("notify_sent", notify_sent_node)
    builder.add_node("mark_failed", mark_failed_node)

    # Edges
    builder.add_edge(START, "gather_context")

    builder.add_conditional_edges(
        "gather_context",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "generate_draft"},
    )
    builder.add_conditional_edges(
        "generate_draft",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "quality_check"},
    )
    builder.add_conditional_edges(
        "quality_check",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "create_approval"},
    )
    # After create_approval: interrupt() pauses, then resumes with approval_decision
    builder.add_conditional_edges(
        "create_approval",
        _check_rejection,
        {"rejected": END, "continue": "validate_send"},
    )
    builder.add_conditional_edges(
        "validate_send",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "send_email"},
    )
    builder.add_conditional_edges(
        "send_email",
        _check_error,
        {"mark_failed": "mark_failed", "continue": "notify_sent"},
    )
    builder.add_edge("notify_sent", END)
    builder.add_edge("mark_failed", END)

    return builder


# Module-level builder (reusable)
_builder = build_outreach_pipeline()


# ---------------------------------------------------------------------------
# Graph accessors
# ---------------------------------------------------------------------------


def get_outreach_pipeline(checkpointer=None):
    """Production: compiled graph with PostgreSQL checkpointer."""
    from app.graphs.resume_pipeline import _checkpointer as shared

    return _builder.compile(checkpointer=checkpointer or shared)


def get_outreach_pipeline_no_checkpointer():
    """Testing: compiled graph without checkpointer."""
    return _builder.compile()
