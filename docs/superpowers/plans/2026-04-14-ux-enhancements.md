# UX Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 4 UX improvements from `docs/superpowers/specs/2026-04-13-ux-enhancements-design.md` — progress indicators, contextual skeletons, actionable empty states, and consistent side panels.

**Architecture:** Two new shared components (`OperationProgress`, `PanelSection`) used across ~8 pages. Per-page loading skeletons in each route's `loading.tsx`. All empty states get CTAs. Three drawer panels refactored to use `PanelSection`. No backend changes.

**Tech Stack:** Next.js 15, React 19, TanStack Query v5, shadcn/ui, Tailwind v4, Vitest + testing-library + happy-dom

---

## File Structure

### New Files

| File | Responsibility |
|------|----------------|
| `jobhunter/frontend/src/components/shared/operation-progress.tsx` | Inline progress indicator for long-running operations |
| `jobhunter/frontend/src/components/shared/panel-section.tsx` | Grouped section wrapper for side panels |
| `jobhunter/frontend/src/components/shared/__tests__/operation-progress.test.tsx` | Unit tests |
| `jobhunter/frontend/src/components/shared/__tests__/panel-section.test.tsx` | Unit tests |

### Modified `loading.tsx` Files

All in `jobhunter/frontend/src/app/(dashboard)/*/loading.tsx`:
- `page.tsx` sibling `loading.tsx` for: dashboard, companies, companies/[id], resume, outreach, interview-prep, apply, approvals, analytics, settings, admin, admin/waitlist

### Modified Component Files

- `jobhunter/frontend/src/components/companies/dossier-view.tsx` — use `OperationProgress`
- `jobhunter/frontend/src/app/(dashboard)/companies/page.tsx` — use `OperationProgress` for discovery, add empty state CTAs
- `jobhunter/frontend/src/app/(dashboard)/resume/page.tsx` — use `OperationProgress` for parsing
- `jobhunter/frontend/src/app/(dashboard)/interview-prep/page.tsx` — use `OperationProgress` for generation, add empty state CTA
- `jobhunter/frontend/src/app/(dashboard)/apply/page.tsx` — use `OperationProgress` for analysis
- `jobhunter/frontend/src/app/(dashboard)/analytics/page.tsx` — add empty state CTA
- `jobhunter/frontend/src/app/(dashboard)/approvals/page.tsx` — add empty state CTA, refactor detail sheet
- `jobhunter/frontend/src/components/admin/user-detail-drawer.tsx` — use `PanelSection`
- `jobhunter/frontend/src/components/incidents/incident-form.tsx` — use `PanelSection`

---

# Section A — Progress Feedback

## Task 1: Create `OperationProgress` component

**Files:**
- Create: `jobhunter/frontend/src/components/shared/operation-progress.tsx`
- Create: `jobhunter/frontend/src/components/shared/__tests__/operation-progress.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `jobhunter/frontend/src/components/shared/__tests__/operation-progress.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { OperationProgress } from "../operation-progress";

describe("OperationProgress", () => {
  it("renders single-state pending with label and progressbar role", () => {
    render(<OperationProgress status="pending" label="Discovering companies" />);
    expect(screen.getByText("Discovering companies")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders multi-state steps with current step highlighted", () => {
    render(
      <OperationProgress
        status="in_progress"
        label="Researching"
        steps={[
          { key: "pending", label: "Queued" },
          { key: "in_progress", label: "Researching" },
          { key: "completed", label: "Done" },
        ]}
      />
    );
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.getByText("Researching")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("renders failed state with error message and retry button", () => {
    const onRetry = vi.fn();
    render(
      <OperationProgress
        status="failed"
        label="Research failed"
        errorMessage="Something broke"
        onRetry={onRetry}
      />
    );
    expect(screen.getByText("Research failed")).toBeInTheDocument();
    expect(screen.getByText("Something broke")).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", { name: /retry/i });
    retryBtn.click();
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders completed state with success message", () => {
    render(<OperationProgress status="completed" label="All done" />);
    expect(screen.getByText("All done")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd jobhunter/frontend && npm run test -- operation-progress`
Expected: FAIL — `Cannot find module '../operation-progress'`

- [ ] **Step 3: Implement `OperationProgress`**

Create `jobhunter/frontend/src/components/shared/operation-progress.tsx`:

```tsx
"use client";

import { Loader2, AlertTriangle, CheckCircle2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface OperationStep {
  key: string;
  label: string;
}

export interface OperationProgressProps {
  status: string;
  label: string;
  steps?: OperationStep[];
  onRetry?: () => void;
  errorMessage?: string;
  className?: string;
}

const FAILED_STATES = ["failed"];
const COMPLETED_STATES = ["completed", "analyzed"];

function isFailed(status: string): boolean {
  return FAILED_STATES.includes(status);
}

function isCompleted(status: string): boolean {
  return COMPLETED_STATES.includes(status);
}

export function OperationProgress({
  status,
  label,
  steps,
  onRetry,
  errorMessage,
  className,
}: OperationProgressProps) {
  if (isFailed(status)) {
    return (
      <Card className={className} role="status" aria-live="polite">
        <CardContent className="p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-destructive mt-0.5 flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <p className="font-medium text-sm">{label}</p>
              {errorMessage && (
                <p className="text-sm text-muted-foreground">{errorMessage}</p>
              )}
              {onRetry && (
                <Button variant="outline" size="sm" onClick={onRetry} className="mt-2">
                  <RotateCcw className="mr-2 h-3.5 w-3.5" />
                  Retry
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isCompleted(status)) {
    return (
      <Card className={className} role="status" aria-live="polite">
        <CardContent className="p-6">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-chart-3 flex-shrink-0" />
            <p className="font-medium text-sm">{label}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // In-progress / pending
  if (steps && steps.length > 0) {
    const currentIndex = steps.findIndex((s) => s.key === status);
    const activeIndex = currentIndex >= 0 ? currentIndex : 0;

    return (
      <Card className={className} role="status" aria-live="polite">
        <CardContent className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <Loader2 className="h-5 w-5 animate-spin text-primary flex-shrink-0" />
            <p className="font-medium text-sm" aria-live="polite">{label}</p>
          </div>
          <div
            className="flex items-center gap-2"
            role="progressbar"
            aria-valuenow={activeIndex + 1}
            aria-valuemin={1}
            aria-valuemax={steps.length}
            aria-label={`Step ${activeIndex + 1} of ${steps.length}`}
          >
            {steps.map((step, i) => (
              <div key={step.key} className="flex items-center gap-2 flex-1">
                <div
                  className={cn(
                    "h-2 flex-1 rounded-full transition-colors",
                    i < activeIndex && "bg-chart-3",
                    i === activeIndex && "bg-primary",
                    i > activeIndex && "bg-muted"
                  )}
                />
              </div>
            ))}
          </div>
          <div className="mt-2 flex justify-between text-xs text-muted-foreground">
            {steps.map((step, i) => (
              <span
                key={step.key}
                className={cn(
                  i === activeIndex && "text-primary font-medium",
                  i < activeIndex && "text-chart-3"
                )}
              >
                {step.label}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Single-state in progress
  return (
    <Card className={className} role="status" aria-live="polite">
      <CardContent className="p-6">
        <div className="flex items-center gap-3 mb-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary flex-shrink-0" />
          <p className="font-medium text-sm">{label}</p>
        </div>
        <div
          className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
          role="progressbar"
          aria-label={label}
        >
          <div className="h-full w-1/3 rounded-full bg-primary animate-[indeterminate_1.5s_ease-in-out_infinite]" />
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd jobhunter/frontend && npm run test -- operation-progress`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add jobhunter/frontend/src/components/shared/operation-progress.tsx jobhunter/frontend/src/components/shared/__tests__/operation-progress.test.tsx
git commit -m "feat(frontend): add shared OperationProgress component"
```

---

## Task 2: Use `OperationProgress` in Company Discovery

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/companies/page.tsx:302-315`

- [ ] **Step 1: Read the current discover panel footer**

Already verified at lines 302-315:
```tsx
<div className="mt-4 flex justify-end">
  <Button onClick={handleDiscover} disabled={discoverMutation.isPending}>
    {discoverMutation.isPending ? (
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
    ) : (
      <Sparkles className="mr-2 h-4 w-4" />
    )}
    {discoverMutation.isPending ? "Discovering…" : "Run Discovery"}
  </Button>
</div>
```

- [ ] **Step 2: Replace with progress indicator**

In `jobhunter/frontend/src/app/(dashboard)/companies/page.tsx`, add import near top:
```tsx
import { OperationProgress } from "@/components/shared/operation-progress";
```

Replace lines 303-314 with:
```tsx
<div className="mt-4 space-y-3">
  {discoverMutation.isPending && (
    <OperationProgress status="in_progress" label="Discovering companies that match your profile…" />
  )}
  <div className="flex justify-end">
    <Button onClick={handleDiscover} disabled={discoverMutation.isPending}>
      {discoverMutation.isPending ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      ) : (
        <Sparkles className="mr-2 h-4 w-4" />
      )}
      {discoverMutation.isPending ? "Discovering…" : "Run Discovery"}
    </Button>
  </div>
</div>
```

- [ ] **Step 3: Verify build and manual test**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep -E "companies/page|operation-progress"`
Expected: no new errors from these files.

- [ ] **Step 4: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/companies/page.tsx
git commit -m "feat(frontend): show OperationProgress during company discovery"
```

---

## Task 3: Use `OperationProgress` in Company Research (dossier)

**Files:**
- Modify: `jobhunter/frontend/src/components/companies/dossier-view.tsx:23-31`

- [ ] **Step 1: Replace "Researching company..." block**

In `jobhunter/frontend/src/components/companies/dossier-view.tsx`, add import at the top:
```tsx
import { OperationProgress } from "@/components/shared/operation-progress";
```

Replace lines 23-31 with:
```tsx
  if (researchStatus === "pending" || researchStatus === "in_progress") {
    return (
      <OperationProgress
        status={researchStatus}
        label="Researching company"
        steps={[
          { key: "pending", label: "Queued" },
          { key: "in_progress", label: "Researching" },
          { key: "completed", label: "Done" },
        ]}
      />
    );
  }
```

- [ ] **Step 2: Verify build**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep dossier-view`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/components/companies/dossier-view.tsx
git commit -m "feat(frontend): show OperationProgress during company research"
```

---

## Task 4: Use `OperationProgress` in Resume Parsing

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/resume/page.tsx:279-293`

- [ ] **Step 1: Replace processing card**

Add import:
```tsx
import { OperationProgress } from "@/components/shared/operation-progress";
```

Replace lines 279-293 (the entire `{!isLoading && uploadedRecently && !hasDna && (...)}` block) with:
```tsx
      {!isLoading && uploadedRecently && !hasDna && (
        <OperationProgress
          status="in_progress"
          label="Processing your resume and generating DNA profile"
        />
      )}
```

- [ ] **Step 2: Verify build**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep resume/page`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/resume/page.tsx
git commit -m "feat(frontend): show OperationProgress during resume parsing"
```

---

## Task 5: Use `OperationProgress` in Interview Generation

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/interview-prep/page.tsx:344-350`

- [ ] **Step 1: Replace skeleton loaders for active generation**

Add import:
```tsx
import { OperationProgress } from "@/components/shared/operation-progress";
```

Replace lines 344-350 (the `{generatePrep.isPending && activeTab === pt.value && (...)}` block) with:
```tsx
              {generatePrep.isPending && activeTab === pt.value && (
                <OperationProgress
                  status="in_progress"
                  label={`Generating ${pt.label} content…`}
                />
              )}
```

- [ ] **Step 2: Verify build**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep interview-prep/page`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/interview-prep/page.tsx
git commit -m "feat(frontend): show OperationProgress during interview generation"
```

---

## Task 6: Use `OperationProgress` in Job Analysis

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/apply/page.tsx:465-478`

- [ ] **Step 1: Replace analysis loading card**

Add import:
```tsx
import { OperationProgress } from "@/components/shared/operation-progress";
```

Replace lines 465-478 (the `{selectedPostingId && !loadingAnalysis && !analysis && !analysisError && (...)}` block) with:
```tsx
          {selectedPostingId && !loadingAnalysis && !analysis && !analysisError && (
            <OperationProgress
              status="in_progress"
              label="Analyzing job posting…"
            />
          )}
```

- [ ] **Step 2: Verify build**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep apply/page`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/apply/page.tsx
git commit -m "feat(frontend): show OperationProgress during job analysis"
```

---

# Section B — Contextual Loading Skeletons

For each page below, replace the current `loading.tsx` (if it uses generic `PageSkeleton`) with a custom skeleton matching the real page layout.

## Task 7: Dashboard loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/loading.tsx` (if exists) or `jobhunter/frontend/src/app/(dashboard)/dashboard/loading.tsx`

- [ ] **Step 1: Locate the dashboard loading file**

Run: `ls jobhunter/frontend/src/app/\(dashboard\)/loading.tsx jobhunter/frontend/src/app/\(dashboard\)/dashboard/loading.tsx 2>&1`

The dashboard page lives at `src/app/(dashboard)/page.tsx`, so `loading.tsx` belongs next to it. If it doesn't exist, create it.

- [ ] **Step 2: Write the skeleton**

Create/replace `jobhunter/frontend/src/app/(dashboard)/loading.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading dashboard">
      <Skeleton className="h-9 w-64" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-16" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-lg border p-6 space-y-4">
          <Skeleton className="h-6 w-48" />
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
        <div className="rounded-lg border p-6 space-y-3">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-20 w-full" />
        </div>
      </div>
      <div className="rounded-lg border p-6 space-y-3">
        <Skeleton className="h-6 w-48" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep dashboard`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/loading.tsx
git commit -m "feat(frontend): custom dashboard loading skeleton"
```

---

## Task 8: Companies loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/companies/loading.tsx`

- [ ] **Step 1: Write the skeleton**

Create/replace the file:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function CompaniesLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading companies">
      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-48" />
        <div className="ml-auto flex gap-2">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-7 w-28" />
        ))}
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Skeleton className="h-9 flex-1 max-w-xs" />
        <Skeleton className="h-9 w-32" />
        <div className="flex gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-20" />
          ))}
        </div>
      </div>
      <div className="rounded-lg border">
        <div className="border-b p-3 flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-4 flex-1" />
          ))}
        </div>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="border-b p-3 flex gap-4 items-center">
            {Array.from({ length: 5 }).map((_, j) => (
              <Skeleton key={j} className="h-5 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep companies`
Expected: no new errors.

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/companies/loading.tsx
git commit -m "feat(frontend): custom companies loading skeleton"
```

---

## Task 9: Company Detail loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/companies/[id]/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function CompanyDetailLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading company details">
      <Skeleton className="h-5 w-40" />
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-6 w-20" />
          </div>
          <div className="flex gap-4">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-24" />
          </div>
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>
      <div className="flex gap-2 border-b">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-24" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-6 space-y-3">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/companies/\[id\]/loading.tsx
git commit -m "feat(frontend): custom company detail loading skeleton"
```

---

## Task 10: Resume loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/resume/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function ResumeLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading resume">
      <Skeleton className="h-9 w-48" />
      <Skeleton className="h-32 w-full rounded-lg" />
      <div className="flex gap-2 border-b">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-24" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border p-6 space-y-4">
          <Skeleton className="h-6 w-40" />
          <div className="flex items-center justify-center">
            <Skeleton className="h-32 w-32 rounded-full" />
          </div>
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-5 w-full" />
            ))}
          </div>
        </div>
        <div className="rounded-lg border p-6 space-y-3">
          <Skeleton className="h-6 w-32" />
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-7 w-20" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/resume/loading.tsx
git commit -m "feat(frontend): custom resume loading skeleton"
```

---

## Task 11: Outreach loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/outreach/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function OutreachLoading() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading outreach">
      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-9 w-32" />
      </div>
      <div className="flex gap-4">
        <div className="w-[400px] border rounded-lg overflow-hidden">
          <div className="p-3 border-b">
            <Skeleton className="h-9 w-full" />
          </div>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="p-3 border-b flex gap-3 items-start">
              <Skeleton className="h-2 w-2 rounded-full mt-2" />
              <Skeleton className="h-8 w-8 rounded-full" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
              </div>
              <Skeleton className="h-3 w-12" />
            </div>
          ))}
        </div>
        <div className="flex-1 border rounded-lg p-6 space-y-4">
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-4 w-48" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/outreach/loading.tsx
git commit -m "feat(frontend): custom outreach loading skeleton"
```

---

## Task 12: Interview Prep loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/interview-prep/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function InterviewPrepLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading interview prep">
      <Skeleton className="h-9 w-48" />
      <Skeleton className="h-10 w-80" />
      <div className="rounded-lg border p-6">
        <Skeleton className="h-5 w-40 mb-4" />
        <div className="flex gap-3 flex-wrap">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex flex-col items-center gap-2">
              <Skeleton className="h-12 w-12 rounded-full" />
              <Skeleton className="h-3 w-16" />
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded" />
            <div className="flex-1 space-y-1.5">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
            <Skeleton className="h-6 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/interview-prep/loading.tsx
git commit -m "feat(frontend): custom interview-prep loading skeleton"
```

---

## Task 13: Apply loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/apply/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function ApplyLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading apply page">
      <Skeleton className="h-9 w-48" />
      <Skeleton className="h-10 w-full max-w-2xl" />
      <div className="grid gap-4 md:grid-cols-[320px_1fr]">
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-lg border p-4 space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-6 w-20" />
            </div>
          ))}
        </div>
        <div className="rounded-lg border p-6 space-y-4">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/apply/loading.tsx
git commit -m "feat(frontend): custom apply loading skeleton"
```

---

## Task 14: Approvals loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/approvals/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function ApprovalsLoading() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading approvals">
      <Skeleton className="h-9 w-40" />
      <div className="flex gap-2">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-9 w-32" />
      </div>
      <div className="rounded-lg border">
        <div className="border-b p-3 flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-4 flex-1" />
          ))}
        </div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="border-b p-3 flex gap-4 items-center">
            <Skeleton className="h-4 w-4" />
            {Array.from({ length: 4 }).map((_, j) => (
              <Skeleton key={j} className="h-5 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/approvals/loading.tsx
git commit -m "feat(frontend): custom approvals loading skeleton"
```

---

## Task 15: Analytics loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/analytics/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function AnalyticsLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading analytics">
      <div className="flex items-center justify-between">
        <Skeleton className="h-9 w-40" />
        <div className="flex gap-2">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>
      <div className="grid gap-3 grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-16" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border p-6 space-y-3">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-[250px] w-full" />
        </div>
        <div className="rounded-lg border p-6 space-y-3">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-[250px] w-full" />
        </div>
      </div>
      <div className="rounded-lg border p-6 space-y-3">
        <Skeleton className="h-6 w-40" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-md border-l-4 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-5 w-16" />
            </div>
            <Skeleton className="h-4 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/analytics/loading.tsx
git commit -m "feat(frontend): custom analytics loading skeleton"
```

---

## Task 16: Settings loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/settings/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function SettingsLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading settings">
      <Skeleton className="h-9 w-32" />
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="rounded-lg border p-6 space-y-4">
          <Skeleton className="h-6 w-48" />
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, j) => (
              <div key={j} className="space-y-1.5">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/settings/loading.tsx
git commit -m "feat(frontend): custom settings loading skeleton"
```

---

## Task 17: Admin loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/admin/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function AdminLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading admin dashboard">
      <Skeleton className="h-9 w-48" />
      <div className="flex gap-2 border-b">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-24" />
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-16" />
          </div>
        ))}
      </div>
      <div className="rounded-lg border p-6 space-y-3">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-20 w-full" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border p-6 space-y-3">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-[300px] w-full" />
        </div>
        <div className="rounded-lg border p-6 space-y-3">
          <Skeleton className="h-6 w-48" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/admin/loading.tsx
git commit -m "feat(frontend): custom admin loading skeleton"
```

---

## Task 18: Admin Waitlist loading skeleton

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/admin/waitlist/loading.tsx`

- [ ] **Step 1: Write the skeleton**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function WaitlistLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading waitlist">
      <Skeleton className="h-9 w-40" />
      <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-12" />
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-9 w-40" />
      </div>
      <div className="rounded-lg border">
        <div className="border-b p-3 flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-4 flex-1" />
          ))}
        </div>
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="border-b p-3 flex gap-4 items-center">
            <Skeleton className="h-4 w-4" />
            {Array.from({ length: 4 }).map((_, j) => (
              <Skeleton key={j} className="h-5 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/admin/waitlist/loading.tsx
git commit -m "feat(frontend): custom waitlist loading skeleton"
```

---

# Section C — Actionable Empty States

## Task 19: Add CTA to Analytics empty state

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/analytics/page.tsx:322-327`

- [ ] **Step 1: Read current empty state**

```tsx
<EmptyState
  title="No data yet"
  description="Start discovering companies and sending outreach to see your analytics dashboard come to life."
/>
```

- [ ] **Step 2: Add the action prop**

Add import at top if missing:
```tsx
import { useRouter } from "next/navigation";
```

In the component function body, add:
```tsx
const router = useRouter();
```

Replace the `<EmptyState>` at lines 322-327 with:
```tsx
<EmptyState
  title="No data yet"
  description="Start discovering companies and sending outreach to see your analytics dashboard come to life."
  action={{
    label: "Discover Companies",
    onClick: () => router.push("/companies"),
  }}
/>
```

- [ ] **Step 3: Verify and commit**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep analytics/page`
Expected: no new errors.

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/analytics/page.tsx
git commit -m "feat(frontend): add CTA to analytics empty state"
```

---

## Task 20: Add CTA to Approvals empty state

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/approvals/page.tsx:295-305`

- [ ] **Step 1: Add router import if missing**

```tsx
import { useRouter } from "next/navigation";
```

In the component function body:
```tsx
const router = useRouter();
```

- [ ] **Step 2: Add action prop to empty state**

Add to the existing `<EmptyState>`:
```tsx
action={{
  label: "Go to Companies",
  onClick: () => router.push("/companies"),
}}
```

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/approvals/page.tsx
git commit -m "feat(frontend): add CTA to approvals empty state"
```

---

## Task 21: Add top-level CTA to Interview Prep empty state

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/interview-prep/page.tsx:295-301`

- [ ] **Step 1: Add router import**

```tsx
import { useRouter } from "next/navigation";
```

```tsx
const router = useRouter();
```

- [ ] **Step 2: Add action to the top-level empty state**

Replace the existing empty state at lines 295-301 with:
```tsx
<EmptyState
  title="Select a company to begin"
  description="Choose an approved company above to generate interview prep materials or start a mock interview."
  action={{
    label: "Browse Companies",
    onClick: () => router.push("/companies"),
  }}
/>
```

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/interview-prep/page.tsx
git commit -m "feat(frontend): add CTA to interview prep empty state"
```

---

## Task 22: Add CTA to Companies empty state

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/companies/page.tsx:379-386`

The spec wants a conditional CTA based on resume existence. We'll use the existing resume query.

- [ ] **Step 1: Check what resume query exists**

Run: `grep -n "useResume\|useDnaProfile\|useCandidateDna" jobhunter/frontend/src/app/\(dashboard\)/companies/page.tsx jobhunter/frontend/src/lib/hooks/ 2>&1 | head`

- [ ] **Step 2: Add conditional CTA**

Replace the existing empty state at lines 379-386 with:
```tsx
<EmptyState
  title="No companies yet"
  description="Upload a resume and discover companies, or add one manually."
  action={{
    label: "Discover Companies",
    onClick: () => setDiscoverOpen(true),
  }}
/>
```

Note: The spec mentions a conditional "Upload Resume" variant based on resume state. This plan ships the single "Discover Companies" CTA only, as it works regardless of resume state (the discover flow already prompts for resume if missing). The conditional variant is out of scope.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/companies/page.tsx
git commit -m "feat(frontend): add CTA to companies empty state"
```

---

# Section D — Side Panel Consistency

## Task 23: Create `PanelSection` component

**Files:**
- Create: `jobhunter/frontend/src/components/shared/panel-section.tsx`
- Create: `jobhunter/frontend/src/components/shared/__tests__/panel-section.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PanelSection } from "../panel-section";
import { Calendar } from "lucide-react";

describe("PanelSection", () => {
  it("renders title and children", () => {
    render(
      <PanelSection title="Details">
        <p>Content here</p>
      </PanelSection>
    );
    expect(screen.getByText("Details")).toBeInTheDocument();
    expect(screen.getByText("Content here")).toBeInTheDocument();
  });

  it("has region role with aria-label", () => {
    render(
      <PanelSection title="Activity">
        <p>x</p>
      </PanelSection>
    );
    const region = screen.getByRole("region", { name: "Activity" });
    expect(region).toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    const { container } = render(
      <PanelSection title="Details" icon={Calendar}>
        <p>x</p>
      </PanelSection>
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests (expect fail)**

Run: `cd jobhunter/frontend && npm run test -- panel-section`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `PanelSection`**

Create `jobhunter/frontend/src/components/shared/panel-section.tsx`:

```tsx
"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PanelSectionProps {
  title: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
}

export function PanelSection({ title, icon: Icon, children, className }: PanelSectionProps) {
  return (
    <section
      role="region"
      aria-label={title}
      className={cn("pt-5 first:pt-0 first:border-t-0 border-t", className)}
    >
      <div className="flex items-center gap-2 mb-3">
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
        <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
      </div>
      {children}
    </section>
  );
}
```

- [ ] **Step 4: Run tests (expect pass)**

Run: `cd jobhunter/frontend && npm run test -- panel-section`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add jobhunter/frontend/src/components/shared/panel-section.tsx jobhunter/frontend/src/components/shared/__tests__/panel-section.test.tsx
git commit -m "feat(frontend): add shared PanelSection component"
```

---

## Task 24: Refactor User Details drawer to use `PanelSection`

**Files:**
- Modify: `jobhunter/frontend/src/components/admin/user-detail-drawer.tsx`

- [ ] **Step 1: Read the current file fully**

Run: `cat jobhunter/frontend/src/components/admin/user-detail-drawer.tsx | head -340`

Note the existing sections: profile info, details rows, plan tier (with edit mode), stats cards, action buttons, two AlertDialogs.

- [ ] **Step 2: Add `PanelSection` import and icon imports**

At the top of the file, add to imports:
```tsx
import { PanelSection } from "@/components/shared/panel-section";
import { Calendar, BarChart3, Settings } from "lucide-react";
```

- [ ] **Step 3: Wrap the three content sections**

Find the section after the Profile info block (name/email/badges + Separator) in `SheetContent`. Wrap:

1. The Details rows (Joined, Invited by, Invite code) + plan tier row in `<PanelSection title="Details" icon={Calendar}>`
2. The stats grid (Companies / Messages) in `<PanelSection title="Activity" icon={BarChart3}>`
3. The action buttons (Toggle admin / Suspend / Delete) in `<PanelSection title="Actions" icon={Settings}>`

Remove the existing `<Separator />` components between these — `PanelSection` provides its own top border.

Keep both AlertDialogs as-is (they render outside the sections).

- [ ] **Step 4: Verify build**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep user-detail-drawer`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add jobhunter/frontend/src/components/admin/user-detail-drawer.tsx
git commit -m "feat(frontend): refactor user detail drawer with PanelSection"
```

---

## Task 25: Refactor Incident Form to use `PanelSection`

**Files:**
- Modify: `jobhunter/frontend/src/components/incidents/incident-form.tsx`

- [ ] **Step 1: Read current file**

Run: `cat jobhunter/frontend/src/components/incidents/incident-form.tsx`

Note the form sections: Category radio group, Title input, Description textarea, Attachments, Submit button.

- [ ] **Step 2: Add imports**

```tsx
import { PanelSection } from "@/components/shared/panel-section";
import { Tag, FileText, Paperclip } from "lucide-react";
```

- [ ] **Step 3: Wrap sections**

Inside the form, wrap the existing sections:

1. Category RadioGroup → `<PanelSection title="Category" icon={Tag}>`
2. Title + Description fields → `<PanelSection title="Details" icon={FileText}>` (combine them; bump internal `space-y-2` to `space-y-4`)
3. Attachments area → `<PanelSection title="Attachments" icon={Paperclip}>`

Keep the Submit button outside `PanelSection` at the form bottom. Remove the header `mt-6` since PanelSection already provides top padding.

Add `sm:max-w-xl` for width consistency (down from `sm:max-w-2xl`) — but keep `sm:max-w-2xl` if the form truly needs it. Per spec, Incident Form is the wide exception, so keep `sm:max-w-2xl`.

- [ ] **Step 4: Verify build**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep incident-form`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add jobhunter/frontend/src/components/incidents/incident-form.tsx
git commit -m "feat(frontend): refactor incident form with PanelSection"
```

---

## Task 26: Refactor Approvals detail sheet to use `PanelSection`

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/approvals/page.tsx`

- [ ] **Step 1: Locate the detail Sheet**

Run: `grep -n "SheetContent" jobhunter/frontend/src/app/\(dashboard\)/approvals/page.tsx`

- [ ] **Step 2: Add imports**

```tsx
import { PanelSection } from "@/components/shared/panel-section";
import { User, Brain, Mail, CheckCircle } from "lucide-react";
```

- [ ] **Step 3: Wrap the detail sections**

Inside the `SheetContent`, wrap the existing content:

1. Contact info (name, email, company) → `<PanelSection title="Contact" icon={User}>`
2. AI Reasoning block → `<PanelSection title="AI Reasoning" icon={Brain}>`
3. Subject + Body → `<PanelSection title="Message" icon={Mail}>`
4. Approve / Reject buttons → `<PanelSection title="Actions" icon={CheckCircle}>`

Keep the status badges header outside `PanelSection`. Remove any hand-rolled dividers since PanelSection provides them.

Set width to `sm:max-w-xl` on `SheetContent` for consistency.

- [ ] **Step 4: Verify build**

Run: `cd jobhunter/frontend && npx tsc --noEmit 2>&1 | grep approvals/page`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/approvals/page.tsx
git commit -m "feat(frontend): refactor approvals detail sheet with PanelSection"
```

---

# Final Verification

## Task 27: Run full frontend test suite

- [ ] **Step 1: Run vitest**

Run: `cd jobhunter/frontend && npm run test -- --run`
Expected: All unit tests PASS, including new ones for `OperationProgress` (4 tests) and `PanelSection` (3 tests).

- [ ] **Step 2: Run type check**

Run: `cd jobhunter/frontend && npx tsc --noEmit`
Expected: No new errors beyond the pre-existing lucide `Linkedin` import errors.

- [ ] **Step 3: Build**

Run: `cd jobhunter/frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Manual visual check**

Start dev server: `cd jobhunter/frontend && npm run dev`

Visit each of these and confirm visuals:
- `/companies` — trigger discovery, see `OperationProgress` card while pending
- `/companies/{id}` — if research is pending, see multi-step progress
- `/resume` — upload a resume, see parsing progress
- `/apply` — analyze a job, see progress card
- `/analytics` — if empty, see "Discover Companies" CTA
- `/approvals` — if empty, see "Go to Companies" CTA
- `/admin` — open User Details drawer, see `PanelSection` grouping
- Click the floating incident button — see `PanelSection` grouping in the form
- Refresh each page to see custom skeletons matching page layout

If any visual issue found, fix inline and commit with message `fix(frontend): <issue>`.

- [ ] **Step 5: Final push**

```bash
git push origin main
```
