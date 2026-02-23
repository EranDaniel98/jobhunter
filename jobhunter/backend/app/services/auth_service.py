import uuid

import structlog
from fastapi import HTTPException, status
from jwt import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.redis_client import get_redis
from app.models.candidate import Candidate
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair
from app.services import invite_service
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = structlog.get_logger()

TOKEN_BLACKLIST_PREFIX = "token:blacklist:"


async def register(db: AsyncSession, data: RegisterRequest) -> Candidate:
    # Validate invite code first
    await invite_service.validate_invite(db, data.invite_code)

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
    )
    db.add(candidate)
    await db.flush()

    # Consume invite code atomically
    await invite_service.consume_invite(db, data.invite_code, candidate)

    await db.commit()
    await db.refresh(candidate)
    logger.info("candidate_registered", candidate_id=str(candidate.id), invite_code=data.invite_code)
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
        )

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


async def logout(token: str) -> None:
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
