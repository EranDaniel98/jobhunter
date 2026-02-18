# ============================================================
# JobHunter AI — Windows Development Script
# Usage: .\dev.ps1 <command>
# ============================================================
param(
    [Parameter(Position=0)]
    [ValidateSet("setup", "dev", "migrate", "seed", "test", "test-cov", "check", "help")]
    [string]$Command = "help"
)

$BackendDir = Join-Path $PSScriptRoot "backend"

function Show-Help {
    Write-Host ""
    Write-Host "JobHunter AI — Development Commands" -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\dev.ps1 setup      Install dependencies (uv sync)"
    Write-Host "  .\dev.ps1 dev        Start the FastAPI dev server"
    Write-Host "  .\dev.ps1 migrate    Run database migrations"
    Write-Host "  .\dev.ps1 seed       Seed development data"
    Write-Host "  .\dev.ps1 test       Run tests"
    Write-Host "  .\dev.ps1 test-cov   Run tests with coverage"
    Write-Host "  .\dev.ps1 check      Verify environment setup"
    Write-Host ""
    Write-Host "Prerequisites:" -ForegroundColor Yellow
    Write-Host "  1. PostgreSQL with pgvector extension (port 5432)"
    Write-Host "  2. Redis (port 6379)"
    Write-Host "  3. Copy .env.example to .env and configure"
    Write-Host ""
}

switch ($Command) {
    "setup" {
        Write-Host "Installing dependencies..." -ForegroundColor Green
        if (-not (Test-Path (Join-Path $PSScriptRoot ".env"))) {
            Copy-Item (Join-Path $PSScriptRoot ".env.example") (Join-Path $PSScriptRoot ".env")
            Write-Host "Created .env from .env.example — edit it with your settings" -ForegroundColor Yellow
        }
        Push-Location $BackendDir
        uv sync --all-extras
        Pop-Location
        Write-Host "Setup complete!" -ForegroundColor Green
    }
    "dev" {
        Write-Host "Starting FastAPI dev server on http://localhost:8000" -ForegroundColor Green
        Write-Host "Swagger UI: http://localhost:8000/docs" -ForegroundColor Cyan
        Push-Location $BackendDir
        uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
        Pop-Location
    }
    "migrate" {
        Write-Host "Running database migrations..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run alembic upgrade head
        Pop-Location
    }
    "seed" {
        Write-Host "Seeding development data..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run python -m scripts.seed_dev_data
        Pop-Location
    }
    "test" {
        Write-Host "Running tests..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run pytest -v
        Pop-Location
    }
    "test-cov" {
        Write-Host "Running tests with coverage..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run coverage run -m pytest -v
        uv run coverage report -m
        Pop-Location
    }
    "check" {
        Write-Host "Checking environment..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run python -m scripts.check_env
        Pop-Location
    }
    "help" {
        Show-Help
    }
}
