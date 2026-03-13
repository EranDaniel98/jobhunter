"""Check environment setup: DB, Redis, required env vars."""
import asyncio
import sys

from app.config import settings


async def check():
    errors = []
    warnings = []

    # Check database
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        engine = create_async_engine(settings.DATABASE_URL)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        print("[OK] Database connection")
    except Exception as e:
        errors.append(f"[FAIL] Database: {e}")

    # Check Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
        print("[OK] Redis connection")
    except Exception as e:
        errors.append(f"[FAIL] Redis: {e}")

    # Check required env vars
    required = [
        ("JWT_SECRET", settings.JWT_SECRET != "change-me-to-a-random-secret-in-production"),
    ]
    for name, ok in required:
        if ok:
            print(f"[OK] {name} is set")
        else:
            warnings.append(f"[WARN] {name} is using default value")

    # Check API keys (optional in mock mode)
    if settings.USE_MOCK_APIS:
        print("[INFO] Running in MOCK mode - API keys not required")
    else:
        api_keys = [
            ("OPENAI_API_KEY", bool(settings.OPENAI_API_KEY)),
            ("HUNTER_API_KEY", bool(settings.HUNTER_API_KEY)),
            ("RESEND_API_KEY", bool(settings.RESEND_API_KEY)),
        ]
        for name, ok in api_keys:
            if ok:
                print(f"[OK] {name} is set")
            else:
                errors.append(f"[FAIL] {name} is not set (required in production mode)")

    # Summary
    print()
    for w in warnings:
        print(w)
    for e in errors:
        print(e)

    if errors:
        print(f"\n{len(errors)} error(s) found. Fix them before running.")
        sys.exit(1)
    else:
        print("\nAll checks passed!")


if __name__ == "__main__":
    asyncio.run(check())
