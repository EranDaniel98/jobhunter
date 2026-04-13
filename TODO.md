# Hunter - TODO

## Bugs

### Quota exceeded gives no user notification
**Priority:** High
**Found:** 2026-03-25
**Context:** User hit free-tier quota limits but received no visible feedback — actions silently failed.

**Current state:**
- Backend returns 429 with structured `{ quota_type, limit, message }` on quota exceed
- Frontend has `QuotaExceededAlert` component (`components/shared/quota-exceeded-alert.tsx`)
- Frontend has `toastError()` and `getQuotaDetail()` utils (`lib/api/error-utils.ts`)
- But the error is not surfaced to the user — either the 429 isn't caught in the mutation's `onError`, or the toast isn't firing

**Fix needed:**
1. Audit all mutation hooks that call quota-gated endpoints (discover, research, contact lookup, email send, OpenAI calls) — ensure `onError` calls `toastError()`
2. Consider showing `QuotaExceededAlert` inline on the page (not just toast) when a quota-gated action fails
3. Add upgrade CTA in the quota notification (link to `/plans` or `/billing`)
4. Consider proactive warning when user is near quota limit (e.g., "2 of 3 discoveries used today")

**Quota-gated endpoints to check:**
- `POST /companies/discover` (discovery)
- `POST /companies/{id}/research` (research)
- `POST /contacts/search` (hunter)
- `POST /outreach/draft` (email + openai)
- `POST /interview-prep` (openai)
- `POST /apply/analyze` (openai)

---

### [FIXED] Dossier endpoint 500 — Pydantic type mismatch
**Priority:** Critical
**Found:** 2026-03-25
**Root cause:** AI-generated dossier data stores `compensation_data` as string and `recent_news` items as strings, but `CompanyDossierResponse` schema expected `dict` and `list[dict]`. Pydantic validation failed → 500 error → frontend showed "Approve this company" instead of dossier.
**Fix:** Made `CompanyDossierResponse` accept `str | dict` for `compensation_data` and `list[dict | str]` for `recent_news`. Updated frontend types and rendering to handle both.

---

### [FIXED] Resume parse failure shows no error to user
**Priority:** High
**Found:** 2026-03-25
**Root cause:** WebSocket `resume_parsed` event always showed "Resume parsed successfully" toast regardless of status. No error stored in DB for display.
**Fix:** WS handler now checks `status === "failed"`. Error stored in `parsed_data._error`. Resume history shows user-friendly message; admins see technical error.

---

### [FIXED] WebSocket doesn't invalidate company detail/dossier queries
**Priority:** High
**Found:** 2026-03-25
**Root cause:** `research_completed` WS event only invalidated `["companies"]` list, not `["company"]`, `["dossier"]`, or `["contacts"]` queries used on detail page.
**Fix:** Added `["company"]`, `["dossier"]`, `["contacts"]` to invalidation for `research_completed` events.

---

### OpenAI API quota exhausted
**Priority:** Blocker (for personal use)
**Found:** 2026-03-25
**Root cause:** Production `OPENAI_API_KEY` has no credits. All AI pipelines fail (resume parsing, company research, outreach drafting).
**Fix:** Add credits at platform.openai.com/settings/organization/billing or replace API key in Railway env vars.

---

## Planned Features

- [ ] Job board scraping (JobSpy integration)
- [ ] LinkedIn API integration
- [ ] Calendar integration for email sequences
- [ ] A/B testing for outreach effectiveness
- [ ] Resume tailoring with tracked-changes diffs
- [ ] Advanced resume parser (structured education, certifications)
- [ ] Interview success prediction (ML scoring)
- [ ] Salary history tracking & negotiation insights
