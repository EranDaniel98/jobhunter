#!/bin/bash
set -e

# Enable pgvector extension before running migrations
uv run python -c "
import asyncio, sqlalchemy
from app.config import settings
async def create_ext():
    engine = sqlalchemy.ext.asyncio.create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text('CREATE EXTENSION IF NOT EXISTS vector'))
    await engine.dispose()
asyncio.run(create_ext())
"

uv run alembic upgrade head
exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
