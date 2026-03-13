# Design: CI/CD, Email Verification, A/B Testing, Resume Bullet Suggestions

**Date:** 2026-02-24
**Issues:** #16, #9, #14, + new resume bullets feature

---

## Feature 1: CI/CD Pipeline (#16)

Single GitHub Actions workflow triggered on push/PR to main.
- **Backend job**: PostgreSQL + Redis service containers, `uv run pytest`
- **Frontend job**: `npm run build` + `npm run lint`
- **Docker job** (release only): Build and push image on tag push

One workflow file, two parallel jobs for CI, one conditional job for releases.

## Feature 2: Email Verification (#9)

- Add `email_verified: bool = False` to Candidate model (Alembic migration)
- On registration: send verification email with short-lived JWT (`type: "verify"`, 24h expiry)
- `POST /auth/verify?token=...` validates token, sets `email_verified = True`
- Guard in `get_current_candidate`: if not verified, return 403
- Frontend: banner on dashboard "Check your email to verify your account" with resend button
- `POST /auth/resend-verification` rate-limited to 1 per 5 minutes per user via Redis (`verify_cooldown:{candidate_id}`, 300s TTL)
- Frontend resend button shows countdown timer, persisted via localStorage

## Feature 3: A/B Testing (#14)

- Add `variant: str | None` column to OutreachMessage (migration)
- `draft_message()` accepts optional `tone` parameter
- `POST /outreach/{contact_id}/draft-variants` returns 2 drafts (professional + conversational)
- User picks one, other is deleted
- Analytics: `get_outreach_stats()` extended to group by variant
- Frontend: side-by-side variant picker dialog on company detail page

## Feature 4: Resume Bullet Suggestions (new)

- Add `resume_bullets: list[str] | None` to CompanyDossier model + schema
- Extend dossier prompt to generate 3-5 bullet points based on DNA gaps vs company requirements
- Display on company detail page below "Why Hire Me" as checklist card
- No separate endpoint - included in existing dossier response
