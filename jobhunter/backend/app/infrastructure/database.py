import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.middleware.tenant import install_rls_listener

logger = structlog.get_logger()

# NOTE: When using pgBouncer in transaction mode, do NOT use session.begin_nested()
# or SAVEPOINTs — they are not supported through transaction-mode pgBouncer.


def _get_engine_config() -> dict:
    """Determine engine URL and pool settings based on PGBOUNCER_URL."""
    if settings.PGBOUNCER_URL:
        return {
            "url": settings.PGBOUNCER_URL,
            "pool_size": 5,
            "max_overflow": 5,
            "mode": "pgbouncer",
        }
    return {
        "url": settings.DATABASE_URL,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "mode": "direct",
    }


_config = _get_engine_config()

engine = create_async_engine(
    _config["url"],
    pool_size=_config["pool_size"],
    max_overflow=_config["max_overflow"],
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
)

logger.info("database.pool_mode", extra={
    "feature": "pgbouncer",
    "detail": {"mode": _config["mode"], "pool_size": _config["pool_size"], "max_overflow": _config["max_overflow"]},
})

# Install RLS listener if enabled (must be done before sessions are created)
install_rls_listener(engine)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        yield session
