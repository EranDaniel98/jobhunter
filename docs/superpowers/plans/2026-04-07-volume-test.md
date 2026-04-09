# Volume Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a Railway `staging-loadtest` environment that mirrors production, run a k6 ramp test to 1200 concurrent users against it with Hunter/Resend mocked and OpenAI hard-capped at 200 runs, and produce a capacity report — all within a $70 budget.

**Architecture:** A `LOADTEST_MODE` flag in the backend swaps real Hunter/Resend clients for in-process mocks and gates the resume pipeline behind a Redis-backed 200-run counter. k6 scripts run from a one-shot Hetzner VM against the staging URL, executing a weighted scenario mix (80% browse / 15% onboard / 5% outreach). Shell scripts orchestrate bring-up → seed → run → collect → teardown with unconditional cleanup on exit.

**Tech Stack:** k6, Railway CLI, Hetzner Cloud CLI (`hcloud`), Python/FastAPI backend, Redis, Postgres+pgvector, bash.

**Spec:** `docs/superpowers/specs/2026-04-06-volume-test-design.md`

---

## File Structure

### New files — backend
- `jobhunter/backend/app/infrastructure/mock_hunter_client.py` — in-process Hunter mock, returns canned fixtures with 200ms sleep
- `jobhunter/backend/app/infrastructure/mock_resend_client.py` — in-process Resend mock, no network
- `jobhunter/backend/app/loadtest_guard.py` — `enforce_ai_budget()` helper using Redis INCR against `loadtest:ai_runs`
- `jobhunter/backend/tests/test_loadtest_guard.py` — unit tests for the budget guard

### New files — k6 scripts
- `jobhunter/backend/tests/loadtest/main.js` — ramp stages, weighted scenario picker, env config
- `jobhunter/backend/tests/loadtest/scenario-browse.js`
- `jobhunter/backend/tests/loadtest/scenario-onboard.js`
- `jobhunter/backend/tests/loadtest/scenario-outreach.js`
- `jobhunter/backend/tests/loadtest/lib/auth.js` — login helper, token cache
- `jobhunter/backend/tests/loadtest/fixtures/users.json` — generated list of 2000 seeded credentials
- `jobhunter/backend/tests/loadtest/fixtures/sample-resume.pdf` — 1-page PDF used by onboarding scenario

### New files — seed script
- `jobhunter/backend/scripts/seed_loadtest_data.py` — creates 2000 candidates, 500 jobs, 50 companies, writes `users.json`

### New files — orchestration scripts
- `scripts/loadtest/bring-up-staging.sh`
- `scripts/loadtest/provision-runner.sh`
- `scripts/loadtest/run-test.sh`
- `scripts/loadtest/collect-artifacts.sh`
- `scripts/loadtest/teardown-staging.sh`
- `scripts/loadtest/lib.sh` — shared helpers (logging, cost gate, trap setup)

### Modified files
- `jobhunter/backend/app/config.py` — add `LOADTEST_MODE: bool = False`, `LOADTEST_AI_BUDGET: int = 0`
- `jobhunter/backend/app/dependencies.py:57` (`get_hunter`) — return mock when `LOADTEST_MODE`
- `jobhunter/backend/app/dependencies.py:75` (`get_email_client`) — return mock when `LOADTEST_MODE`
- `jobhunter/backend/app/graphs/resume_pipeline.py` — call `enforce_ai_budget()` at pipeline entry
- `jobhunter/backend/pyproject.toml` — no new deps expected (verify)

### Results output
- `docs/superpowers/loadtest-results/2026-04-07/report.md`
- `docs/superpowers/loadtest-results/2026-04-07/k6-summary.json`
- `docs/superpowers/loadtest-results/2026-04-07/railway-logs.txt`
- `docs/superpowers/loadtest-results/2026-04-07/pg-slow.log`

---

## Task 1: Config flags

**Files:**
- Modify: `jobhunter/backend/app/config.py`

- [ ] **Step 1: Add the two settings**

Add to the Settings class:

```python
    LOADTEST_MODE: bool = False
    LOADTEST_AI_BUDGET: int = 0  # 0 = unlimited, >0 = hard cap on resume pipeline runs
```

- [ ] **Step 2: Verify the app still boots**

Run: `cd jobhunter/backend && python -c "from app.config import settings; print(settings.LOADTEST_MODE, settings.LOADTEST_AI_BUDGET)"`
Expected: `False 0`

- [ ] **Step 3: Commit**

```bash
git add jobhunter/backend/app/config.py
git commit -m "feat(loadtest): add LOADTEST_MODE and LOADTEST_AI_BUDGET settings"
```

---

## Task 2: AI budget guard (TDD)

**Files:**
- Create: `jobhunter/backend/app/loadtest_guard.py`
- Create: `jobhunter/backend/tests/test_loadtest_guard.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_loadtest_guard.py
import pytest
from unittest.mock import AsyncMock
from app.loadtest_guard import enforce_ai_budget, AIBudgetExceeded


@pytest.mark.asyncio
async def test_allows_when_disabled():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    # budget=0 means disabled, should never call redis or raise
    await enforce_ai_budget(redis, budget=0)
    redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_allows_under_budget():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=5)
    await enforce_ai_budget(redis, budget=200)
    redis.incr.assert_awaited_once_with("loadtest:ai_runs")


@pytest.mark.asyncio
async def test_raises_over_budget():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=201)
    with pytest.raises(AIBudgetExceeded):
        await enforce_ai_budget(redis, budget=200)


@pytest.mark.asyncio
async def test_raises_at_boundary_plus_one():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=200)
    # 200th run still allowed
    await enforce_ai_budget(redis, budget=200)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd jobhunter/backend && pytest tests/test_loadtest_guard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.loadtest_guard'`

- [ ] **Step 3: Implement the guard**

```python
# app/loadtest_guard.py
"""Load-test safety guard: hard cap on expensive AI pipeline runs.

Used only when LOADTEST_MODE=1 and LOADTEST_AI_BUDGET>0. In production these
settings are 0/False and this module is a no-op.
"""
from redis.asyncio import Redis


class AIBudgetExceeded(Exception):
    """Raised when the load-test AI run budget has been exhausted."""


AI_RUNS_KEY = "loadtest:ai_runs"


async def enforce_ai_budget(redis: Redis, budget: int) -> None:
    """Atomically increment the AI run counter and raise if over budget.

    budget=0 disables the check entirely (production default).
    """
    if budget <= 0:
        return
    count = await redis.incr(AI_RUNS_KEY)
    if count > budget:
        raise AIBudgetExceeded(
            f"Load-test AI budget exhausted: {count} > {budget}"
        )
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `cd jobhunter/backend && pytest tests/test_loadtest_guard.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add jobhunter/backend/app/loadtest_guard.py jobhunter/backend/tests/test_loadtest_guard.py
git commit -m "feat(loadtest): add Redis-backed AI budget guard"
```

---

## Task 3: Wire guard into resume pipeline

**Files:**
- Modify: `jobhunter/backend/app/graphs/resume_pipeline.py`

- [ ] **Step 1: Read the pipeline entry point to find the right insertion site**

Read the top-level `run_resume_pipeline()` (or equivalent entry function). The guard must run *before* any OpenAI call, *after* we have a Redis handle.

- [ ] **Step 2: Add the guard call**

At the start of the pipeline entry function, after acquiring `redis`:

```python
from app.config import settings
from app.loadtest_guard import enforce_ai_budget, AIBudgetExceeded

# ... inside the entry function, before any LLM call ...
if settings.LOADTEST_MODE:
    try:
        await enforce_ai_budget(redis, settings.LOADTEST_AI_BUDGET)
    except AIBudgetExceeded as e:
        logger.warning("loadtest.ai_budget_exceeded", error=str(e))
        # Short-circuit: mark the candidate's resume as "skipped" and return
        await _mark_resume_skipped(candidate_id, reason="loadtest_budget")
        return
```

Where `_mark_resume_skipped` updates the candidate's resume row `status='skipped'` so the polling k6 scenario sees a terminal state and stops waiting. If a similar helper already exists, reuse it; otherwise add a small one in the same module.

- [ ] **Step 3: Smoke test locally with LOADTEST_MODE off**

Run: `cd jobhunter/backend && pytest tests/ -k resume_pipeline -v`
Expected: existing tests still pass (guard is inert when `LOADTEST_MODE=False`)

- [ ] **Step 4: Commit**

```bash
git add jobhunter/backend/app/graphs/resume_pipeline.py
git commit -m "feat(loadtest): gate resume pipeline on AI budget in loadtest mode"
```

---

## Task 4: Mock Hunter client

**Files:**
- Create: `jobhunter/backend/app/infrastructure/mock_hunter_client.py`

- [ ] **Step 1: Inspect the protocol**

Read `jobhunter/backend/app/infrastructure/protocols.py` and find `HunterClientProtocol`. Note every method signature — the mock must implement all of them.

- [ ] **Step 2: Write the mock**

```python
# app/infrastructure/mock_hunter_client.py
"""In-process Hunter.io mock for load testing.

Returns deterministic canned data with ~200ms simulated latency so that
the load test measures our own system, not Hunter's throughput.
"""
import asyncio
from app.infrastructure.protocols import HunterClientProtocol

_LATENCY_S = 0.2


class MockHunterClient(HunterClientProtocol):
    async def domain_search(self, domain: str, limit: int = 10) -> dict:
        await asyncio.sleep(_LATENCY_S)
        return {
            "domain": domain,
            "emails": [
                {
                    "value": f"person{i}@{domain}",
                    "first_name": f"First{i}",
                    "last_name": f"Last{i}",
                    "position": "Engineering Manager",
                    "confidence": 90,
                }
                for i in range(min(limit, 5))
            ],
        }

    async def email_finder(self, domain: str, first_name: str, last_name: str) -> dict:
        await asyncio.sleep(_LATENCY_S)
        return {
            "email": f"{first_name.lower()}.{last_name.lower()}@{domain}",
            "confidence": 85,
        }

    async def email_verifier(self, email: str) -> dict:
        await asyncio.sleep(_LATENCY_S)
        return {"email": email, "result": "deliverable", "score": 90}

    async def aclose(self) -> None:
        return None
```

Adjust method names/signatures to match the actual protocol after reading it in Step 1. If the protocol has additional methods, add stub implementations that return plausible shapes.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/backend/app/infrastructure/mock_hunter_client.py
git commit -m "feat(loadtest): add in-process Hunter.io mock client"
```

---

## Task 5: Mock Resend client

**Files:**
- Create: `jobhunter/backend/app/infrastructure/mock_resend_client.py`

- [ ] **Step 1: Inspect the protocol**

Read `EmailClientProtocol` in `app/infrastructure/protocols.py`. Note every method signature.

- [ ] **Step 2: Write the mock**

```python
# app/infrastructure/mock_resend_client.py
"""In-process Resend mock for load testing. Swallows all sends."""
import uuid
from app.infrastructure.protocols import EmailClientProtocol


class MockResendClient(EmailClientProtocol):
    async def send_email(
        self,
        to: str,
        subject: str,
        text: str,
        from_email: str | None = None,
        reply_to: str | None = None,
    ) -> dict:
        return {"id": f"mock-{uuid.uuid4()}", "to": to, "subject": subject}

    async def aclose(self) -> None:
        return None
```

Match the actual protocol signatures exactly.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/backend/app/infrastructure/mock_resend_client.py
git commit -m "feat(loadtest): add in-process Resend mock client"
```

---

## Task 6: Swap clients in DI when LOADTEST_MODE

**Files:**
- Modify: `jobhunter/backend/app/dependencies.py:57` (`get_hunter`)
- Modify: `jobhunter/backend/app/dependencies.py:75` (`get_email_client`)

- [ ] **Step 1: Update `get_hunter`**

```python
def get_hunter() -> HunterClientProtocol:
    global _hunter_client
    if _hunter_client is None:
        from app.config import settings
        if settings.LOADTEST_MODE:
            from app.infrastructure.mock_hunter_client import MockHunterClient
            _hunter_client = MockHunterClient()
        else:
            from app.infrastructure.hunter_client import HunterClient
            _hunter_client = HunterClient()
    return _hunter_client
```

- [ ] **Step 2: Update `get_email_client`**

```python
def get_email_client() -> EmailClientProtocol:
    global _email_client
    if _email_client is None:
        from app.config import settings
        if settings.LOADTEST_MODE:
            from app.infrastructure.mock_resend_client import MockResendClient
            _email_client = MockResendClient()
        else:
            from app.infrastructure.resend_client import ResendClient
            _email_client = ResendClient()
    return _email_client
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `cd jobhunter/backend && pytest tests/ -x -q`
Expected: all green

- [ ] **Step 4: Commit**

```bash
git add jobhunter/backend/app/dependencies.py
git commit -m "feat(loadtest): swap Hunter/Resend for mocks when LOADTEST_MODE"
```

---

## Task 7: Load-test seed script

**Files:**
- Create: `jobhunter/backend/scripts/seed_loadtest_data.py`

- [ ] **Step 1: Write the seed script**

```python
# scripts/seed_loadtest_data.py
"""Seed a staging-loadtest Railway environment.

Creates:
  - 2000 free-tier candidates with credentials user0001..user2000 / LoadTest!1
  - 500 fake jobs across 50 fake companies
  - Writes credentials to tests/loadtest/fixtures/users.json for k6 to read

REFUSES to run unless settings.LOADTEST_MODE is True, to prevent polluting prod.
"""
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select
from app.config import settings
from app.db import get_session_maker  # adjust import to match repo
from app.models import Candidate, Company, Job
from app.auth import hash_password  # adjust import to match repo

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "loadtest" / "fixtures" / "users.json"
PASSWORD = "LoadTest!1"
N_CANDIDATES = 2000
N_COMPANIES = 50
N_JOBS = 500


async def main() -> None:
    if not settings.LOADTEST_MODE:
        sys.exit("REFUSING: LOADTEST_MODE is False. This script must only run against staging-loadtest.")

    session_maker = get_session_maker()
    async with session_maker() as db:
        # Idempotent: if already seeded, exit
        existing = (await db.execute(select(Candidate).where(Candidate.email == "user0001@loadtest.local"))).scalar_one_or_none()
        if existing:
            print("already seeded")
        else:
            await _seed_candidates(db)
            await _seed_companies_and_jobs(db)
            await db.commit()

        users = [{"email": f"user{i:04d}@loadtest.local", "password": PASSWORD} for i in range(1, N_CANDIDATES + 1)]
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(json.dumps(users))
        print(f"wrote {len(users)} users to {FIXTURE_PATH}")


async def _seed_candidates(db) -> None:
    pw_hash = hash_password(PASSWORD)
    for i in range(1, N_CANDIDATES + 1):
        db.add(Candidate(
            email=f"user{i:04d}@loadtest.local",
            password_hash=pw_hash,
            tier="free",
            is_active=True,
        ))
        if i % 500 == 0:
            await db.flush()


async def _seed_companies_and_jobs(db) -> None:
    companies = []
    for i in range(1, N_COMPANIES + 1):
        c = Company(name=f"LoadCo {i}", domain=f"loadco{i}.local")
        db.add(c)
        companies.append(c)
    await db.flush()
    for j in range(1, N_JOBS + 1):
        company = companies[j % N_COMPANIES]
        db.add(Job(
            title=f"Engineer {j}",
            company_id=company.id,
            description=f"Placeholder job description {j}",
            location="Remote",
        ))


if __name__ == "__main__":
    asyncio.run(main())
```

**Note to implementer:** Before running, open `app/models/` and adjust field names to match the real schema (e.g. `Candidate` may require `first_name`, `last_name`; `Job` may require `source`, `url`, `posted_at`). The structure of the script stays the same — only column names need alignment.

- [ ] **Step 2: Dry-run check locally (without executing)**

Run: `cd jobhunter/backend && python -c "import ast; ast.parse(open('scripts/seed_loadtest_data.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add jobhunter/backend/scripts/seed_loadtest_data.py
git commit -m "feat(loadtest): add staging seed script for 2000 users + 500 jobs"
```

---

## Task 8: k6 auth helper

**Files:**
- Create: `jobhunter/backend/tests/loadtest/lib/auth.js`

- [ ] **Step 1: Write the helper**

```javascript
// tests/loadtest/lib/auth.js
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL;

export function login(email, password) {
  const res = http.post(`${BASE}/api/v1/auth/login`, JSON.stringify({ email, password }), {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'login' },
  });
  check(res, { 'login 200': (r) => r.status === 200 });
  return res.json('access_token');
}

export function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } };
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/backend/tests/loadtest/lib/auth.js
git commit -m "feat(loadtest): add k6 auth helper"
```

---

## Task 9: k6 browse scenario

**Files:**
- Create: `jobhunter/backend/tests/loadtest/scenario-browse.js`

- [ ] **Step 1: Write the scenario**

```javascript
// tests/loadtest/scenario-browse.js
import http from 'k6/http';
import { sleep, check } from 'k6';
import { login, authHeaders } from './lib/auth.js';

const BASE = __ENV.BASE_URL;

export function browse(user) {
  const token = login(user.email, user.password);
  if (!token) return;
  const h = authHeaders(token);

  const dash = http.get(`${BASE}/api/v1/dashboard`, { ...h, tags: { endpoint: 'dashboard' } });
  check(dash, { 'dashboard 200': (r) => r.status === 200 });

  const jobs = http.get(`${BASE}/api/v1/jobs?limit=20`, { ...h, tags: { endpoint: 'jobs_list' } });
  check(jobs, { 'jobs 200': (r) => r.status === 200 });

  const first = jobs.json('items.0.id');
  if (first) {
    const one = http.get(`${BASE}/api/v1/jobs/${first}`, { ...h, tags: { endpoint: 'job_detail' } });
    check(one, { 'job 200': (r) => r.status === 200 });
  }

  const resume = http.get(`${BASE}/api/v1/resume`, { ...h, tags: { endpoint: 'resume_get' } });
  check(resume, { 'resume 200 or 404': (r) => r.status === 200 || r.status === 404 });

  sleep(2 + Math.random() * 3);
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/backend/tests/loadtest/scenario-browse.js
git commit -m "feat(loadtest): add k6 browsing scenario"
```

---

## Task 10: k6 onboarding scenario

**Files:**
- Create: `jobhunter/backend/tests/loadtest/scenario-onboard.js`

- [ ] **Step 1: Write the scenario**

```javascript
// tests/loadtest/scenario-onboard.js
import http from 'k6/http';
import { sleep, check } from 'k6';
import { Counter } from 'k6/metrics';
import { login, authHeaders } from './lib/auth.js';

const BASE = __ENV.BASE_URL;
const ONBOARD_CAP = parseInt(__ENV.ONBOARD_CAP || '200', 10);
const RESUME_PDF = open('./fixtures/sample-resume.pdf', 'b');

export const onboardStarted = new Counter('loadtest_onboard_started');
export const onboardSkipped = new Counter('loadtest_onboard_skipped_cap');

// Global counter shared across VUs via k6's __VU/__ITER and a simple in-memory
// counter object exported from main.js. See main.js for the coordinator.
import { tryClaimOnboardSlot } from './main.js';

export function onboard(user, runBrowseFallback) {
  if (!tryClaimOnboardSlot(ONBOARD_CAP)) {
    onboardSkipped.add(1);
    runBrowseFallback(user);
    return;
  }
  onboardStarted.add(1);

  // Register a fresh user derived from the pool user's index so we don't collide
  const email = `onboard-${__VU}-${__ITER}-${Date.now()}@loadtest.local`;
  const reg = http.post(
    `${BASE}/api/v1/auth/register`,
    JSON.stringify({ email, password: 'LoadTest!1' }),
    { headers: { 'Content-Type': 'application/json' }, tags: { endpoint: 'register' } },
  );
  check(reg, { 'register 201': (r) => r.status === 201 });
  if (reg.status !== 201) return;

  const token = reg.json('access_token') || login(email, 'LoadTest!1');
  const h = authHeaders(token);

  const upload = http.post(
    `${BASE}/api/v1/resume/upload`,
    { file: http.file(RESUME_PDF, 'resume.pdf', 'application/pdf') },
    { headers: { Authorization: `Bearer ${token}` }, tags: { endpoint: 'resume_upload' } },
  );
  check(upload, { 'upload 2xx': (r) => r.status >= 200 && r.status < 300 });

  // Poll up to 60s for terminal state
  for (let i = 0; i < 30; i++) {
    sleep(2);
    const r = http.get(`${BASE}/api/v1/resume`, { ...h, tags: { endpoint: 'resume_poll' } });
    const status = r.json('status');
    if (status === 'complete' || status === 'failed' || status === 'skipped') break;
  }

  http.get(`${BASE}/api/v1/dashboard`, { ...h, tags: { endpoint: 'dashboard' } });
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/backend/tests/loadtest/scenario-onboard.js
git commit -m "feat(loadtest): add k6 onboarding scenario with hard cap"
```

---

## Task 11: k6 outreach scenario

**Files:**
- Create: `jobhunter/backend/tests/loadtest/scenario-outreach.js`

- [ ] **Step 1: Write the scenario**

```javascript
// tests/loadtest/scenario-outreach.js
import http from 'k6/http';
import { check } from 'k6';
import { login, authHeaders } from './lib/auth.js';

const BASE = __ENV.BASE_URL;

export function outreach(user) {
  const token = login(user.email, user.password);
  if (!token) return;
  const h = authHeaders(token);

  const companies = http.get(`${BASE}/api/v1/companies?limit=5`, { ...h, tags: { endpoint: 'companies_list' } });
  check(companies, { 'companies 200': (r) => r.status === 200 });
  const companyId = companies.json('items.0.id');
  if (!companyId) return;

  const dossier = http.get(`${BASE}/api/v1/companies/${companyId}/dossier`, { ...h, tags: { endpoint: 'dossier' } });
  check(dossier, { 'dossier 2xx': (r) => r.status >= 200 && r.status < 300 });

  const draft = http.post(
    `${BASE}/api/v1/outreach/draft`,
    JSON.stringify({ company_id: companyId }),
    { ...h, tags: { endpoint: 'outreach_draft' } },
  );
  check(draft, { 'draft 2xx': (r) => r.status >= 200 && r.status < 300 });

  http.get(`${BASE}/api/v1/analytics`, { ...h, tags: { endpoint: 'analytics' } });
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/backend/tests/loadtest/scenario-outreach.js
git commit -m "feat(loadtest): add k6 outreach scenario"
```

---

## Task 12: k6 main orchestrator

**Files:**
- Create: `jobhunter/backend/tests/loadtest/main.js`

- [ ] **Step 1: Write the orchestrator**

```javascript
// tests/loadtest/main.js
import { SharedArray } from 'k6/data';
import { browse } from './scenario-browse.js';
import { onboard } from './scenario-onboard.js';
import { outreach } from './scenario-outreach.js';

export const options = {
  thresholds: {
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: true, delayAbortEval: '30s' }],
    'http_req_duration{expected_response:true}': ['p(95)<5000'],
  },
  stages: [
    { duration: '2m', target: 10 },    // warm-up
    { duration: '5m', target: 100 },   // ramp 1
    { duration: '5m', target: 300 },   // ramp 2
    { duration: '5m', target: 700 },   // ramp 3
    { duration: '5m', target: 1200 },  // ramp 4
    { duration: '3m', target: 1200 },  // sustain
    { duration: '30s', target: 0 },    // ramp-down
  ],
};

const users = new SharedArray('users', () => JSON.parse(open('./fixtures/users.json')));

// Global onboarding counter shared across all VUs in this process.
// k6 runs all VUs in a single Go process so a module-level int is safe.
let onboardClaimed = 0;
export function tryClaimOnboardSlot(cap) {
  if (onboardClaimed >= cap) return false;
  onboardClaimed += 1;
  return true;
}

export default function () {
  const user = users[Math.floor(Math.random() * users.length)];
  const r = Math.random();
  if (r < 0.80) {
    browse(user);
  } else if (r < 0.95) {
    onboard(user, browse);
  } else {
    outreach(user);
  }
}
```

- [ ] **Step 2: Validate k6 syntax locally (if k6 installed)**

Run: `k6 inspect jobhunter/backend/tests/loadtest/main.js` (optional — will be validated on the runner)
Expected: no syntax errors

- [ ] **Step 3: Commit**

```bash
git add jobhunter/backend/tests/loadtest/main.js
git commit -m "feat(loadtest): add k6 main orchestrator with ramp stages and mix"
```

---

## Task 13: Sample resume fixture

**Files:**
- Create: `jobhunter/backend/tests/loadtest/fixtures/sample-resume.pdf`

- [ ] **Step 1: Generate a 1-page PDF**

Run:
```bash
cd jobhunter/backend/tests/loadtest/fixtures
python -c "
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
c = canvas.Canvas('sample-resume.pdf')
c.drawString(72, 800, 'Load Test User')
c.drawString(72, 780, 'Senior Engineer')
c.drawString(72, 750, 'Experience: Python, FastAPI, Postgres')
c.save()
"
```

If `reportlab` is unavailable, use any 1-page PDF checked into the repo fixtures — the content is irrelevant, only the file shape matters.

- [ ] **Step 2: Commit**

```bash
git add jobhunter/backend/tests/loadtest/fixtures/sample-resume.pdf
git commit -m "feat(loadtest): add sample resume PDF fixture"
```

---

## Task 14: Orchestration library

**Files:**
- Create: `scripts/loadtest/lib.sh`

- [ ] **Step 1: Write shared helpers**

```bash
#!/usr/bin/env bash
# scripts/loadtest/lib.sh — shared helpers for load-test orchestration

set -euo pipefail

LOG_PREFIX="[loadtest]"

log() { echo "${LOG_PREFIX} $*" >&2; }
die() { log "FATAL: $*"; exit 1; }

# Cost gate — fail loudly if we've blown the budget
BUDGET_USD="${BUDGET_USD:-70}"
check_budget() {
  local spent="$1"
  if (( $(echo "$spent > $BUDGET_USD" | bc -l) )); then
    die "budget exceeded: \$$spent > \$$BUDGET_USD"
  fi
}

# Require a command to be installed
require() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/loadtest/lib.sh
git commit -m "feat(loadtest): add orchestration lib helpers"
```

---

## Task 15: Bring up staging script

**Files:**
- Create: `scripts/loadtest/bring-up-staging.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/loadtest/bring-up-staging.sh
#
# Creates a Railway environment named 'staging-loadtest' in the jobhunter project,
# sets LOADTEST_MODE=1 and LOADTEST_AI_BUDGET=200, deploys current main, runs
# migrations, and seeds fixtures. Prints the deployed URL on success.
#
# Idempotent: if the environment already exists, skips creation and just redeploys.

source "$(dirname "$0")/lib.sh"
require railway

ENV_NAME="staging-loadtest"
PROJECT_ID="cc873661-d54c-44b4-acda-975758d196fe"
SERVICE="jobhunter"

log "linking Railway project $PROJECT_ID"
railway link --project "$PROJECT_ID" --service "$SERVICE"

if ! railway environment | grep -q "^$ENV_NAME$"; then
  log "creating environment $ENV_NAME"
  railway environment new "$ENV_NAME"
else
  log "environment $ENV_NAME already exists"
fi
railway environment use "$ENV_NAME"

log "setting loadtest env vars"
railway variables set LOADTEST_MODE=1 LOADTEST_AI_BUDGET=200 OPENAI_MODEL=gpt-4o-mini

log "deploying"
railway up --detach

log "waiting 60s for healthcheck"
sleep 60

URL=$(railway domain | head -1)
log "staging URL: $URL"

log "running migrations"
railway run --service "$SERVICE" alembic upgrade head

log "seeding data"
railway run --service "$SERVICE" python scripts/seed_loadtest_data.py

# Pull the generated users.json back locally so the k6 runner can use it
log "pulling users.json fixture"
railway run --service "$SERVICE" cat tests/loadtest/fixtures/users.json > jobhunter/backend/tests/loadtest/fixtures/users.json

echo "$URL" > .loadtest-staging-url
log "done. URL stored in .loadtest-staging-url"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/loadtest/bring-up-staging.sh
git add scripts/loadtest/bring-up-staging.sh
git commit -m "feat(loadtest): add Railway staging bring-up script"
```

---

## Task 16: Provision runner script

**Files:**
- Create: `scripts/loadtest/provision-runner.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/loadtest/provision-runner.sh
#
# Spins up a Hetzner CPX21 in eu-central, installs k6, copies test scripts,
# and writes the IP to .loadtest-runner-ip for subsequent scripts to read.

source "$(dirname "$0")/lib.sh"
require hcloud
require ssh
require scp

SERVER_NAME="jobhunter-loadtest-$(date +%s)"
SSH_KEY_NAME="${HCLOUD_SSH_KEY:?set HCLOUD_SSH_KEY to the name of an hcloud ssh key}"

log "creating Hetzner CPX21 $SERVER_NAME"
hcloud server create \
  --name "$SERVER_NAME" \
  --type cpx21 \
  --image ubuntu-24.04 \
  --location nbg1 \
  --ssh-key "$SSH_KEY_NAME"

IP=$(hcloud server ip "$SERVER_NAME")
log "runner IP: $IP"
echo "$SERVER_NAME" > .loadtest-runner-name
echo "$IP" > .loadtest-runner-ip

log "waiting 30s for sshd"
sleep 30

log "installing k6"
ssh -o StrictHostKeyChecking=no "root@$IP" bash -s <<'REMOTE'
set -e
apt-get update -qq
apt-get install -y -qq gnupg ca-certificates
gpg -k
gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | tee /etc/apt/sources.list.d/k6.list
apt-get update -qq
apt-get install -y -qq k6
k6 version
REMOTE

log "copying test scripts"
scp -o StrictHostKeyChecking=no -r jobhunter/backend/tests/loadtest "root@$IP:/root/loadtest"

log "runner ready"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/loadtest/provision-runner.sh
git add scripts/loadtest/provision-runner.sh
git commit -m "feat(loadtest): add Hetzner runner provisioning script"
```

---

## Task 17: Run test script

**Files:**
- Create: `scripts/loadtest/run-test.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/loadtest/run-test.sh
#
# Runs k6 on the provisioned runner against the staging URL, streams the
# summary JSON back, and unconditionally triggers teardown on exit.

source "$(dirname "$0")/lib.sh"

IP=$(cat .loadtest-runner-ip) || die "no runner IP — run provision-runner.sh first"
URL=$(cat .loadtest-staging-url) || die "no staging URL — run bring-up-staging.sh first"
DATE=$(date +%Y-%m-%d)
OUT_DIR="docs/superpowers/loadtest-results/$DATE"
mkdir -p "$OUT_DIR"

trap '"$(dirname "$0")/teardown-staging.sh" || true' EXIT

log "starting k6 against $URL"
ssh -o StrictHostKeyChecking=no "root@$IP" \
  "cd /root/loadtest && BASE_URL='$URL' ONBOARD_CAP=200 k6 run --summary-export=/root/summary.json main.js" \
  | tee "$OUT_DIR/k6-stdout.log"

log "pulling artifacts"
scp "root@$IP:/root/summary.json" "$OUT_DIR/k6-summary.json"

log "k6 run complete, artifacts in $OUT_DIR"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/loadtest/run-test.sh
git add scripts/loadtest/run-test.sh
git commit -m "feat(loadtest): add k6 run script with trap-based teardown"
```

---

## Task 18: Collect artifacts script

**Files:**
- Create: `scripts/loadtest/collect-artifacts.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/loadtest/collect-artifacts.sh
#
# Collects Railway logs, Postgres slow query log, and Redis snapshot
# from the staging environment into the results directory.

source "$(dirname "$0")/lib.sh"

DATE=$(date +%Y-%m-%d)
OUT_DIR="docs/superpowers/loadtest-results/$DATE"
mkdir -p "$OUT_DIR"

log "pulling Railway backend logs"
railway logs --service jobhunter --environment staging-loadtest > "$OUT_DIR/railway-logs.txt" || true

log "pulling Postgres slow query log"
railway run --service postgres psql -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 50;" \
  > "$OUT_DIR/pg-slow.log" || true

log "pulling Redis info"
railway run --service redis redis-cli INFO > "$OUT_DIR/redis-info.txt" || true

log "artifacts collected in $OUT_DIR"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/loadtest/collect-artifacts.sh
git add scripts/loadtest/collect-artifacts.sh
git commit -m "feat(loadtest): add artifact collection script"
```

---

## Task 19: Teardown script

**Files:**
- Create: `scripts/loadtest/teardown-staging.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/loadtest/teardown-staging.sh
#
# Unconditional cleanup: destroys the staging Railway environment AND the
# Hetzner runner VM. Safe to call multiple times (idempotent).

source "$(dirname "$0")/lib.sh"

ENV_NAME="staging-loadtest"

if command -v railway >/dev/null; then
  log "destroying Railway env $ENV_NAME"
  railway environment delete "$ENV_NAME" --yes || log "railway env delete failed (may already be gone)"
fi

if command -v hcloud >/dev/null && [[ -f .loadtest-runner-name ]]; then
  RUNNER=$(cat .loadtest-runner-name)
  log "destroying Hetzner runner $RUNNER"
  hcloud server delete "$RUNNER" || log "hcloud delete failed (may already be gone)"
  rm -f .loadtest-runner-name .loadtest-runner-ip
fi

rm -f .loadtest-staging-url
log "teardown complete"
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x scripts/loadtest/teardown-staging.sh
git add scripts/loadtest/teardown-staging.sh
git commit -m "feat(loadtest): add unconditional teardown script"
```

---

## Task 20: End-to-end dry run (dry mode)

**Files:**
- None (execution task)

- [ ] **Step 1: Verify all scripts parse**

Run:
```bash
for s in scripts/loadtest/*.sh; do bash -n "$s" && echo "OK $s"; done
```
Expected: every script prints `OK`.

- [ ] **Step 2: Verify backend unit tests still pass**

Run: `cd jobhunter/backend && pytest tests/ -x -q`
Expected: all green

- [ ] **Step 3: Check required CLIs are installed**

Run:
```bash
command -v railway && command -v hcloud && command -v ssh && command -v scp
```
Expected: all four resolve. If any are missing, install before proceeding to Task 21.

- [ ] **Step 4: Confirm HCLOUD_SSH_KEY is set**

Run: `echo "${HCLOUD_SSH_KEY:-UNSET}"`
Expected: a non-`UNSET` value. If unset, run `hcloud ssh-key list`, pick or create one, and `export HCLOUD_SSH_KEY=<name>`.

---

## Task 21: Execute the load test

**Files:**
- Updates: `docs/superpowers/loadtest-results/2026-04-07/` (new directory)

- [ ] **Step 1: Bring up staging**

Run: `scripts/loadtest/bring-up-staging.sh`
Expected: prints `staging URL: https://...`, writes `.loadtest-staging-url`

- [ ] **Step 2: Smoke-check staging health**

Run: `curl -sf "$(cat .loadtest-staging-url)/api/v1/health"`
Expected: 200 with `{"status": "healthy"}` (or similar).

**Stop-and-confirm gate ($20):** at this point Railway has billed for bring-up + ~5 min idle. Check the Railway billing dashboard. If spent > $20, STOP, report to user, do NOT proceed.

- [ ] **Step 3: Provision runner**

Run: `scripts/loadtest/provision-runner.sh`
Expected: prints `runner ready`, writes `.loadtest-runner-ip`

- [ ] **Step 4: Run the test**

Run: `scripts/loadtest/run-test.sh`
Expected: k6 ramps through all stages OR aborts on threshold breach. Either way, summary JSON lands in `docs/superpowers/loadtest-results/2026-04-07/k6-summary.json`. Teardown runs on exit via trap.

- [ ] **Step 5: Collect artifacts (before teardown completes — this runs inside the trap too)**

Run: `scripts/loadtest/collect-artifacts.sh` — only if trap in run-test.sh didn't already call it. Manual invocation is safe.

- [ ] **Step 6: Confirm teardown**

Run:
```bash
railway environment list | grep staging-loadtest && echo "STILL EXISTS" || echo "GONE"
hcloud server list | grep jobhunter-loadtest && echo "STILL EXISTS" || echo "GONE"
```
Expected: both print `GONE`. If either still exists, run `scripts/loadtest/teardown-staging.sh` manually.

---

## Task 22: Write the report

**Files:**
- Create: `docs/superpowers/loadtest-results/2026-04-07/report.md`

- [ ] **Step 1: Extract headline metrics from k6 summary**

Read `docs/superpowers/loadtest-results/2026-04-07/k6-summary.json`. Identify:
- Total requests, total failures, error rate
- p50/p95/p99 `http_req_duration` overall
- Per-endpoint p95 (from the `tags.endpoint` breakdown)
- At which ramp stage failures or latency first crossed the SLO (p95 > 2s OR error rate > 1%)

- [ ] **Step 2: Read Railway/Postgres/Redis artifacts**

Scan `railway-logs.txt` for ERROR/CRITICAL lines. Note the top 5 error signatures.
Scan `pg-slow.log` for the slowest queries.
Scan `redis-info.txt` for peak memory / connected clients.

- [ ] **Step 3: Write the report**

```markdown
# Load Test Report — 2026-04-07

## Headline
System handled **N concurrent users** before breaching SLO (p95 < 2s, error rate < 1%).

## Per-Phase Results
| Phase   | VUs        | req/s | p50  | p95  | p99  | errors | first-failing endpoint |
|---------|------------|-------|------|------|------|--------|------------------------|
| warm-up | 10         | ...   | ...  | ...  | ...  | ...%   | —                      |
| ramp 1  | 10→100     | ...   | ...  | ...  | ...  | ...%   | ...                    |
| ramp 2  | 100→300    | ...   | ...  | ...  | ...  | ...%   | ...                    |
| ramp 3  | 300→700    | ...   | ...  | ...  | ...  | ...%   | ...                    |
| ramp 4  | 700→1200   | ...   | ...  | ...  | ...  | ...%   | ...                    |
| sustain | last stable| ...   | ...  | ...  | ...  | ...%   | ...                    |

## Top 10 Slowest Endpoints
(fill from k6 per-endpoint p95)

## Top 5 Error Signatures
(fill from Railway logs)

## Resource Usage
- Backend CPU peak: ...
- Backend memory peak: ...
- Postgres CPU peak: ...
- Postgres connections peak: ...
- Redis memory peak: ...
- Redis connected clients peak: ...

## Bottleneck Diagnosis
(Which layer saturated first — app CPU, DB connection pool, Redis, pgvector writes, OpenAI cap — with evidence from the artifacts.)

## Go / No-Go
(Verdict against the launch target + prioritized list of fixes.)

## Budget Actuals
| Item                      | Estimated | Actual |
|---------------------------|-----------|--------|
| Railway staging           | $5–15     | $...   |
| OpenAI (≤200 runs)        | $10–30    | $...   |
| Hetzner runner            | < $1      | $...   |
| **Total**                 | **$26–66**| **$...** |

## Artifacts
- `k6-summary.json`
- `k6-stdout.log`
- `railway-logs.txt`
- `pg-slow.log`
- `redis-info.txt`
```

- [ ] **Step 4: Commit report**

```bash
git add docs/superpowers/loadtest-results/2026-04-07/
git commit -m "docs(loadtest): add 2026-04-07 volume test results and report"
```

---

## Self-Review Notes

**Spec coverage:**
- Staging env w/ prod-identical plan → Task 15
- Mocked Hunter/Resend → Tasks 4–6
- OpenAI cap of 200 runs → Tasks 2–3
- Seeded 2000 candidates + 500 jobs + 50 companies → Task 7
- Ramp 10→1200 profile → Task 12
- 80/15/5 traffic mix → Task 12
- Abort conditions (p95, error rate) → Task 12 (thresholds)
- k6 on cloud runner → Tasks 16–17
- Unconditional teardown → Tasks 17, 19
- Observability (Railway/PG/Redis) → Task 18
- Headline report → Task 22
- $20 stop-and-confirm gate → Task 21 Step 2
- Budget ceiling tracking → Task 22 actuals table

**Known risks for the implementer:**
- The seed script (Task 7) and DI swap (Task 6) assume current model/protocol shapes. Read the real files before blindly applying the code in the plan.
- The onboarding cap in `main.js` relies on a module-level counter — correct for a single-process k6 run, would need Redis or equivalent if we ever switch to distributed runners.
- `railway run ... cat` for fixture pull (Task 15) may not work on every Railway plan; fallback is to `railway ssh` and scp, or to generate `users.json` deterministically on both sides.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-07-volume-test.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session with checkpoints.

Which approach?
