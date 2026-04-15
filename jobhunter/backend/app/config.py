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

    # Global daily OpenAI cost cap (in cents, default $50)
    DAILY_OPENAI_COST_LIMIT_CENTS: int = 5000

    # LLM model routing per pipeline (cost optimization)
    SCOUT_QUERIES_MODEL: str = "gpt-4o-mini"
    SCOUT_PARSE_MODEL: str = "gpt-4o-mini"
    ANALYTICS_INSIGHTS_MODEL: str = "gpt-4o-mini"

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
    MAX_DAILY_INVITES: int = 200

    # Stripe billing
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_EXPLORER: str = ""
    STRIPE_PRICE_HUNTER: str = ""

    # Multi-tenant RLS (SQLAlchemy ORM-level row filtering by candidate_id)
    ENABLE_RLS: bool = False  # Fixed to use Session-level listener; enable after admin bypass is validated

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Metrics
    METRICS_SECRET: str = ""

    # Sentry (leave empty to disable)
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # Database pool
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    PGBOUNCER_URL: str = ""

    # App
    APP_NAME: str = "JobHunter AI"
    API_V1_PREFIX: str = "/api/v1"

    # Cloudflare R2 (optional - falls back to local filesystem if not set)
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""

    # ARQ Batching
    ARQ_CHUNK_SIZE: int = 10
    ARQ_CHUNK_CONCURRENCY: int = 5
    ARQ_MAX_CHUNKS_PER_RUN: int = 50

    # TTLs (seconds)
    DOSSIER_CACHE_TTL: int = 604800  # 7 days
    REDIS_APPLY_ANALYSIS_TTL: int = 86400 * 7  # 7 days
    REDIS_WEBHOOK_DEDUP_TTL: int = 86400  # 24 hours
    REDIS_QUOTA_TTL: int = 86400  # 24 hours
    PENDING_ACTION_MAX_AGE_DAYS: int = 30

    # DNS Health
    DKIM_SELECTOR: str = "resend"
    SPF_EXPECTED_INCLUDES: list[str] = ["amazonses.com", "resend.com"]
    DNS_HEALTH_CACHE_TTL: int = 300
    DNS_LOOKUP_TIMEOUT: float = 3.0

    # Paths
    UPLOAD_DIR: str = str(BASE_DIR / "data" / "uploads")

    # Load testing
    LOADTEST_MODE: bool = False
    LOADTEST_AI_BUDGET: int = 0  # 0 = unlimited, >0 = hard cap on resume pipeline runs

    # GitHub (incident sync)
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = "EranDaniel98/jobhunter"

    model_config = {
        "env_file": [str(BASE_DIR / ".env"), str(BASE_DIR.parent / ".env")],
        "extra": "ignore",
    }


settings = Settings()
