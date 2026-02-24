import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session
from app.infrastructure.redis_client import get_redis

router = APIRouter(tags=["health"])
logger = structlog.get_logger()


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_session),
):
    checks = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"
        logger.error("health_check_db_failed", error=str(e))

    # Redis check
    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"
        logger.error("health_check_redis_failed", error=str(e))

    # Migration version check (informational — does not affect healthy/unhealthy)
    try:
        result = await db.execute(text(
            "SELECT version_num FROM alembic_version LIMIT 1"
        ))
        row = result.first()
        current = row[0] if row else "none"
        checks["migration_version"] = current
    except Exception:
        checks["migration_version"] = "unknown"

    all_healthy = all(v == "healthy" for v in checks.values())
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "version": "0.2.0",
            "checks": checks,
        },
    )
