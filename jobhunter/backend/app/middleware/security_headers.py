from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "0"

        # Derive WebSocket CSP origin from FRONTEND_URL
        ws_origin = settings.FRONTEND_URL.replace("https://", "wss://").replace("http://", "ws://")

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://js.stripe.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            f"connect-src 'self' https://api.stripe.com {ws_origin}; "
            "frame-src https://js.stripe.com; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
