import structlog
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = structlog.get_logger()


def _get_rate_limit_key(request: Request) -> str:
    """Use candidate_id from JWT when available, fall back to real IP.

    Behind Cloudflare, all traffic shares the same origin IP.
    CF-Connecting-IP gives the real client IP as fallback.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from app.utils.security import decode_token

            payload = decode_token(auth_header[7:])
            candidate_id = payload.get("sub")
            if candidate_id:
                return f"user:{candidate_id}"
        except Exception as e:
            logger.debug("rate_limit_key_jwt_decode_failed", error=str(e))

    # Try Cloudflare header for real client IP
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip

    return get_remote_address(request)


limiter = Limiter(key_func=_get_rate_limit_key)
