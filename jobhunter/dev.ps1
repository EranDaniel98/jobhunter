# ============================================================
# JobHunter AI - Windows Development Script
# Usage: .\dev.ps1 <command>
# ============================================================
param(
    [Parameter(Position=0)]
    [ValidateSet("setup", "start", "stop", "dev", "migrate", "seed", "test", "test-cov", "check", "help")]
    [string]$Command = "help"
)

$BackendDir = Join-Path $PSScriptRoot "backend"
$FrontendDir = Join-Path $PSScriptRoot "frontend"

function Stop-Servers {
    Get-CimInstance Win32_Process 2>$null |
        Where-Object { $_.CommandLine -match 'jobhunter' -and $_.Name -match 'python|node' } |
        ForEach-Object {
            Write-Host "  Stopping $($_.Name) PID $($_.ProcessId)" -ForegroundColor Yellow
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Show-Help {
    Write-Host ""
    Write-Host "JobHunter AI - Development Commands" -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\dev.ps1 setup      Install dependencies"
    Write-Host "  .\dev.ps1 start      Start backend + frontend + Docker" -ForegroundColor White
    Write-Host "  .\dev.ps1 stop       Stop backend + frontend"
    Write-Host "  .\dev.ps1 dev        Start the FastAPI dev server only"
    Write-Host "  .\dev.ps1 migrate    Run database migrations"
    Write-Host "  .\dev.ps1 seed       Seed development data"
    Write-Host "  .\dev.ps1 test       Run tests"
    Write-Host "  .\dev.ps1 test-cov   Run tests with coverage"
    Write-Host "  .\dev.ps1 check      Verify environment setup"
    Write-Host ""
    Write-Host "Prerequisites:" -ForegroundColor Yellow
    Write-Host "  1. PostgreSQL with pgvector extension on port 5432"
    Write-Host "  2. Redis on port 6379"
    Write-Host "  3. Copy .env.example to .env and configure"
    Write-Host ""
}

switch ($Command) {
    "start" {
        $composeFile = Join-Path $PSScriptRoot "docker-compose.yml"
        $docker = docker compose -f $composeFile ps --status running 2>$null
        if ($docker -notmatch 'postgres') {
            Write-Host "Starting Docker services..." -ForegroundColor Cyan
            docker compose -f $composeFile up -d
            Start-Sleep -Seconds 3
        } else {
            Write-Host "Docker services already running." -ForegroundColor Gray
        }

        Write-Host "Stopping existing servers..." -ForegroundColor Yellow
        Stop-Servers
        Start-Sleep -Seconds 1

        Write-Host "Starting backend on :8000..." -ForegroundColor Cyan
        $pyExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
        $backendArgs = @{
            FilePath = $pyExe
            ArgumentList = @("-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000")
            WorkingDirectory = $BackendDir
            PassThru = $true
            NoNewWindow = $true
        }
        $backend = Start-Process @backendArgs

        Write-Host "Starting frontend on :3000..." -ForegroundColor Cyan
        $frontendArgs = @{
            FilePath = "npx"
            ArgumentList = @("next", "dev")
            WorkingDirectory = $FrontendDir
            PassThru = $true
            NoNewWindow = $true
        }
        $frontend = Start-Process @frontendArgs

        Write-Host ""
        Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
        Write-Host "Swagger:  http://localhost:8000/docs" -ForegroundColor Green
        Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
        Write-Host "Press Ctrl+C to stop all..." -ForegroundColor Gray
        Write-Host ""

        try {
            while ($true) {
                if ($backend.HasExited) {
                    Write-Host "Backend exited with code $($backend.ExitCode)" -ForegroundColor Red
                    break
                }
                if ($frontend.HasExited) {
                    Write-Host "Frontend exited with code $($frontend.ExitCode)" -ForegroundColor Red
                    break
                }
                Start-Sleep -Seconds 2
            }
        } finally {
            Write-Host "`nShutting down..." -ForegroundColor Yellow
            Stop-Servers
        }
    }
    "stop" {
        Write-Host "Stopping servers..." -ForegroundColor Yellow
        Stop-Servers
        Write-Host "Done." -ForegroundColor Green
    }
    "setup" {
        Write-Host "Installing dependencies..." -ForegroundColor Green
        $envFile = Join-Path $PSScriptRoot ".env"
        $envExample = Join-Path $PSScriptRoot ".env.example"
        if (-not (Test-Path $envFile)) {
            Copy-Item $envExample $envFile
            Write-Host "Created .env from .env.example - edit it with your settings" -ForegroundColor Yellow
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
