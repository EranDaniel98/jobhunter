# Open Issues, Features & TODOs

## Bugs / Needs Verification
- **Indeterminate progress bar not visible**: The loading bar animation (`animate-[indeterminate_1.5s_ease-in-out_infinite]`) added to apply analysis and resume processing does not display. Likely a CSS/Tailwind issue - the keyframe may not be picked up by Tailwind's JIT or the element dimensions are wrong.

## Recently Completed (QA Audit v0.3.0)

### Phase 1 - Critical Fixes
- ~~**Set max_tokens on all OpenAI calls**~~: chat=2000, parse_structured=4000, vision=2000 with optional override
- ~~**Interview prep quota enforcement**~~: `check_and_increment("openai")` on all 4 endpoints
- ~~**CORS restriction**~~: Explicit `allow_methods` and `allow_headers` (was `["*"]`)
- ~~**MIME type + magic bytes validation**~~: File uploads check content_type + %PDF/PK header bytes
- ~~**Contacts pagination**~~: Added `skip`/`limit` to `/{company_id}/contacts`
- ~~**CSP hardening**~~: Removed `unsafe-inline` from `script-src`, scoped `wss:` to FRONTEND_URL
- ~~**Root error boundary + 404**~~: `error.tsx` and `not-found.tsx` at app root

### Phase 2 - High-Impact Improvements
- ~~**Combined dashboard API call**~~: 3 analytics hooks → single `useAnalyticsDashboard()` (saves 2 API calls/page)
- ~~**Remove refetchOnWindowFocus from admin**~~: Removed from 4 hooks that already use `refetchInterval`
- ~~**Debounce WS cache invalidations**~~: 500ms debounce window, batch invalidation
- ~~**Outreach graph N+1 fix**~~: `selectinload` + `asyncio.gather` (6 queries → 3)
- ~~**Admin pagination**~~: Added `skip` to `/activity` and `/audit-log`
- ~~**Sanitize ValueError messages**~~: `safe_400()` utility applied to contacts + companies
- ~~**WebSocket token re-validation**~~: 5-min periodic re-auth, sends `auth_expired` before disconnect

### Phase 3 - Optimization & Hardening
- ~~**Skip-to-content link**~~: Accessibility a11y landmark in root layout
- ~~**Docker resource limits**~~: backend 1G, postgres 2G, redis 512M, arq 1G
- ~~**ARQ worker health check**~~: Redis ping health check added
- ~~**Redis TTL on warm-up keys**~~: 90-day expiry on `email_warmup:*:start_date`

### Phase 4 - v0.4.0 (Cost, Auth, Multi-Tenant)
- ~~**Per-user concurrency semaphore**~~: `asyncio.Semaphore(3)` per user, 5s timeout → 429 on interview, companies, apply
- ~~**Daily spending circuit breaker**~~: Redis-backed daily cost tracker, `check_budget()` before every OpenAI call, 503 at limit
- ~~**Align rate limits with quotas**~~: Company discover rate limit 3/hr → 2/hr to match free tier quota
- ~~**Zod form validation schemas**~~: `zod` + `react-hook-form` + `@hookform/resolvers` on login, register, settings security
- ~~**Accessibility**~~: `aria-live` on dashboard stats, `aria-describedby` on form errors, `aria-expanded` on discover collapsible
- ~~**Password reset flow**~~: `POST /forgot-password` + `/reset-password`, 2h token, rate-limited 5/hr, frontend pages
- ~~**#29 Per-user API cost tracking**~~: `api_usage` table (migration 021), per-request recording, admin + user endpoints
- ~~**#30 Multi-tenant RLS**~~: SQLAlchemy `do_orm_execute` event listener, `current_tenant_id` context var, behind `ENABLE_RLS` flag

## P1 - Next Up

### Features
- **Landing page waitlist → beta invites**: Convert waitlist signups to invite flow (growth)
- **SPF/DKIM deliverability**: Verify DNS records for Resend so outreach emails don't land in spam (ops)
- **pgBouncer connection pooling**: Add connection pooling to handle 200+ concurrent DB connections (infra)
- **OpenAI response caching**: Cache identical company research results to cut API costs (infra, ai)
- **Batch ARQ cron jobs**: Batch per-user cron jobs instead of sequential execution (infra)

## P2 - Soon
- **#5**: Resume tailoring with tracked-changes diffs (area: ai)
- **Retry button on failed company research**: Show a refresh/retry button when research fails (only if daily quota not reached)
- **Guided onboarding tour**: Highlight blocks, show descriptions, walk user through all pages step-by-step
- **Google OAuth**: Social login to reduce signup friction (auth)
- **GDPR self-service data export**: Let users export their own data, not just admin CSV export (compliance)
- **Lazy-load recharts**: `next/dynamic({ ssr: false })` for chart components when used (~60KB savings)

## P3 - Later
- **#6**: Job board scraping with JobSpy (area: companies)
- **#15**: Salary negotiation module (area: ai)
- **#27**: LinkedIn API integration for automated profile enrichment (area: companies)
- **#28**: Calendar integration for interview scheduling
- **Hebrew/i18n**: User-selectable language for interview prep, company enriched data, apply tab, etc.
- **Image alt text ESLint rule**: `jsx-a11y/alt-text` for future images
- **`aria-live` for WebSocket updates**: Real-time content announcements for screen readers
- **Content terminology audit**: Consistent wording across all pages
- **Localization readiness**: Audit hardcoded date/currency formats
