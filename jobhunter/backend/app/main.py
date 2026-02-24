from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.infrastructure.database import engine
from app.infrastructure.redis_client import close_redis, init_redis
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging_config import setup_logging
from app.middleware.request_id import RequestIDMiddleware
from app.rate_limit import limiter

logger = structlog.get_logger()


_JWT_DEFAULT = "change-me-to-a-random-secret-in-production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    if settings.JWT_SECRET == _JWT_DEFAULT:
        logger.critical(
            "jwt_secret_not_configured",
            msg="JWT_SECRET is still set to the default placeholder. "
                "Set a strong random secret in .env before running in production.",
        )
        raise SystemExit("FATAL: JWT_SECRET must be changed from the default value.")

    logger.info("starting_up", app=settings.APP_NAME)
    await init_redis()
    from app.graphs.resume_pipeline import init_checkpointer, close_checkpointer
    await init_checkpointer(settings.DATABASE_URL)
    yield
    logger.info("shutting_down", app=settings.APP_NAME)
    await close_checkpointer()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# State for slowapi
app.state.limiter = limiter

# Exception handlers
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware (order matters: last added = first executed)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers — imported here to avoid circular imports
from app.api.health import router as health_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.candidates import router as candidates_router  # noqa: E402
from app.api.companies import router as companies_router  # noqa: E402
from app.api.contacts import router as contacts_router  # noqa: E402
from app.api.outreach import router as outreach_router  # noqa: E402
from app.api.analytics import router as analytics_router  # noqa: E402
from app.api.webhooks import router as webhooks_router  # noqa: E402
from app.api.invites import router as invites_router  # noqa: E402
from app.api.admin import router as admin_router  # noqa: E402
from app.api.approvals import router as approvals_router  # noqa: E402
from app.api.ws import router as ws_router  # noqa: E402

app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(candidates_router, prefix=settings.API_V1_PREFIX)
app.include_router(companies_router, prefix=settings.API_V1_PREFIX)
app.include_router(contacts_router, prefix=settings.API_V1_PREFIX)
app.include_router(outreach_router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(webhooks_router, prefix=settings.API_V1_PREFIX)
app.include_router(invites_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(approvals_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router, prefix=settings.API_V1_PREFIX)
