"""Seed load-test data: 2000 candidates, 50 companies, 500 jobs.

Refuses to run unless LOADTEST_MODE=True. Idempotent — safe to re-run; skips
creation if user0001@loadtest.local already exists.

Also writes tests/loadtest/fixtures/users.json for the k6 scenarios to read.

Usage:
    LOADTEST_MODE=1 python scripts/seed_loadtest_data.py
"""
import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.infrastructure.database import async_session_factory
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.utils.security import hash_password

N_USERS = 2000
N_COMPANIES = 50
N_JOBS = 500
PASSWORD = "LoadTest!1"
FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "loadtest"
    / "fixtures"
    / "users.json"
)


def _email(i: int) -> str:
    return f"user{i:04d}@loadtest.local"


async def seed() -> None:
    if not settings.LOADTEST_MODE:
        print("ERROR: LOADTEST_MODE is False. Refusing to seed.", file=sys.stderr)
        sys.exit(1)

    async with async_session_factory() as db:
        # Idempotency check
        existing = await db.execute(
            select(Candidate).where(Candidate.email == _email(1))
        )
        if existing.scalar_one_or_none() is not None:
            print("Seed data already exists (user0001@loadtest.local found). Skipping.")
            _write_fixture()
            return

        pw_hash = hash_password(PASSWORD)

        # Candidates
        print(f"Creating {N_USERS} candidates...")
        candidates: list[Candidate] = []
        for i in range(1, N_USERS + 1):
            c = Candidate(
                id=uuid.uuid4(),
                email=_email(i),
                password_hash=pw_hash,
                full_name=f"Load Test User {i:04d}",
                plan_tier="free",
                is_active=True,
                email_verified=True,
            )
            candidates.append(c)
            db.add(c)
            if i % 500 == 0:
                await db.flush()
                print(f"  flushed {i} candidates")
        await db.flush()

        # Companies (all under user0001 for simplicity; companies are per-candidate)
        owner = candidates[0]
        print(f"Creating {N_COMPANIES} companies under {owner.email}...")
        companies: list[Company] = []
        for i in range(N_COMPANIES):
            co = Company(
                id=uuid.uuid4(),
                candidate_id=owner.id,
                name=f"LoadTest Co {i:03d}",
                domain=f"lt-co-{i:03d}.local",
                industry="Software",
                size_range="51-200",
                status="approved",
                research_status="completed",
                source="manual",
            )
            companies.append(co)
            db.add(co)
        await db.flush()

        # Jobs distributed across companies
        print(f"Creating {N_JOBS} jobs...")
        for i in range(N_JOBS):
            co = companies[i % N_COMPANIES]
            job = JobPosting(
                id=uuid.uuid4(),
                candidate_id=owner.id,
                company_id=co.id,
                title=f"Load Test Role {i:04d}",
                company_name=co.name,
                url=f"https://{co.domain}/jobs/{i}",
                raw_text=f"Mock job posting {i} for load testing.",
                status="pending",
                application_stage="saved",
            )
            db.add(job)
            if i % 200 == 0 and i:
                await db.flush()

        await db.commit()
        print("Seed complete.")

    _write_fixture()


def _write_fixture() -> None:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = [{"email": _email(i), "password": PASSWORD} for i in range(1, N_USERS + 1)]
    FIXTURE_PATH.write_text(json.dumps(data, indent=2))
    print(f"Wrote {len(data)} users to {FIXTURE_PATH}")


if __name__ == "__main__":
    asyncio.run(seed())
