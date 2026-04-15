#!/bin/bash
set -e

# Use the venv directly (already built during Docker build)
export PATH="/app/.venv/bin:$PATH"

PROCESS_TYPE="${PROCESS_TYPE:-api}"

if [ "$PROCESS_TYPE" = "api" ]; then
    # API service owns migrations. Worker waits for API to apply them first.
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
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
elif [ "$PROCESS_TYPE" = "worker" ]; then
    # ARQ worker: no migrations, no HTTP server. Expects DB schema to exist.
    exec arq app.worker.WorkerSettings
else
    echo "Unknown PROCESS_TYPE: $PROCESS_TYPE (expected 'api' or 'worker')" >&2
    exit 1
fi
