# Volume Test Design — JobHunter Pre-Launch

**Date:** 2026-04-06
**Status:** Draft (awaiting user approval)
**Author:** Eran + Claude

## Goal

Find the concurrent-user ceiling of the JobHunter backend before public launch, on a staging environment that mirrors Railway production, within a hard budget of **$50–70 USD**.

The headline question we want to answer: *"How many concurrent users can the system support before it breaches our SLO (p95 latency < 2s, error rate < 1%)?"*

This is a stress test, not a soak test or a benchmark. We ramp until something breaks, then report what broke.

## Non-Goals

- Validating OpenAI's own throughput / rate limits (out of our control)
- Validating email deliverability (Resend is mocked)
- Long-duration soak / endurance testing (out of budget)
- Frontend client performance (Next.js is not under test; only the API tier is)
- Testing payment flows (not implemented yet)

## Environment

A new Railway environment `staging-loadtest` in the existing project (`cc873661-d54c-44b4-acda-975758d196fe`), provisioned for the duration of the test and destroyed after.

- **Service plan:** identical to production so the capacity numbers transfer to launch day.
- **Resources:** dedicated Postgres+pgvector, dedicated Redis, dedicated R2 bucket, fresh `JWT_SECRET` and `UNSUBSCRIBE_SECRET`.
- **External services neutered:**
  - **OpenAI:** real calls, but forced to `gpt-4o-mini`. The resume pipeline checks a `LOADTEST_AI_BUDGET=200` env var on entry and refuses new runs once 200 lifetime runs have been recorded in Redis (`loadtest:ai_runs` counter, atomic INCR).
  - **Hunter.io:** mocked client behind `LOADTEST_MODE=1`, returns canned company/contact fixtures with 200ms simulated latency.
  - **Resend:** mocked behind `LOADTEST_MODE=1`, no real emails sent. Returns synthetic message IDs.
- **Seeded data:** ~500 fake jobs, 50 fake companies, 2000 free-tier candidates with known credentials, all loaded via a fixture script before the test starts.
- **Teardown:** environment deleted unconditionally at end of test (success or failure) via `scripts/loadtest/teardown-staging.sh`.

## Load Profile

Ramp test designed to find the breaking point, not measure steady-state.

| Phase    | Duration | Concurrent VUs    | Purpose                          |
|----------|----------|-------------------|----------------------------------|
| Warm-up  | 2 min    | 10                | Prime caches, warm connections   |
| Ramp 1   | 5 min    | 10 → 100          | Baseline                         |
| Ramp 2   | 5 min    | 100 → 300         | Expected launch load             |
| Ramp 3   | 5 min    | 300 → 700         | Stress                           |
| Ramp 4   | 5 min    | 700 → 1200        | Find the breaking point          |
| Sustain  | 3 min    | last stable level | Confirm stability                |

**Total wall-clock:** ~25 minutes of active load + ~30 minutes for setup/teardown.

### Traffic Mix

Each virtual user runs an infinite loop, picking a scenario by weighted random on each iteration:

- **80% — Browsing**
  Login → `GET /api/v1/dashboard` → `GET /api/v1/jobs` → `GET /api/v1/jobs/{id}` → `GET /api/v1/resume` → think 2–5s → repeat.

- **15% — Onboarding**
  Register → upload a small fixed PDF resume → poll `GET /api/v1/resume` until pipeline completes → `GET /api/v1/dashboard`.
  **Globally hard-capped at 200 total runs** across the whole test session, enforced by a shared k6 counter. VUs that try to start an onboarding past the cap fall back to a browsing iteration.

- **5% — Outreach / Dossier**
  Login → `GET /api/v1/companies/{id}/dossier` for a seeded company → trigger a (mocked) outreach draft → `GET /api/v1/analytics`.

### Abort Conditions

The test runner auto-stops the ramp if any of the following holds true:

- p95 latency > 5s for 60 seconds straight
- Error rate > 10% for 30 seconds straight
- Any 5xx burst > 50/sec
- Railway healthcheck for the backend service fails

When aborted, the test reports the last stable concurrency level as the ceiling.

## Tooling

- **Load generator:** [k6](https://k6.io/) (Grafana). Chosen over Locust/Artillery/JMeter for its high VU-per-machine throughput, native ramp stages, JS scripting, and built-in p50/p95/p99 metrics.
- **Runner:** a one-shot **Hetzner CPX21** VM in `eu-central` (close to Railway's region — realistic latency, not zero). Spun up at the start of the test, destroyed at the end. Estimated cost: < $1.
- **Test scripts location:** `jobhunter/backend/tests/loadtest/`
  - `scenario-browse.js`
  - `scenario-onboard.js`
  - `scenario-outreach.js`
  - `main.js` — ramp stages, weighted scenario picker, global onboarding counter
  - `fixtures/sample-resume.pdf`
- **Synthetic users:** pre-seeded into staging DB before the test starts. k6 picks credentials from a `SharedArray`.
- **Provisioning scripts:** `scripts/loadtest/`
  - `bring-up-staging.sh` — creates Railway env, deploys current main, applies migrations, seeds fixtures
  - `provision-runner.sh` — creates Hetzner VM, installs k6, scp's scripts
  - `run-test.sh` — kicks off k6 on the runner, streams results back
  - `collect-artifacts.sh` — pulls Railway logs, Postgres slow query log, Redis snapshots, k6 JSON
  - `teardown-staging.sh` — destroys staging env + runner VM (idempotent, safe to call multiple times)

## Observability

Captured during the test window:

- **Railway:** built-in metrics dashboard for backend, Postgres, Redis (CPU, memory, network I/O)
- **Postgres:** `pg_stat_activity` snapshots every 10s, slow query log (> 500ms) tailed to file
- **Redis:** `INFO` snapshots every 10s
- **App logs:** structured JSON logs streamed via `railway logs --service jobhunter` to a file
- **k6:** native metrics — req/sec, p50/p95/p99 latency, error rate, per-endpoint breakdown — written to JSON

## Results & Reporting

Final artifact: `docs/superpowers/loadtest-results/2026-04-06/report.md` containing:

- **Headline:** "System handled N concurrent users before breaching SLO (p95 < 2s, error rate < 1%)"
- **Per-phase table:** concurrent VUs, requests/sec, p50/p95/p99 latency, error rate, top failing endpoint
- **Resource graphs:** Railway CPU/memory/network for backend, Postgres, Redis across the test window
- **Top 10 slowest endpoints** under load
- **Top 5 error signatures** grouped by exception type / status code
- **Bottleneck diagnosis:** which layer saturated first (app CPU? DB connection pool? Redis? pgvector HNSW writes? OpenAI cap?)
- **Go/no-go verdict** against the launch target, with a prioritized list of fixes if any
- Raw artifacts (k6 JSON, Railway logs, Postgres slow log, Redis snapshots) archived alongside

## Budget

Hard ceiling: **$70**. The test aborts and re-scopes with the user if any phase exceeds its allotment.

| Item                                                  | Estimate    |
|-------------------------------------------------------|-------------|
| Railway staging env (~4 hours @ prod-equivalent plan) | $5–15       |
| OpenAI `gpt-4o-mini` × ≤200 capped pipeline runs      | $10–30      |
| Hetzner CPX21 runner VM (~2 hours)                    | < $1        |
| Buffer for retries / re-runs                          | $10–20      |
| **Total ceiling**                                     | **$26–66**  |

**Stop-and-confirm gate:** if staging bring-up + first warm-up run exceed $20, halt and re-scope with the user before continuing the full ramp.

## Risks & Mitigations

| Risk                                                              | Mitigation                                                                                  |
|-------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| Staging env left running after test, burning Railway credit       | Unconditional teardown in `teardown-staging.sh`, called from a `trap` in `run-test.sh`      |
| OpenAI cost overrun                                               | Hard cap of 200 pipeline runs enforced server-side via Redis counter, not just client-side  |
| Test results don't transfer to prod (different plan)              | Staging uses identical service plan to production                                           |
| Test traffic hits production by mistake                           | Staging gets its own subdomain, its own JWT secret; runner only knows staging URL           |
| k6 runner becomes the bottleneck instead of the backend           | Hetzner CPX21 (4 vCPU, 8GB) handles 1200 VUs with headroom; verified in warm-up phase       |
| Mocked Hunter/Resend hide a real bottleneck                       | Documented as a known limitation; mocks add 200ms simulated latency to stay realistic       |

## Execution Plan (for the implementation phase)

The detailed plan will be produced by the `writing-plans` skill after this design is approved. High-level shape:

1. **Parallel scaffolding (subagents A–D):**
   - Agent A: write k6 scripts (`scenario-*.js`, `main.js`)
   - Agent B: write staging seed fixture script (2000 candidates, 500 jobs, 50 companies)
   - Agent C: add `LOADTEST_MODE` + `LOADTEST_AI_BUDGET` gates in the resume pipeline; add Hunter/Resend mock clients
   - Agent D: write Railway bring-up / Hetzner provisioning / teardown shell scripts

2. **Sequential execution (single coordinator):**
   - Bring up staging env, run migrations, seed data
   - Provision runner VM, copy scripts
   - Run warm-up phase, verify metrics flowing
   - **Stop-and-confirm gate** ($20 check)
   - Run full ramp test
   - Collect artifacts
   - Teardown
   - Generate report

## Open Questions

None at time of writing. All design decisions captured in the sections above.
