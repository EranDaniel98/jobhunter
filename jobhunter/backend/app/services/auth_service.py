import uuid

import structlog
from fastapi import HTTPException, status
from jwt import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_email_client
from app.infrastructure.redis_client import get_redis
from app.models.candidate import Candidate
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair
from app.services import invite_service
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    create_verification_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = structlog.get_logger()

TOKEN_BLACKLIST_PREFIX = "token:blacklist:"


async def register(db: AsyncSession, data: RegisterRequest) -> Candidate:
    # Check for existing email
    result = await db.execute(select(Candidate).where(Candidate.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    candidate = Candidate(
        id=uuid.uuid4(),
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        preferences=data.preferences.model_dump() if data.preferences else None,
        email_verified=False,
    )
    db.add(candidate)
    await db.flush()

    # Validate and atomically consume invite code (race-condition safe)
    await invite_service.validate_and_consume(db, data.invite_code, candidate.id)

    await db.commit()
    await db.refresh(candidate)
    logger.info("candidate_registered", candidate_id=str(candidate.id), invite_code=data.invite_code)

    # Send verification email (best-effort, don't block registration)
    try:
        token = create_verification_token(str(candidate.id))
        verify_url = f"{settings.FRONTEND_URL}/login?verify={token}"
        email_client = get_email_client()
        await email_client.send(
            to=candidate.email,
            from_email=settings.SENDER_EMAIL,
            subject=f"Verify your {settings.APP_NAME} account",
            body=(
                f"Hi {candidate.full_name},\n\n"
                f"Please verify your email by clicking: {verify_url}\n\n"
                "This link expires in 24 hours."
            ),
        )
        logger.info("verification_email_sent", candidate_id=str(candidate.id))
    except Exception as e:
        logger.warning("verification_email_failed", candidate_id=str(candidate.id), error=str(e))

    return candidate


async def login(db: AsyncSession, data: LoginRequest) -> TokenPair:
    result = await db.execute(select(Candidate).where(Candidate.email == data.email))
    candidate = result.scalar_one_or_none()

    if not candidate or not verify_password(data.password, candidate.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not candidate.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended",
        )

    access_token, _ = create_access_token(str(candidate.id))
    refresh_token, _ = create_refresh_token(str(candidate.id))

    logger.info("candidate_logged_in", candidate_id=str(candidate.id))
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


async def refresh_token(token: str) -> TokenPair:
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Check blacklist
    redis = get_redis()
    jti = payload.get("jti")
    if jti and await redis.get(f"{TOKEN_BLACKLIST_PREFIX}{jti}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    candidate_id = payload["sub"]
    access_token, _ = create_access_token(candidate_id)
    new_refresh, _ = create_refresh_token(candidate_id)

    # Blacklist old refresh token
    if jti:
        ttl = settings.JWT_REFRESH_EXPIRE_DAYS * 86400
        await redis.setex(f"{TOKEN_BLACKLIST_PREFIX}{jti}", ttl, "revoked")

    return TokenPair(access_token=access_token, refresh_token=new_refresh)


async def forgot_password(db: AsyncSession, email: str) -> None:
    """Send a password reset email. Always returns success (no email enumeration)."""
    result = await db.execute(select(Candidate).where(Candidate.email == email))
    candidate = result.scalar_one_or_none()

    if not candidate:
        logger.debug("forgot_password_unknown_email", email=email)
        return  # Silent — no email enumeration

    token = create_reset_token(str(candidate.id))
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    try:
        email_client = get_email_client()
        await email_client.send(
            to=candidate.email,
            from_email=settings.SENDER_EMAIL,
            subject=f"Reset your {settings.APP_NAME} password",
            body=(
                f"Hi {candidate.full_name},\n\n"
                f"Click the link below to reset your password:\n{reset_url}\n\n"
                "This link expires in 2 hours. If you didn't request this, ignore this email."
            ),
        )
        logger.info("reset_email_sent", candidate_id=str(candidate.id))
    except Exception as e:
        logger.warning("reset_email_failed", candidate_id=str(candidate.id), error=str(e))


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    """Reset password using a valid reset token."""
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link",
        ) from None

    if payload.get("type") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token type",
        )

    candidate_id = payload.get("sub")
    result = await db.execute(select(Candidate).where(Candidate.id == uuid.UUID(candidate_id)))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link",
        )

    candidate.password_hash = hash_password(new_password)
    await db.commit()
    logger.info("password_reset", candidate_id=candidate_id)


async def logout(token: str, refresh_token: str | None = None) -> None:
    try:
        payload = decode_token(token)
    except JWTError:
        return  # Already invalid, nothing to blacklist

    jti = payload.get("jti")
    if jti:
        redis = get_redis()
        ttl = settings.JWT_ACCESS_EXPIRE_MINUTES * 60
        await redis.setex(f"{TOKEN_BLACKLIST_PREFIX}{jti}", ttl, "revoked")
        logger.info("token_blacklisted", jti=jti)

    if refresh_token:
        try:
            ref_payload = decode_token(refresh_token)
            ref_jti = ref_payload.get("jti")
            if ref_jti:
                redis = get_redis()
                ttl = settings.JWT_REFRESH_EXPIRE_DAYS * 86400
                await redis.setex(f"{TOKEN_BLACKLIST_PREFIX}{ref_jti}", ttl, "revoked")
                logger.info("refresh_token_blacklisted", jti=ref_jti)
        except Exception as e:
            logger.debug("refresh_token_blacklist_skipped", error=str(e))
