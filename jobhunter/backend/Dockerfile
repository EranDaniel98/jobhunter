# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

ENV UV_NO_CACHE=1

# Copy only dependency files first (maximises layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

# Copy application code and finalise install
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini start.sh ./
RUN uv sync --no-dev

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Minimal runtime system deps (curl for debugging; libpq for psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and upload directory
RUN adduser --disabled-password --no-create-home appuser && \
    mkdir -p /app/data/uploads && \
    chown -R appuser:appuser /app

# Copy virtualenv from builder (contains all installed packages)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --from=builder --chown=appuser:appuser /app/app /app/app
COPY --from=builder --chown=appuser:appuser /app/alembic /app/alembic
COPY --from=builder --chown=appuser:appuser /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=appuser:appuser /app/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Put the venv on PATH so python/uvicorn/alembic are found
ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/api/v1/health')" || exit 1

USER appuser

EXPOSE 8000

CMD ["./start.sh"]
