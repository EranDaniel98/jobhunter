# ============================================================
# JobHunter AI - Windows Development Script
# Usage: .\dev.ps1 <command>
# ============================================================
param(
    [Parameter(Position=0)]
    [ValidateSet("setup", "start", "stop", "dev", "migrate", "seed", "test", "test-cov", "lint", "format", "check", "logs", "help")]
    [string]$Command = "help"
)

$BackendDir = Join-Path $PSScriptRoot "backend"
$FrontendDir = Join-Path $PSScriptRoot "frontend"
$ComposeFile = Join-Path $PSScriptRoot "docker-compose.yml"

function Stop-Servers {
    Get-CimInstance Win32_Process 2>$null |
        Where-Object { $_.CommandLine -match 'jobhunter' -and $_.Name -match 'python|node' } |
        ForEach-Object {
            Write-Host "  Stopping $($_.Name) PID $($_.ProcessId)" -ForegroundColor Yellow
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Ensure-Docker {
    $docker = docker compose -f $ComposeFile ps --status running 2>$null
    if ($docker -notmatch 'postgres') {
        Write-Host "Starting Docker services (postgres + redis)..." -ForegroundColor Cyan
        docker compose -f $ComposeFile up -d postgres redis
        Start-Sleep -Seconds 3
    } else {
        Write-Host "Docker services already running." -ForegroundColor Gray
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "JobHunter AI - Development Commands" -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\dev.ps1 setup      Install backend + frontend dependencies"
    Write-Host "  .\dev.ps1 start      Start Docker, backend, and frontend" -ForegroundColor White
    Write-Host "  .\dev.ps1 stop       Stop everything (servers + Docker)"
    Write-Host "  .\dev.ps1 dev        Start FastAPI dev server only (+ Docker)"
    Write-Host "  .\dev.ps1 migrate    Run database migrations (via Docker)"
    Write-Host "  .\dev.ps1 seed       Seed development data"
    Write-Host "  .\dev.ps1 test       Run tests"
    Write-Host "  .\dev.ps1 test-cov   Run tests with coverage (85% threshold)"
    Write-Host "  .\dev.ps1 lint       Run Ruff linter + format check"
    Write-Host "  .\dev.ps1 format     Auto-format code with Ruff"
    Write-Host "  .\dev.ps1 check      Verify environment setup"
    Write-Host "  .\dev.ps1 logs       Tail Docker service logs"
    Write-Host ""
    Write-Host "Prerequisites:" -ForegroundColor Yellow
    Write-Host "  1. Docker Desktop running"
    Write-Host "  2. Copy .env.example to .env and configure"
    Write-Host ""
}

switch ($Command) {
    "start" {
        Ensure-Docker

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
            [Console]::TreatControlCAsInput = $true
            while ($true) {
                # Check for Ctrl+C
                if ([Console]::KeyAvailable) {
                    $key = [Console]::ReadKey($true)
                    if ($key.Modifiers -band [ConsoleModifiers]::Control -and $key.Key -eq 'C') {
                        break
                    }
                }
                if ($backend.HasExited) {
                    Write-Host "Backend exited with code $($backend.ExitCode)" -ForegroundColor Red
                    break
                }
                if ($frontend.HasExited) {
                    Write-Host "Frontend exited with code $($frontend.ExitCode)" -ForegroundColor Red
                    break
                }
                Start-Sleep -Milliseconds 500
            }
        } finally {
            [Console]::TreatControlCAsInput = $false
            Write-Host "`nShutting down..." -ForegroundColor Yellow
            # Kill process trees to ensure Node/Next.js child processes are stopped
            foreach ($proc in @($backend, $frontend)) {
                if ($proc -and -not $proc.HasExited) {
                    try {
                        $procId = $proc.Id
                        # Kill entire process tree
                        taskkill /PID $procId /T /F 2>$null | Out-Null
                    } catch {}
                }
            }
            Stop-Servers
        }
    }
    "stop" {
        Write-Host "Stopping servers..." -ForegroundColor Yellow
        Stop-Servers
        Write-Host "Stopping Docker services..." -ForegroundColor Yellow
        docker compose -f $ComposeFile down
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

        Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
        Push-Location $BackendDir
        uv sync --all-extras
        Pop-Location

        Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
        Push-Location $FrontendDir
        npm install
        Pop-Location

        Write-Host "Setup complete!" -ForegroundColor Green
    }
    "dev" {
        Ensure-Docker
        Write-Host "Starting FastAPI dev server on http://localhost:8000" -ForegroundColor Green
        Write-Host "Swagger UI: http://localhost:8000/docs" -ForegroundColor Cyan
        Push-Location $BackendDir
        uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
        Pop-Location
    }
    "migrate" {
        Ensure-Docker
        Write-Host "Running database migrations..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run alembic upgrade head
        Pop-Location
    }
    "seed" {
        Ensure-Docker
        Write-Host "Seeding development data..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run python -m scripts.seed_dev_data
        Pop-Location
    }
    "test" {
        Ensure-Docker
        Write-Host "Running tests..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run pytest -v
        Pop-Location
    }
    "test-cov" {
        Ensure-Docker
        Write-Host "Running tests with coverage..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run pytest -v --cov=app --cov-report=term-missing --cov-fail-under=85
        Pop-Location
    }
    "lint" {
        Write-Host "Running linter..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run ruff check app/
        uv run ruff format --check app/
        Pop-Location
    }
    "format" {
        Write-Host "Formatting code..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run ruff format app/
        uv run ruff check --fix app/
        Pop-Location
    }
    "check" {
        Write-Host "Checking environment..." -ForegroundColor Green
        Push-Location $BackendDir
        uv run python -m scripts.check_env
        Pop-Location
    }
    "logs" {
        docker compose -f $ComposeFile logs -f postgres redis
    }
    "help" {
        Show-Help
    }
}
