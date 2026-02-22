FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --no-dev

# Copy and prepare startup script
COPY start.sh .
RUN chmod +x start.sh

# Create upload directory and non-root user
RUN mkdir -p /app/data/uploads && \
    adduser --disabled-password --no-create-home appuser && \
    chown -R appuser:appuser /app

ENV UV_NO_CACHE=1

USER appuser

EXPOSE 8000

CMD ["./start.sh"]
