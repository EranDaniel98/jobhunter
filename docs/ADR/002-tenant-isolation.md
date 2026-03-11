# ADR-002: Tenant Isolation via Middleware

## Status
Accepted

## Context
JobHunter is designed as a multi-tenant SaaS where each candidate is a tenant. All database tables already have `candidate_id` foreign keys, but tenant context wasn't systematically propagated through the request lifecycle.

## Decision
Implement `TenantMiddleware` (`app/middleware/tenant.py`) that extracts `candidate_id` from the JWT on authenticated requests and:
1. Sets `request.state.tenant_id` for use by downstream handlers
2. Binds `tenant_id` to structlog context for automatic inclusion in all log entries

Public endpoints and admin endpoints bypass tenant extraction.

## Consequences
- **Positive:** Every log line includes tenant context, enabling per-tenant debugging. Foundation for row-level security and tenant-scoped queries.
- **Negative:** JWT is decoded twice (once in middleware, once in auth dependency). Minimal overhead since JWT decode is fast.
- **Future:** Add database-level row security policies. Add tenant-scoped rate limiting.
