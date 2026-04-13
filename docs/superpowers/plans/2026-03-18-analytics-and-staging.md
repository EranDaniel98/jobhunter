# Conversion Tracking & Staging Environment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Plausible analytics to the marketing site for conversion tracking, and create a Railway staging environment that mirrors production.

**Architecture:** Plausible Cloud (hosted) for privacy-friendly web analytics with custom event tracking on waitlist signups — no cookie banners needed. Staging is a second Railway service pointing at a separate Postgres + Redis, sharing the same Docker image but with `SENTRY_ENVIRONMENT=staging`. Frontend staging deploys via a separate Cloudflare Pages project with `NEXT_PUBLIC_API_URL` pointing to the staging backend.

**Tech Stack:** Plausible Analytics (Cloud), Railway CLI, Cloudflare Pages, Next.js `<Script>`, existing CI workflow

---

## File Structure

### Analytics (Step 2)

| File | Action | Responsibility |
|------|--------|----------------|
| `jobhunter/frontend/src/app/layout.tsx` | Modify | Inject Plausible `<Script>` tag inside `<body>` |
| `jobhunter/frontend/next.config.ts` | Modify | Add CSP header allowing `plausible.io` |
| `jobhunter/frontend/src/lib/analytics.ts` | Create | Thin wrapper: `trackEvent(name, props)` around `window.plausible` |
| `jobhunter/frontend/src/app/(marketing)/page.tsx` | Modify | Fire `Waitlist Signup` event on successful form submit |
| `jobhunter/frontend/.env.production` | Modify | Add `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` |
| `jobhunter/frontend/.env.local` | Modify | Add `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` (empty = disabled locally) |
| `jobhunter/frontend/src/lib/__tests__/analytics.test.ts` | Create | Unit tests for `trackEvent` |

### Staging Environment (Step 3)

| File | Action | Responsibility |
|------|--------|----------------|
| `.github/workflows/deploy-staging.yml` | Create | Deploy-to-staging workflow (on push to `main`, no manual gate) |
| `.github/workflows/deploy.yml` | Modify | Add "require staging health check" before prod deploy |
| `jobhunter/backend/.env.staging.example` | Create | Document required staging env vars |

---

## Task 1: Set Up Plausible Analytics Account

**Files:**
- None (external setup)

- [ ] **Step 1: Create Plausible Cloud site**

Go to https://plausible.io and create an account (or log in). Add site `hunter-job.com`. Copy the script tag — it will look like:

```html
<script defer data-domain="hunter-job.com" src="https://plausible.io/js/script.js"></script>
```

Note: Plausible is privacy-friendly (no cookies, GDPR-compliant by default, no cookie banner needed).

- [ ] **Step 2: Enable custom events**

In Plausible dashboard > Site Settings > Goals, add these custom goals:
- `Waitlist Signup` (Custom Event)
- `Pricing Click` (Custom Event)
- `CTA Click` (Custom Event)

These must exist in the dashboard before events can be tracked.

---

## Task 2: Add Plausible Script to Frontend

**Files:**
- Modify: `jobhunter/frontend/.env.production`
- Modify: `jobhunter/frontend/.env.local`
- Modify: `jobhunter/frontend/src/app/layout.tsx:31-55`
- Modify: `jobhunter/frontend/next.config.ts:13-22`

- [ ] **Step 1: Add env vars**

Append to `jobhunter/frontend/.env.production`:
```
NEXT_PUBLIC_PLAUSIBLE_DOMAIN=hunter-job.com
```

Append to `jobhunter/frontend/.env.local`:
```
NEXT_PUBLIC_PLAUSIBLE_DOMAIN=
```

Empty value disables the script in local dev (no noise in analytics).

- [ ] **Step 2: Add Plausible script to root layout**

In `jobhunter/frontend/src/app/layout.tsx`, add the import and script tag.

**Important:** The root layout has no explicit `<head>` tag (Next.js App Router manages `<head>` via metadata exports). Place the `<Script>` component as a direct child of `<body>`, after the existing providers.

```tsx
import Script from "next/script";

// Inside <body>, after the existing children/providers:
{process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && (
  <Script
    data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN}
    src="https://plausible.io/js/script.js"
    strategy="afterInteractive"
  />
)}
```

Note: Do NOT add `defer` — the Next.js `<Script>` component manages loading via `strategy`. Adding `defer` would be a no-op or cause a React DOM warning.

- [ ] **Step 3: Add CSP header for Plausible**

In `jobhunter/frontend/next.config.ts`, add a Content-Security-Policy header to the existing security headers array so Plausible's script and event endpoint are allowed:

```ts
{
  key: 'Content-Security-Policy',
  value: "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://plausible.io; connect-src 'self' https://plausible.io https://*.hunter-job.com;"
}
```

This prevents future CSP additions from silently blocking Plausible.

- [ ] **Step 4: Verify locally**

Run: `cd jobhunter/frontend && npm run dev`

Open http://localhost:3000 in browser, view page source. Confirm the Plausible script is **NOT** present (because `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` is empty locally).

- [ ] **Step 5: Commit**

```bash
git add jobhunter/frontend/.env.production jobhunter/frontend/.env.local jobhunter/frontend/src/app/layout.tsx jobhunter/frontend/next.config.ts
git commit -m "feat(frontend): add Plausible analytics script to root layout"
```

---

## Task 3: Create Analytics Event Helper

**Files:**
- Create: `jobhunter/frontend/src/lib/analytics.ts`
- Create: `jobhunter/frontend/src/lib/__tests__/analytics.test.ts`

- [ ] **Step 1: Write the failing test**

Create `jobhunter/frontend/src/lib/__tests__/analytics.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { trackEvent } from "../analytics";

describe("trackEvent", () => {
  beforeEach(() => {
    // Reset window.plausible before each test
    delete (window as any).plausible;
  });

  it("calls window.plausible when available", () => {
    const mock = vi.fn();
    (window as any).plausible = mock;

    trackEvent("Waitlist Signup", { source: "landing" });

    expect(mock).toHaveBeenCalledWith("Waitlist Signup", {
      props: { source: "landing" },
    });
  });

  it("does nothing when window.plausible is not available", () => {
    // Should not throw
    expect(() => trackEvent("Waitlist Signup")).not.toThrow();
  });

  it("works without props", () => {
    const mock = vi.fn();
    (window as any).plausible = mock;

    trackEvent("CTA Click");

    expect(mock).toHaveBeenCalledWith("CTA Click", { props: {} });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd jobhunter/frontend && npx vitest run src/lib/__tests__/analytics.test.ts`
Expected: FAIL — module `../analytics` does not exist

- [ ] **Step 3: Write implementation**

Create `jobhunter/frontend/src/lib/analytics.ts`:

```ts
/**
 * Track a custom event in Plausible Analytics.
 *
 * No-ops gracefully when Plausible is not loaded (local dev, ad-blockers).
 * See: https://plausible.io/docs/custom-event-goals
 */
export function trackEvent(
  name: string,
  props: Record<string, string | number | boolean> = {}
): void {
  if (typeof window !== "undefined" && typeof window.plausible === "function") {
    window.plausible(name, { props });
  }
}

// Extend Window interface for TypeScript
declare global {
  interface Window {
    plausible?: (
      event: string,
      options?: { props?: Record<string, string | number | boolean> }
    ) => void;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd jobhunter/frontend && npx vitest run src/lib/__tests__/analytics.test.ts`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add jobhunter/frontend/src/lib/analytics.ts jobhunter/frontend/src/lib/__tests__/analytics.test.ts
git commit -m "feat(frontend): add trackEvent analytics helper with tests"
```

---

## Task 4: Track Waitlist Signups

**Files:**
- Modify: `jobhunter/frontend/src/app/(marketing)/page.tsx:382-408`

- [ ] **Step 1: Add trackEvent import and call**

In `jobhunter/frontend/src/app/(marketing)/page.tsx`:

Add import at top:
```tsx
import { trackEvent } from "@/lib/analytics";
```

In the `handleWaitlist` function, after the line that sets `setStatus("success")` (around line 397), add:

```tsx
trackEvent("Waitlist Signup", { source: "landing_page" });
```

- [ ] **Step 2: Verify locally**

Run: `cd jobhunter/frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/(marketing)/page.tsx
git commit -m "feat(frontend): track waitlist signups in Plausible"
```

---

## Task 5: Track CTA and Pricing Clicks

**Files:**
- Modify: `jobhunter/frontend/src/app/(marketing)/page.tsx`

- [ ] **Step 1: Add click tracking to key CTAs**

Find the primary CTA buttons (e.g., "Get Started", "Join Waitlist" hero button, pricing tier buttons) and add `onClick` handlers:

```tsx
onClick={() => trackEvent("CTA Click", { location: "hero" })}
```

For pricing tier buttons:
```tsx
onClick={() => trackEvent("Pricing Click", { tier: "explorer" })}
```

Only add to the 3-4 most important buttons — don't over-instrument.

- [ ] **Step 2: Build and lint**

Run: `cd jobhunter/frontend && npm run build && npm run lint`
Expected: Both pass.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/(marketing)/page.tsx
git commit -m "feat(frontend): track CTA and pricing clicks in Plausible"
```

---

## Task 6: Create Railway Staging Service

**Files:**
- None (Railway dashboard + CLI)

Railway staging uses the same `railway.toml` as production — the service is linked via `railway service link` in the deploy workflow. No separate config file is needed.

- [ ] **Step 1: Create staging service in Railway**

In the Railway dashboard (project ID: `cc873661-d54c-44b4-acda-975758d196fe`):

1. Click **"+ New Service"** > **"Database"** > **PostgreSQL** — name it `postgres-staging`
2. Click **"+ New Service"** > **"Database"** > **Redis** — name it `redis-staging`
3. Click **"+ New Service"** > **"GitHub Repo"** > select `jobhunter` — name it `jobhunter-staging`

Set the `jobhunter-staging` service config:
- **Root directory:** `jobhunter/backend`
- **Build command:** same as production
- **Start command:** same as production

- [ ] **Step 2: Configure staging environment variables**

In `jobhunter-staging` service settings > Variables, set:

```
DATABASE_URL=<from postgres-staging service reference>
REDIS_URL=<from redis-staging service reference>
JWT_SECRET=<generate a unique staging secret>
OPENAI_API_KEY=<same as prod or a separate key with lower limits>
HUNTER_API_KEY=<same as prod>
SENTRY_ENVIRONMENT=staging
SENTRY_DSN=<same as prod — Sentry filters by environment>
APP_NAME=JobHunter AI (Staging)
FRONTEND_URL=https://staging.hunter-job.com
METRICS_SECRET=<generate unique>
ENABLE_RLS=false
```

- [ ] **Step 3: Generate a staging domain**

In `jobhunter-staging` > Settings > Networking > Generate Domain.

This gives a URL like `jobhunter-staging-xxxx.up.railway.app`. Optionally add a custom domain `api-staging.hunter-job.com` via Cloudflare.

- [ ] **Step 4: Verify staging health**

```bash
curl -sf https://jobhunter-staging-xxxx.up.railway.app/api/v1/health | python -m json.tool
```

Expected: `{"status": "healthy", "checks": {"database": "healthy", "redis": "healthy", ...}}`

---

## Task 7: Create Staging Deploy Workflow

**Files:**
- Create: `.github/workflows/deploy-staging.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/deploy-staging.yml`:

```yaml
name: Deploy Staging

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm i -g @railway/cli

      - name: Deploy backend to staging
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: |
          cd jobhunter/backend
          railway link ${{ vars.RAILWAY_PROJECT_ID }}
          railway service link jobhunter-staging
          railway up --detach

      - name: Wait for deploy and health check
        run: |
          echo "Waiting 60s for deploy to propagate..."
          sleep 60
          for i in $(seq 1 10); do
            STATUS=$(curl -sf "${{ vars.STAGING_API_URL }}/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unreachable")
            echo "Attempt $i: $STATUS"
            if [ "$STATUS" = "healthy" ]; then
              echo "Staging is healthy!"
              exit 0
            fi
            sleep 10
          done
          echo "::error::Staging health check failed after 10 attempts"
          exit 1
```

- [ ] **Step 2: Add GitHub repository variables**

In GitHub repo Settings > Secrets and variables > Actions > Variables, add:
- `RAILWAY_PROJECT_ID`: `cc873661-d54c-44b4-acda-975758d196fe`
- `STAGING_API_URL`: `https://jobhunter-staging-xxxx.up.railway.app/api/v1`

Ensure `RAILWAY_TOKEN` is already in Secrets (it should be, since prod deploy uses it).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy-staging.yml
git commit -m "ci: add staging deploy workflow with health check"
```

---

## Task 8: Gate Production Deploy on Staging

**Files:**
- Modify: `.github/workflows/deploy.yml:1-67`

- [ ] **Step 1: Add staging health check before prod deploy**

In `.github/workflows/deploy.yml`, add a `staging-gate` job and update the existing `deploy` job's `needs` array to include it. The existing `deploy` job has `needs: [ci]` — change it to `needs: [ci, staging-gate]`.

```yaml
jobs:
  staging-gate:
    runs-on: ubuntu-latest
    steps:
      - name: Verify staging is healthy
        run: |
          STATUS=$(curl -sf "${{ vars.STAGING_API_URL }}/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unreachable")
          if [ "$STATUS" != "healthy" ]; then
            echo "::error::Staging is not healthy ($STATUS). Deploy to staging first."
            exit 1
          fi
          echo "Staging is healthy. Proceeding to production deploy."

  deploy:
    needs: [ci, staging-gate]
    # ... rest of existing deploy job unchanged
```

**Important:** The existing `deploy` job has `needs: [ci]`. You must change it to `needs: [ci, staging-gate]` — do not replace, merge both dependencies.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: gate production deploy on staging health check"
```

---

## Task 9: Document Staging Setup

**Files:**
- Create: `jobhunter/backend/.env.staging.example`

- [ ] **Step 1: Create staging env example**

Create `jobhunter/backend/.env.staging.example`:

```bash
# Staging Environment Variables
# Copy to Railway staging service variables

DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0
JWT_SECRET=generate-a-unique-staging-secret-here
OPENAI_API_KEY=sk-your-staging-key
HUNTER_API_KEY=your-hunter-key
SENTRY_DSN=same-as-prod
SENTRY_ENVIRONMENT=staging
APP_NAME=JobHunter AI (Staging)
FRONTEND_URL=https://staging.hunter-job.com
METRICS_SECRET=generate-unique
ENABLE_RLS=false
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/backend/.env.staging.example
git commit -m "docs: add staging environment variable template"
```

---

## Task 10: Final Verification

- [ ] **Step 1: Run full frontend test suite**

```bash
cd jobhunter/frontend && npm run test && npm run lint && npm run build
```

Expected: All pass.

- [ ] **Step 2: Push and verify CI**

```bash
git push origin main
```

Watch CI: `gh run watch $(gh run list -L1 --json databaseId -q '.[0].databaseId') --exit-status`

Expected: All green (backend, frontend, e2e).

- [ ] **Step 3: Deploy and verify Plausible**

After deploy completes, visit https://hunter-job.com and check:
1. View page source — Plausible script tag is present
2. Open Plausible dashboard — page view appears within 30 seconds
3. Submit waitlist form — `Waitlist Signup` event appears in Plausible

---

## Summary

| What | Tool | Cost | Why |
|------|------|------|-----|
| Web analytics | Plausible Cloud | ~$9/mo (10k pageviews) | Privacy-friendly, no cookie banner, custom events |
| Staging backend | Railway | ~$5-10/mo (usage-based) | Mirrors prod, catches deploy issues before they hit users |
| Staging DB + Redis | Railway | Included in plan | Isolated data, safe to test migrations |
| Staging frontend | Cloudflare Pages | Free tier | Separate project, same repo |

## Notes on `.env.staging`

Next.js does **not** auto-load `.env.staging` — it only loads `.env.local`, `.env.development`, `.env.production`, and `.env.test`. For the frontend staging deploy, set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` directly in the Cloudflare Pages project environment variables. No `.env.staging` file is needed.
