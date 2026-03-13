"""Waitlist API - public signup endpoint."""

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.waitlist import WaitlistEntry
from app.rate_limit import limiter

logger = structlog.get_logger()

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


class WaitlistRequest(BaseModel):
    email: EmailStr
    source: str = "landing_page"


class WaitlistResponse(BaseModel):
    message: str


@router.post("", response_model=WaitlistResponse)
@limiter.limit("10/minute")
async def join_waitlist(request: Request, body: WaitlistRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == body.email))
    if existing.scalar_one_or_none():
        return WaitlistResponse(message="You're already on the waitlist!")

    entry = WaitlistEntry(email=body.email, source=body.source)
    db.add(entry)
    await db.commit()
    logger.info("waitlist_signup", email=body.email, source=body.source)
    return WaitlistResponse(message="Welcome! You've been added to the waitlist.")
