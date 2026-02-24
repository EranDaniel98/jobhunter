import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from jwt import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_candidate, get_db, get_email_client
from app.infrastructure.redis_client import get_redis
from app.models.candidate import Candidate
from app.schemas.auth import (
    CandidateResponse,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.candidate import CandidateUpdate
from app.services import auth_service
from app.utils.security import create_verification_token, decode_token, hash_password, verify_password

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
    )


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, data)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest):
    return await auth_service.refresh_token(data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token:
        await auth_service.logout(token)


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


@router.post("/verify", status_code=200)
async def verify_email(token: str = Query(...), db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    if payload.get("type") != "verify":
        raise HTTPException(status_code=400, detail="Invalid token type")

    candidate_id = payload.get("sub")
    result = await db.execute(
        select(Candidate).where(Candidate.id == uuid.UUID(candidate_id))
    )
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
    redis = get_redis()
    cooldown_key = f"verify_cooldown:{candidate.id}"
    ttl = await redis.ttl(cooldown_key)
    if ttl and ttl > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {ttl // 60} min {ttl % 60}s before requesting another email",
        )

    await redis.setex(cooldown_key, 300, "1")  # 5 min cooldown

    token = create_verification_token(str(candidate.id))
    verify_url = f"{settings.FRONTEND_URL}/login?verify={token}"
    email_client = get_email_client()
    await email_client.send(
        to=candidate.email,
        from_email=settings.SENDER_EMAIL,
        subject=f"Verify your {settings.APP_NAME} account",
        body=f"Hi {candidate.full_name},\n\nPlease verify your email by clicking: {verify_url}\n\nThis link expires in 24 hours.",
    )
    logger.info("verification_email_resent", candidate_id=str(candidate.id))
    return {"message": "Verification email sent"}
