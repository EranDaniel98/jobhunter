import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from jwt import PyJWTError as JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_candidate, get_db, get_email_client
from app.infrastructure.redis_client import redis_safe_get, redis_safe_setex
from app.models.candidate import Candidate
from app.rate_limit import limiter
from app.schemas.auth import (
    CandidateResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
)
from app.schemas.candidate import CandidateUpdate
from app.services import auth_service
from app.utils.security import create_verification_token, decode_token, hash_password, verify_password


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger()


@router.post("/register", response_model=CandidateResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    candidate = await auth_service.register(db, data)
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        is_admin=candidate.is_admin,
        email_verified=candidate.email_verified,
        preferences=candidate.preferences,
        plan_tier=candidate.plan_tier,
        onboarding_completed_at=candidate.onboarding_completed_at,
        onboarding_completed=candidate.onboarding_completed_at is not None,
        tour_completed_at=candidate.tour_completed_at,
        tour_completed=candidate.tour_completed_at is not None,
    )


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, data)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest):
    return await auth_service.refresh_token(data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(request: Request, data: LogoutRequest | None = None):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token:
        await auth_service.logout(token, refresh_token=data.refresh_token if data else None)


@router.post("/forgot-password", status_code=200)
@limiter.limit("5/hour")
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.forgot_password(db, data.email)
    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
@limiter.limit("5/hour")
async def reset_password(request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(db, data.token, data.new_password)
    return {"message": "Password reset successfully. You can now log in."}


@router.get("/me", response_model=CandidateResponse)
async def get_me(candidate: Candidate = Depends(get_current_candidate)):
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        email_verified=candidate.email_verified,
        preferences=candidate.preferences,
        plan_tier=candidate.plan_tier,
        onboarding_completed_at=candidate.onboarding_completed_at,
        onboarding_completed=candidate.onboarding_completed_at is not None,
        tour_completed_at=candidate.tour_completed_at,
        tour_completed=candidate.tour_completed_at is not None,
    )


@router.patch("/me", response_model=CandidateResponse)
async def update_me(
    data: CandidateUpdate,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(candidate, key, value)
    await db.commit()
    await db.refresh(candidate)
    logger.info("candidate_updated", candidate_id=str(candidate.id), fields=list(update_data.keys()))
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        email_verified=candidate.email_verified,
        preferences=candidate.preferences,
        plan_tier=candidate.plan_tier,
        onboarding_completed_at=candidate.onboarding_completed_at,
        onboarding_completed=candidate.onboarding_completed_at is not None,
        tour_completed_at=candidate.tour_completed_at,
        tour_completed=candidate.tour_completed_at is not None,
    )


@router.post("/complete-onboarding", response_model=CandidateResponse)
async def complete_onboarding(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Mark onboarding wizard as completed for the current candidate."""
    if candidate.onboarding_completed_at is None:
        candidate.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(candidate)
        logger.info("onboarding_completed", candidate_id=str(candidate.id))
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        email_verified=candidate.email_verified,
        preferences=candidate.preferences,
        plan_tier=candidate.plan_tier,
        onboarding_completed_at=candidate.onboarding_completed_at,
        onboarding_completed=candidate.onboarding_completed_at is not None,
        tour_completed_at=candidate.tour_completed_at,
        tour_completed=candidate.tour_completed_at is not None,
    )


@router.post("/complete-tour", response_model=CandidateResponse)
async def complete_tour(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Mark dashboard tour as completed for the current candidate."""
    if candidate.tour_completed_at is None:
        candidate.tour_completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(candidate)
        logger.info("tour_completed", candidate_id=str(candidate.id))
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        email_verified=candidate.email_verified,
        preferences=candidate.preferences,
        plan_tier=candidate.plan_tier,
        onboarding_completed_at=candidate.onboarding_completed_at,
        onboarding_completed=candidate.onboarding_completed_at is not None,
        tour_completed_at=candidate.tour_completed_at,
        tour_completed=candidate.tour_completed_at is not None,
    )


@router.post("/me/password", status_code=204)
async def change_password(
    data: ChangePasswordRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, candidate.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    candidate.password_hash = hash_password(data.new_password)
    await db.commit()
    logger.info("password_changed", candidate_id=str(candidate.id))


@router.get("/me/api-usage")
async def get_my_api_usage(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's API usage history."""
    from sqlalchemy import func

    from app.models.billing import ApiUsageRecord

    result = await db.execute(
        select(ApiUsageRecord)
        .where(ApiUsageRecord.candidate_id == candidate.id)
        .order_by(ApiUsageRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    records = result.scalars().all()

    count_result = await db.execute(
        select(func.count(ApiUsageRecord.id)).where(ApiUsageRecord.candidate_id == candidate.id)
    )
    total = count_result.scalar() or 0

    return {
        "records": [
            {
                "id": str(r.id),
                "service": r.service,
                "model": r.model,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "estimated_cost_cents": r.estimated_cost_cents,
                "endpoint": r.endpoint,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "total": total,
    }


@router.post("/verify", status_code=200)
async def verify_email(token: str = Query(...), db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link") from None

    if payload.get("type") != "verify":
        raise HTTPException(status_code=400, detail="Invalid token type")

    candidate_id = payload.get("sub")
    result = await db.execute(select(Candidate).where(Candidate.id == uuid.UUID(candidate_id)))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Account not found")

    candidate.email_verified = True
    await db.commit()
    logger.info("email_verified", candidate_id=candidate_id)
    return {"message": "Email verified successfully"}


@router.post("/resend-verification", status_code=200)
async def resend_verification(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    if candidate.email_verified:
        return {"message": "Email already verified"}

    # Rate limit: 1 per 5 minutes
    cooldown_key = f"verify_cooldown:{candidate.id}"
    cooldown = await redis_safe_get(cooldown_key)
    if cooldown:
        raise HTTPException(
            status_code=429,
            detail="Please wait before requesting another verification email",
        )

    await redis_safe_setex(cooldown_key, 300, "1")  # 5 min cooldown

    token = create_verification_token(str(candidate.id))
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    email_client = get_email_client()
    await email_client.send(
        to=candidate.email,
        from_email=settings.SENDER_EMAIL,
        subject=f"Verify your {settings.APP_NAME} account",
        body=(
            f"Hi {candidate.full_name},\n\nPlease verify your email by clicking: {verify_url}"
            "\n\nThis link expires in 24 hours."
        ),
    )
    logger.info("verification_email_resent", candidate_id=str(candidate.id))
    return {"message": "Verification email sent"}
