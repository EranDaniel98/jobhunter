import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_email_client
from app.services.email_service import handle_resend_webhook, process_unsubscribe

router = APIRouter(tags=["webhooks"])
logger = structlog.get_logger()


@router.post("/webhooks/resend")
async def resend_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Resend webhook events (no JWT auth — uses Svix signature verification)."""
    body = await request.body()
    signature = request.headers.get("svix-signature", "")

    email_client = get_email_client()

    try:
        payload = email_client.verify_webhook(body, signature)
    except Exception as e:
        logger.warning("webhook_verification_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    await handle_resend_webhook(db, payload)
    return {"status": "ok"}


@router.get("/unsubscribe/{token}")
async def unsubscribe(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle email unsubscribe (no JWT auth — recipient clicks link)."""
    success = await process_unsubscribe(db, token)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired unsubscribe link")
    return {"status": "unsubscribed", "message": "You have been successfully unsubscribed."}
