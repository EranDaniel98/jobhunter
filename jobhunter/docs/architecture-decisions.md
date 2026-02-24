# Architecture Decision Records

This document captures key architectural decisions made during JobHunter AI development.

---

## ADR-001: PyJWT over python-jose

**Status:** Accepted

**Context:** We needed a JWT library for authentication. `python-jose` is popular but has had stale maintenance. `PyJWT` is actively maintained and has a simpler API.

**Decision:** Use `PyJWT` for JWT encoding/decoding.

**Consequences:** Simpler dependency tree, active security patches, no JOSE-specific features needed.

---

## ADR-002: Protocol-based Dependency Injection

**Status:** Accepted

**Context:** External API clients (OpenAI, Hunter.io, Resend) need to be swappable in tests without hitting real APIs.

**Decision:** Define Python `Protocol` classes for each client interface. Production implementations and test stubs both satisfy the same protocol. `dependencies.py` manages singleton instances.

**Consequences:** Tests run fast with zero API calls. Adding a new client requires implementing the protocol + a stub. No DI framework needed — plain FastAPI `Depends()`.

---

## ADR-003: Redis Graceful Degradation

**Status:** Accepted

**Context:** Redis is used for rate limiting, caching, and quota tracking. If Redis goes down, the app should not crash.

**Decision:** Provide `redis_safe_get` / `redis_safe_setex` helpers that catch exceptions and return fallback values. Critical paths (auth, DB) work without Redis.

**Consequences:** Partial functionality during Redis outages. Rate limits and quotas become temporarily unenforced, which is acceptable for a single-tenant app.

---

## ADR-004: Numeric Alembic Revision Prefixes

**Status:** Accepted

**Context:** Auto-generated Alembic revision IDs are random hex strings, making migration order unclear.

**Decision:** Use numeric prefixes in migration messages (e.g., `001_initial_schema`, `002_add_contacts`).

**Consequences:** Clear ordering in file listings. Manual numbering required when creating migrations.

---

## ADR-005: OpenAI Structured Output with Strict Mode

**Status:** Accepted

**Context:** We need reliable structured data from OpenAI (company discovery, resume parsing, dossier generation).

**Decision:** Use OpenAI's structured output (JSON mode with schema) and `strict=True` to guarantee valid responses.

**Consequences:** Eliminates JSON parsing errors. Requires well-defined schemas for each use case. Minor latency increase from schema validation.

---

## ADR-006: SlowAPI in Separate Module

**Status:** Accepted

**Context:** Importing `limiter` directly in `main.py` and route modules caused circular imports because `main.py` also imports the routers.

**Decision:** Define the `limiter` instance in a standalone `rate_limit.py` module that both `main.py` and route modules import.

**Consequences:** Clean dependency graph. All rate limit configuration in one place.

---

## ADR-007: Atomic Redis INCR for Daily Limits

**Status:** Accepted

**Context:** Daily email sending and API call quotas need race-condition-safe counting.

**Decision:** Use Redis `INCR` (atomic increment) with date-based keys and `EXPIRE` for auto-cleanup. Pattern: `quota:{user_id}:{type}:{date}` → INCR → check limit → DECR if over.

**Consequences:** No database writes for quota tracking. Keys auto-expire after 24h. Same pattern used for email limits and API cost quotas.

---

## ADR-008: Singleton Client Pattern in dependencies.py

**Status:** Accepted

**Context:** API clients (OpenAI, Hunter, Resend, Storage) should be instantiated once and reused across requests.

**Decision:** `dependencies.py` holds module-level `_client` variables initialized on first access via `get_*()` functions. Tests override these directly.

**Consequences:** Zero overhead from repeated client creation. Test cleanup must reset singletons to `None`.

---

## ADR-009: LangGraph for Resume Pipeline Orchestration

**Status:** Accepted

**Context:** Resume processing involves multiple sequential steps (parse → extract skills → generate DNA → compute embeddings → update fit scores). Steps can fail independently and should be retryable.

**Decision:** Use LangGraph with PostgreSQL-backed checkpointing for the resume processing pipeline. Each step is a graph node with typed state.

**Consequences:** Built-in retry, state persistence, and step-level visibility. Adds LangGraph + checkpoint-postgres dependencies. Pipeline state survives server restarts.
