import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = structlog.get_logger()


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except Exception:
                pass
            request_id = structlog.contextvars.get_contextvars().get("request_id", "unknown")
            logger.error(
                "unhandled_exception",
                error=str(exc),
                error_type=type(exc).__name__,
                path=str(request.url.path),
                method=request.method,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "detail": "An unexpected error occurred.",
                    "request_id": request_id,
                },
            )
