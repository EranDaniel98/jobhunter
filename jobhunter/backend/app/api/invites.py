import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.schemas.invite import InviteCreateResponse, InviteListItem, InviteValidateResponse
from app.services import invite_service

router = APIRouter(prefix="/invites", tags=["invites"])
logger = structlog.get_logger()


@router.post("", response_model=InviteCreateResponse, status_code=201)
async def create_invite(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    invite = await invite_service.create_invite(db, candidate)
    invite_url = f"{settings.FRONTEND_URL}/register?invite={invite.code}"
    return InviteCreateResponse(
        code=invite.code,
        invite_url=invite_url,
        expires_at=invite.expires_at,
    )


@router.get("/{code}/validate", response_model=InviteValidateResponse)
async def validate_invite(code: str, db: AsyncSession = Depends(get_db)):
    invite = await invite_service.validate_invite(db, code)
    return InviteValidateResponse(
        valid=True,
        invited_by_name=invite.invited_by.full_name if invite.invited_by else None,
    )


@router.get("", response_model=list[InviteListItem])
async def list_invites(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    invites = await invite_service.list_invites(db, candidate)
    return [
        InviteListItem(
            id=str(inv.id),
            code=inv.code,
            is_used=inv.is_used,
            used_by_email=inv.used_by.email if inv.used_by else None,
            expires_at=inv.expires_at,
            created_at=inv.created_at,
        )
        for inv in invites
    ]
