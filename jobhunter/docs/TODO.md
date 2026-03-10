# Open Issues, Features & TODOs

## Bugs / Needs Verification
- **Admin quota bypass**: Code is implemented but user still saw "Free Plan" and limits. Verify `is_admin=true` in DB for erand1998@gmail.com.
- **Indeterminate progress bar not visible**: The loading bar animation (`animate-[indeterminate_1.5s_ease-in-out_infinite]`) added to apply analysis and resume processing does not display. Likely a CSS/Tailwind issue — the keyframe may not be picked up by Tailwind's JIT or the element dimensions are wrong.

## Not Yet Implemented (from UI/UX batch)
- **Retry button on failed company research**: Show a refresh/retry button when research fails (only if daily quota not reached)

## Deferred Features (UI/UX)
- **Hebrew/i18n**: User-selectable language for interview prep, company enriched data, apply tab, etc.
- **Guided onboarding tour**: Highlight blocks, show descriptions, walk user through all pages step-by-step

## GitHub Issues — Phase 2
- **#5**: Resume tailoring with tracked-changes diffs (area: ai)
- **#6**: Job board scraping with JobSpy (area: companies)
- **#15**: Salary negotiation module (area: ai)

## GitHub Issues — Phase 4
- **#27**: LinkedIn API integration for automated profile enrichment (area: companies)
- **#28**: Calendar integration for interview scheduling
- **#30**: Multi-tenant architecture with row-level security (infra)

## GitHub Issues — Unscheduled
- **#29**: Per-user API cost tracking with OpenAI token metering (area: ai, billing)

## Open PR
- **#24**: Landing page overhaul — product-first design (`feat/landing-page-overhaul`, current branch)
