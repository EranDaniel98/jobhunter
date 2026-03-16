import uuid

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session
from app.infrastructure.protocols import (
    EmailClientProtocol,
    HunterClientProtocol,
    NewsAPIClientProtocol,
    OpenAIClientProtocol,
)
from app.infrastructure.redis_client import get_redis
from app.models.candidate import Candidate
from app.utils.security import decode_token

logger = structlog.get_logger()

security = HTTPBearer()

TOKEN_BLACKLIST_PREFIX = "token:blacklist:"

# Singleton client instances (initialized on first use)
_openai_client: OpenAIClientProtocol | None = None
_hunter_client: HunterClientProtocol | None = None
_email_client: EmailClientProtocol | None = None
_newsapi_client: NewsAPIClientProtocol | None = None


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async for session in get_session():
        yield session


async def get_admin_db() -> AsyncSession:  # type: ignore[misc]
    """Admin database session that bypasses RLS filtering."""
    async for session in get_session():
        yield session.execution_options(_bypass_rls=True)


def get_openai() -> OpenAIClientProtocol:
    global _openai_client
    if _openai_client is None:
        from app.infrastructure.openai_client import OpenAIClient

        _openai_client = OpenAIClient()
    return _openai_client


def get_hunter() -> HunterClientProtocol:
    global _hunter_client
    if _hunter_client is None:
        from app.infrastructure.hunter_client import HunterClient

        _hunter_client = HunterClient()
    return _hunter_client


def get_newsapi() -> NewsAPIClientProtocol:
    global _newsapi_client
    if _newsapi_client is None:
        from app.infrastructure.newsapi_client import NewsAPIClient

        _newsapi_client = NewsAPIClient()
    return _newsapi_client


def get_email_client() -> EmailClientProtocol:
    global _email_client
    if _email_client is None:
        from app.infrastructure.resend_client import ResendClient

        _email_client = ResendClient()
    return _email_client


async def get_current_candidate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Candidate:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Check blacklist (fail closed: if Redis is down, reject request)
    jti = payload.get("jti")
    if jti:
        try:
            blacklisted = await get_redis().get(f"{TOKEN_BLACKLIST_PREFIX}{jti}")
        except Exception as exc:
            logger.warning("token_blacklist_check_failed_redis_unavailable", jti=jti)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            ) from exc
        if blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )

    candidate_id = payload.get("sub")
    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(Candidate).where(Candidate.id == uuid.UUID(candidate_id)))
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Candidate not found",
        )

    return candidate


async def get_current_admin(
    candidate: Candidate = Depends(get_current_candidate),
) -> Candidate:
    if not candidate.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return candidate
