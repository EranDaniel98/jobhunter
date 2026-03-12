"""HTTP response utilities."""

import structlog
from fastapi import HTTPException

logger = structlog.get_logger()


def safe_400(e: Exception, fallback: str = "Invalid request") -> HTTPException:
    """Log the full error but return only a safe message to the client."""
    logger.warning("client_error", error=str(e), fallback=fallback)
    return HTTPException(status_code=400, detail=fallback)
