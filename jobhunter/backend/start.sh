#!/bin/bash
set -e

# Use the venv directly (already built during Docker build)
export PATH="/app/.venv/bin:$PATH"

# Enable pgvector extension before running migrations
python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
async def create_ext():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    await engine.dispose()
asyncio.run(create_ext())
"

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
