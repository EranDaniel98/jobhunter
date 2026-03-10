from pathlib import Path

from pydantic_settings import BaseSettings

# Project root = backend/ directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://jobhunter:jobhunter@localhost:5432/jobhunter"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "change-me-to-a-random-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 1440  # 24 hours
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # API Keys
    OPENAI_API_KEY: str = ""
    HUNTER_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    NEWSAPI_KEY: str = ""

    # Resend webhook
    RESEND_WEBHOOK_SECRET: str = ""

    # Unsubscribe link signing
    UNSUBSCRIBE_SECRET: str = ""

    # API cost limits (daily per user)
    DAILY_OPENAI_CALL_LIMIT: int = 100
    DAILY_HUNTER_CALL_LIMIT: int = 50
    DAILY_DISCOVERY_LIMIT: int = 10
    DAILY_RESEARCH_LIMIT: int = 5

    # Email
    DAILY_EMAIL_LIMIT: int = 50
    SENDER_EMAIL: str = "outreach@hunter-job.com"
    SENDER_NAME: str = "Eran"
    PHYSICAL_ADDRESS: str = "Tel Aviv, Israel"

    # Invites
    INVITE_EXPIRE_DAYS: int = 7

    # Stripe billing
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_EXPLORER: str = ""
    STRIPE_PRICE_HUNTER: str = ""

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Sentry (leave empty to disable)
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # Database pool
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # App
    APP_NAME: str = "JobHunter AI"
    API_V1_PREFIX: str = "/api/v1"

    # Cloudflare R2 (optional — falls back to local filesystem if not set)
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""

    # TTLs (seconds)
    REDIS_APPLY_ANALYSIS_TTL: int = 86400 * 7   # 7 days
    REDIS_WEBHOOK_DEDUP_TTL: int = 86400         # 24 hours
    REDIS_QUOTA_TTL: int = 86400                 # 24 hours
    PENDING_ACTION_MAX_AGE_DAYS: int = 30

    # Paths
    UPLOAD_DIR: str = str(BASE_DIR / "data" / "uploads")

    model_config = {
        "env_file": [str(BASE_DIR / ".env"), str(BASE_DIR.parent / ".env")],
        "extra": "ignore",
    }


settings = Settings()
