# ============================================================
# JobHunter AI — Development Commands
# Works with: Docker (Linux/Mac) or local (Windows, see dev.ps1)
# ============================================================
.PHONY: setup dev test migrate seed clean

# --- Docker-based (if Docker available) ---
docker-dev:
	docker compose up --build

docker-stop:
	docker compose down

docker-migrate:
	docker compose exec backend uv run alembic upgrade head

docker-seed:
	docker compose exec backend uv run python -m scripts.seed_dev_data

docker-test:
	docker compose exec backend uv run pytest -v

docker-setup:
	cp -n .env.example .env 2>/dev/null || true
	docker compose up --build -d
	sleep 5
	docker compose exec backend uv run alembic upgrade head

docker-clean:
	docker compose down -v --remove-orphans

# --- Local development (Windows) ---
setup:
	cd backend && uv sync --all-extras

dev:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m scripts.seed_dev_data

test:
	cd backend && uv run pytest -v

test-cov:
	cd backend && uv run coverage run -m pytest -v
	cd backend && uv run coverage report -m

check:
	cd backend && uv run python -m scripts.check_env
