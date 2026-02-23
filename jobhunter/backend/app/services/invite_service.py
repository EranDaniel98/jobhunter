import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.models.candidate import Candidate
from app.models.invite import InviteCode

logger = structlog.get_logger()


async def create_invite(db: AsyncSession, candidate: Candidate) -> InviteCode:
    code = secrets.token_urlsafe(32)
    invite = InviteCode(
        id=uuid.uuid4(),
        code=code,
        invited_by_id=candidate.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.INVITE_EXPIRE_DAYS),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    logger.info("invite_created", code=code, invited_by=str(candidate.id))
    return invite


async def validate_invite(db: AsyncSession, code: str) -> InviteCode:
    result = await db.execute(
        select(InviteCode)
        .options(joinedload(InviteCode.invited_by))
        .where(InviteCode.code == code)
    )
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code",
        )

    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invite code has already been used",
        )

    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invite code has expired",
        )

    return invite


async def consume_invite(db: AsyncSession, code: str, used_by: Candidate) -> None:
    result = await db.execute(
        select(InviteCode).where(InviteCode.code == code)
    )
    invite = result.scalar_one_or_none()
    if invite:
        invite.is_used = True
        invite.used_by_id = used_by.id
        logger.info("invite_consumed", code=code, used_by=str(used_by.id))


async def list_invites(db: AsyncSession, candidate: Candidate) -> list[InviteCode]:
    result = await db.execute(
        select(InviteCode)
        .options(joinedload(InviteCode.used_by))
        .where(InviteCode.invited_by_id == candidate.id)
        .order_by(InviteCode.created_at.desc())
    )
    return list(result.scalars().all())
