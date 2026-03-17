"""Prometheus metrics middleware for HTTP request monitoring."""

import time
from collections.abc import Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/metrics":
            from app.config import settings

            if settings.METRICS_SECRET:
                secret = request.headers.get("X-Metrics-Token", "")
                if secret != settings.METRICS_SECRET:
                    return Response(status_code=403, content="Forbidden")
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )

        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        # Normalize path to avoid high cardinality
        path = request.url.path
        for prefix in ["/api/v1/companies/", "/api/v1/outreach/", "/api/v1/candidates/"]:
            if path.startswith(prefix) and len(path) > len(prefix):
                path = prefix + "{id}"
                break

        REQUEST_COUNT.labels(
            method=request.method,
            path=path,
            status=response.status_code,
        ).inc()

        REQUEST_DURATION.labels(
            method=request.method,
            path=path,
        ).observe(duration)

        return response
