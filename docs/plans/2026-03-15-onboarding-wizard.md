# Onboarding Wizard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-step onboarding wizard (Welcome → Profile → Resume) that guides new users through setup, followed by a live guided tour on the actual dashboard — spotlighting each panel with explanations so users understand every feature.

**Architecture:** New `(onboarding)` route group with a 3-step wizard (Welcome → Profile → Resume). The wizard's final step completes onboarding and redirects to the dashboard, where a **spotlight tour overlay** walks the user through each real panel — sidebar nav items, stats cards, pipeline overview, and recent companies. Backend adds `onboarding_completed_at` column and a `tour_completed_at` column to Candidate model. Auth guards redirect un-onboarded users from dashboard to `/onboarding`. **Resume support:** The wizard computes the initial step from user data state (profile fields filled → skip to Resume, DNA exists → skip straight to dashboard tour) so users who close mid-wizard resume from where they left off. Dashboard elements get `data-tour` attributes for the spotlight overlay to anchor to.

**Tech Stack:** Next.js 16, Tailwind CSS v4 (tw-animate-css), shadcn/ui, react-hook-form + zod, TanStack Query, FastAPI, SQLAlchemy async, Alembic, pytest

---

## File Structure

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `jobhunter/backend/alembic/versions/023_add_onboarding_and_tour.py` | Migration: adds `onboarding_completed_at` and `tour_completed_at` columns to `candidates` table |

### Backend — Modified Files
| File | Change |
|------|--------|
| `jobhunter/backend/app/models/candidate.py` | Add `onboarding_completed_at` and `tour_completed_at` fields to Candidate model |
| `jobhunter/backend/app/schemas/auth.py` | Add `onboarding_completed_at`, `onboarding_completed`, `tour_completed_at`, `tour_completed` to CandidateResponse |
| `jobhunter/backend/app/api/auth.py` | Add `POST /auth/complete-onboarding` and `POST /auth/complete-tour` endpoints; update all CandidateResponse construction sites |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `src/app/(onboarding)/layout.tsx` | Auth guard + clean full-page layout (no sidebar) |
| `src/app/(onboarding)/onboarding/page.tsx` | Wizard orchestrator — manages step state, renders shell + step components |
| `src/components/onboarding/wizard-shell.tsx` | Outer wrapper: step indicator at top, content area, nav buttons at bottom |
| `src/components/onboarding/step-indicator.tsx` | Horizontal stepper with checkmarks, current highlight, connecting lines |
| `src/components/onboarding/step-welcome.tsx` | Welcome screen with app overview and step preview cards |
| `src/components/onboarding/step-profile.tsx` | Profile form (headline, location, target roles/industries/locations, salary) |
| `src/components/onboarding/step-email-verify.tsx` | Email verification nudge — check inbox prompt with resend button |
| `src/components/onboarding/step-resume.tsx` | Resume upload + DNA processing state |
| `src/components/onboarding/tag-input.tsx` | Reusable multi-value tag input component |
| `src/lib/schemas/onboarding.ts` | Zod schema for profile step |
| `src/components/dashboard/tour-overlay.tsx` | Spotlight tour overlay — highlights dashboard panels one by one with tooltips |
| `src/components/dashboard/tour-spotlight.tsx` | Spotlight primitive — renders dimmed backdrop with cutout around target element |
| `src/components/dashboard/tour-tooltip.tsx` | Tour tooltip — positioned next to spotlight, shows title/description/nav buttons |
| `src/lib/tour-steps.ts` | Tour step definitions — data-tour selectors, titles, descriptions for each panel |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `src/providers/auth-provider.tsx` | Add `isOnboarded`, `isTourCompleted`, `completeOnboarding()`, `completeTour()`, `resetTour()` |
| `src/lib/api/auth.ts` | Add `completeOnboarding()`, `completeTour()` API calls |
| `src/lib/types.ts` | Add `onboarding_completed_at`, `onboarding_completed`, `tour_completed_at`, `tour_completed` to `CandidateResponse` |
| `src/app/(auth)/layout.tsx` | Redirect authenticated users to `/onboarding` if not onboarded |
| `src/app/(dashboard)/layout.tsx` | Redirect to `/onboarding` if authenticated but not onboarded; render `TourOverlay` if tour not completed |
| `src/app/(dashboard)/dashboard/page.tsx` | Add `data-tour` attributes to panels (stats, pipeline, actions, companies table) |
| `src/app/(dashboard)/settings/page.tsx` | Add "Replay guided tour" button |
| `src/components/layout/sidebar.tsx` | Add `data-tour` attributes to nav items |

### Frontend paths are relative to `jobhunter/frontend/`

---

## Chunk 1: Backend — Model, Migration, Schema, Endpoint

### Task 1: Add `onboarding_completed_at` to Candidate model

**Files:**
- Modify: `jobhunter/backend/app/models/candidate.py`

- [ ] **Step 1: Add imports and field**

Add `DateTime` to the sqlalchemy import line (which currently imports `Boolean, Float, ForeignKey, Integer, String, Text`). Add `from datetime import datetime` at the top. Then add the field after `subscription_status`:

```python
# At top of file, add:
from datetime import datetime

# In sqlalchemy imports line, add DateTime:
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text

# In Candidate class, after subscription_status field:
onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
tour_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 2: Verify model loads**

```bash
cd jobhunter/backend && python -c "from app.models.candidate import Candidate; print('OK:', [c.key for c in Candidate.__table__.columns if 'onboarding' in c.key or 'tour' in c.key])"
```
Expected: `OK: ['onboarding_completed_at', 'tour_completed_at']`

### Task 2: Create Alembic migration

**Files:**
- Create: `jobhunter/backend/alembic/versions/023_add_onboarding_and_tour.py`

- [ ] **Step 1: Create migration file**

```python
"""Add onboarding_completed_at and tour_completed_at to candidates."""

import sqlalchemy as sa
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "candidates",
        sa.Column("tour_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidates", "tour_completed_at")
    op.drop_column("candidates", "onboarding_completed_at")
```

- [ ] **Step 2: Verify migration chain**

```bash
cd jobhunter/backend && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; s = ScriptDirectory.from_config(Config('alembic.ini')); print('Head:', s.get_current_head())"
```
Expected: `Head: 023`

### Task 3: Update CandidateResponse schema

**Files:**
- Modify: `jobhunter/backend/app/schemas/auth.py`

- [ ] **Step 1: Add fields to CandidateResponse**

Add `from datetime import datetime` to imports. Add four fields after `plan_tier` in `CandidateResponse`:

```python
from datetime import datetime

# In CandidateResponse class, after plan_tier:
onboarding_completed_at: datetime | None = None
onboarding_completed: bool = False
tour_completed_at: datetime | None = None
tour_completed: bool = False
```

### Task 4: Add complete-onboarding endpoint and update construction sites

**Files:**
- Modify: `jobhunter/backend/app/api/auth.py`

- [ ] **Step 1: Add datetime imports**

Add to the existing imports at the top of `auth.py`:

```python
from datetime import datetime, timezone
```

- [ ] **Step 2: Update ALL CandidateResponse construction sites**

There are 3 sites in auth.py where `CandidateResponse(...)` is constructed: in `register` (~line 41), `get_me` (~line 86), and `update_me` (~line 116). Each needs four new keyword arguments added:

```python
onboarding_completed_at=candidate.onboarding_completed_at,
onboarding_completed=candidate.onboarding_completed_at is not None,
tour_completed_at=candidate.tour_completed_at,
tour_completed=candidate.tour_completed_at is not None,
```

For the `register` handler specifically, since `candidate` is a freshly-created ORM object, both will be `None` — but still pass from the model for consistency.

**IMPORTANT:** Read the file first to find the exact line numbers and copy the exact field pattern used in each construction site. Do not guess — the three sites may have slightly different field sets.

- [ ] **Step 3: Add the complete-onboarding and complete-tour endpoints**

Add after the `update_me` handler. Copy the exact `CandidateResponse(...)` construction pattern from `get_me`. Two separate endpoints — one for wizard completion, one for tour completion:

```python
@router.post("/complete-onboarding", response_model=CandidateResponse)
async def complete_onboarding(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Mark onboarding wizard as completed for the current candidate."""
    if candidate.onboarding_completed_at is None:
        candidate.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(candidate)
        logger.info("onboarding_completed", candidate_id=str(candidate.id))
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        email_verified=candidate.email_verified,
        preferences=candidate.preferences,
        plan_tier=candidate.plan_tier,
        onboarding_completed_at=candidate.onboarding_completed_at,
        onboarding_completed=candidate.onboarding_completed_at is not None,
        tour_completed_at=candidate.tour_completed_at,
        tour_completed=candidate.tour_completed_at is not None,
    )


@router.post("/complete-tour", response_model=CandidateResponse)
async def complete_tour(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Mark dashboard tour as completed for the current candidate."""
    if candidate.tour_completed_at is None:
        candidate.tour_completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(candidate)
        logger.info("tour_completed", candidate_id=str(candidate.id))
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        email_verified=candidate.email_verified,
        preferences=candidate.preferences,
        plan_tier=candidate.plan_tier,
        onboarding_completed_at=candidate.onboarding_completed_at,
        onboarding_completed=candidate.onboarding_completed_at is not None,
        tour_completed_at=candidate.tour_completed_at,
        tour_completed=candidate.tour_completed_at is not None,
    )
```

Both endpoints are **idempotent** — calling them twice returns 200 both times (second call skips the write).

- [ ] **Step 4: Verify backend starts and linting passes**

```bash
cd jobhunter/backend && python -m py_compile app/api/auth.py && python -m py_compile app/models/candidate.py && python -m py_compile app/schemas/auth.py && echo "OK"
```

- [ ] **Step 5: Run existing auth tests to ensure nothing is broken**

```bash
cd jobhunter/backend && python -m pytest tests/test_auth.py tests/test_auth_service_unit.py -v --tb=short
```
Expected: All existing tests pass. Some may need the new fields added to assertions if they check the full response body.

- [ ] **Step 6: Commit backend changes**

```bash
git add jobhunter/backend/app/models/candidate.py jobhunter/backend/app/schemas/auth.py jobhunter/backend/app/api/auth.py jobhunter/backend/alembic/versions/023_add_onboarding_and_tour.py
git commit -m "feat(backend): add onboarding and tour tracking fields with completion endpoints"
```

---

## Chunk 2: Frontend — Types, API Client, Auth Provider, Route Guards

### Task 5: Update TypeScript types

**Files:**
- Modify: `jobhunter/frontend/src/lib/types.ts`

- [ ] **Step 1: Add onboarding fields to CandidateResponse**

Find the `CandidateResponse` interface (search for `interface CandidateResponse`). Add after `plan_tier`:

```typescript
onboarding_completed_at: string | null;
onboarding_completed: boolean;
tour_completed_at: string | null;
tour_completed: boolean;
```

### Task 6: Add completeOnboarding and completeTour API functions

**Files:**
- Modify: `jobhunter/frontend/src/lib/api/auth.ts`

- [ ] **Step 1: Add the API functions**

Add at the end of the file, before any default export:

```typescript
export async function completeOnboarding(): Promise<CandidateResponse> {
  const { data } = await api.post<CandidateResponse>("/auth/complete-onboarding");
  return data;
}

export async function completeTour(): Promise<CandidateResponse> {
  const { data } = await api.post<CandidateResponse>("/auth/complete-tour");
  return data;
}
```

### Task 7: Update AuthProvider with isOnboarded, isTourCompleted, and completion functions

**Files:**
- Modify: `jobhunter/frontend/src/providers/auth-provider.tsx`

- [ ] **Step 1: Update AuthContextType interface**

Add fields to the `AuthContextType` interface:

```typescript
interface AuthContextType {
  // ... existing fields ...
  isOnboarded: boolean;
  isTourCompleted: boolean;
  completeOnboarding: () => Promise<void>;
  completeTour: () => Promise<void>;
  resetTour: () => void;
}
```

- [ ] **Step 2: Add completion callbacks**

Add after the `refreshUser` callback:

```typescript
const completeOnboarding = useCallback(async () => {
  const updated = await authApi.completeOnboarding();
  setUser(updated);
}, []);

const completeTour = useCallback(async () => {
  const updated = await authApi.completeTour();
  setUser(updated);
}, []);

const resetTour = useCallback(() => {
  // Client-side only reset — sets isTourCompleted to false so the tour overlay shows again.
  // Does NOT call the backend — the tour_completed_at stays set in DB.
  // The overlay will call completeTour() again when the user finishes the replayed tour.
  if (user) {
    setUser({ ...user, tour_completed: false, tour_completed_at: null });
  }
}, [user]);
```

- [ ] **Step 3: Update context value**

Add to the `value` object in `AuthContext.Provider`:

```typescript
value={{
  // ... existing fields ...
  isOnboarded: !!(user?.onboarding_completed),
  isTourCompleted: !!(user?.tour_completed),
  completeOnboarding,
  completeTour,
  resetTour,
}}
```

- [ ] **Step 4: Update login redirect**

In the `login` callback, change `router.push("/dashboard")` to be conditional:

```typescript
const login = useCallback(
  async (email: string, password: string) => {
    const tokens = await authApi.login(email, password);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const me = await authApi.getMe();
    setUser(me);
    router.push(me.onboarding_completed ? "/dashboard" : "/onboarding");
  },
  [router]
);
```

### Task 8: Update auth layout redirect

**Files:**
- Modify: `jobhunter/frontend/src/app/(auth)/layout.tsx`

- [ ] **Step 1: Redirect based on onboarding status**

Change the `useEffect` and the guard:

```typescript
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, isOnboarded } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(isOnboarded ? "/dashboard" : "/onboarding");
    }
  }, [isAuthenticated, isLoading, isOnboarded, router]);

  if (isLoading) return null;
  if (isAuthenticated) return null;

  // ... rest unchanged
```

### Task 9: Update dashboard layout guard

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Add onboarding redirect**

Add `isOnboarded` to the destructured auth context and add a second redirect:

```typescript
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, isOnboarded } = useAuth();
  const router = useRouter();
  // ... existing state ...

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
    if (!isLoading && isAuthenticated && !isOnboarded) {
      router.replace("/onboarding");
    }
  }, [isAuthenticated, isLoading, isOnboarded, router]);

  // ... existing loading/unauthenticated guards ...
  if (!isAuthenticated || !isOnboarded) return null;

  // ... rest unchanged
```

- [ ] **Step 2: Verify frontend builds**

```bash
cd jobhunter/frontend && npx next build
```
Expected: Build succeeds with no type errors.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/lib/types.ts jobhunter/frontend/src/lib/api/auth.ts jobhunter/frontend/src/providers/auth-provider.tsx jobhunter/frontend/src/app/\(auth\)/layout.tsx jobhunter/frontend/src/app/\(dashboard\)/layout.tsx
git commit -m "feat(frontend): add onboarding guards and auth provider updates"
```

---

## Chunk 3: Frontend — Shared Onboarding Components (TagInput, StepIndicator, WizardShell, Schema)

### Task 10: Create the onboarding zod schema

**Files:**
- Create: `jobhunter/frontend/src/lib/schemas/onboarding.ts`

- [ ] **Step 1: Write the schema**

All fields are optional — users can skip the profile step entirely:

```typescript
import { z } from "zod";

export const onboardingProfileSchema = z.object({
  headline: z.string().max(500).optional().or(z.literal("")),
  location: z.string().max(255).optional().or(z.literal("")),
  target_roles: z.array(z.string()).max(10).optional(),
  target_industries: z.array(z.string()).max(10).optional(),
  target_locations: z.array(z.string()).max(10).optional(),
  salary_min: z.coerce.number().nonnegative().optional().or(z.literal("")),
  salary_max: z.coerce.number().nonnegative().optional().or(z.literal("")),
});

export type OnboardingProfileFormData = z.infer<typeof onboardingProfileSchema>;
```

### Task 11: Create TagInput component

**Files:**
- Create: `jobhunter/frontend/src/components/onboarding/tag-input.tsx`

- [ ] **Step 1: Write the component**

A controlled multi-value input. Tags appear as Badges. Enter/comma adds, Backspace removes last. No duplicates. Trims whitespace.

```typescript
"use client";

import { useState, useCallback, type KeyboardEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";

interface TagInputProps {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  maxTags?: number;
}

export function TagInput({ value, onChange, placeholder, maxTags = 10 }: TagInputProps) {
  const [input, setInput] = useState("");

  const addTag = useCallback(
    (tag: string) => {
      const trimmed = tag.trim();
      if (!trimmed) return;
      if (value.includes(trimmed)) return;
      if (value.length >= maxTags) return;
      onChange([...value, trimmed]);
      setInput("");
    },
    [value, onChange, maxTags]
  );

  const removeTag = useCallback(
    (index: number) => {
      onChange(value.filter((_, i) => i !== index));
    },
    [value, onChange]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        addTag(input);
      } else if (e.key === "Backspace" && !input && value.length > 0) {
        removeTag(value.length - 1);
      }
    },
    [input, value, addTag, removeTag]
  );

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-md border bg-background px-3 py-2 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
      {value.map((tag, i) => (
        <Badge key={tag} variant="secondary" className="gap-1 pr-1">
          {tag}
          <button
            type="button"
            onClick={() => removeTag(i)}
            className="ml-0.5 rounded-full p-0.5 hover:bg-muted-foreground/20"
            aria-label={`Remove ${tag}`}
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ))}
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => addTag(input)}
        placeholder={value.length === 0 ? placeholder : ""}
        className="h-7 min-w-[120px] flex-1 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0"
      />
    </div>
  );
}
```

### Task 12: Create StepIndicator component

**Files:**
- Create: `jobhunter/frontend/src/components/onboarding/step-indicator.tsx`

- [ ] **Step 1: Write the component**

Horizontal stepper: completed = green checkmark circle, current = numbered circle with primary border, future = muted numbered circle. Connecting lines between. Collapses to "Step X of N" on mobile.

```typescript
import { Check } from "lucide-react";

interface StepIndicatorProps {
  currentStep: number;
  steps: string[];
}

export function StepIndicator({ currentStep, steps }: StepIndicatorProps) {
  return (
    <div>
      {/* Mobile: compact */}
      <div className="flex items-center justify-center gap-2 sm:hidden">
        <span className="text-sm font-medium text-primary">
          Step {currentStep + 1} of {steps.length}
        </span>
        <span className="text-sm text-muted-foreground">— {steps[currentStep]}</span>
      </div>

      {/* Desktop: full stepper */}
      <div className="hidden sm:flex items-center justify-center">
        {steps.map((label, i) => {
          const isCompleted = i < currentStep;
          const isCurrent = i === currentStep;

          return (
            <div key={label} className="flex items-center">
              {/* Step circle */}
              <div className="flex flex-col items-center gap-1.5">
                {isCompleted ? (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary">
                    <Check className="h-4 w-4 text-primary-foreground" />
                  </div>
                ) : isCurrent ? (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-primary bg-background">
                    <span className="text-sm font-semibold text-primary">{i + 1}</span>
                  </div>
                ) : (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-muted-foreground/30 bg-background">
                    <span className="text-sm text-muted-foreground">{i + 1}</span>
                  </div>
                )}
                <span
                  className={`text-xs whitespace-nowrap ${
                    isCurrent ? "font-medium text-foreground" : "text-muted-foreground"
                  }`}
                >
                  {label}
                </span>
              </div>

              {/* Connector line */}
              {i < steps.length - 1 && (
                <div
                  className={`mx-3 mt-[-1.25rem] h-0.5 w-12 lg:w-20 ${
                    i < currentStep ? "bg-primary" : "bg-muted-foreground/20"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

### Task 13: Create WizardShell component

**Files:**
- Create: `jobhunter/frontend/src/components/onboarding/wizard-shell.tsx`

- [ ] **Step 1: Write the component**

Wraps step content with indicator at top and navigation buttons at bottom. Supports Back, Skip, and Next. Handles loading state on Next.

```typescript
"use client";

import { StepIndicator } from "@/components/onboarding/step-indicator";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Loader2 } from "lucide-react";

interface WizardShellProps {
  currentStep: number;
  steps: string[];
  children: React.ReactNode;
  onBack: () => void;
  onNext: () => void;
  onSkip?: () => void;
  showBack?: boolean;
  canSkip?: boolean;
  nextLabel?: string;
  isNextLoading?: boolean;
  isNextDisabled?: boolean;
  resumeMessage?: string;
}

export function WizardShell({
  currentStep,
  steps,
  children,
  onBack,
  onNext,
  onSkip,
  showBack = true,
  canSkip = false,
  nextLabel = "Next",
  isNextLoading = false,
  isNextDisabled = false,
  resumeMessage,
}: WizardShellProps) {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header with step indicator */}
      <div className="border-b bg-background/95 backdrop-blur px-4 py-4">
        <div className="mx-auto max-w-2xl">
          <StepIndicator currentStep={currentStep} steps={steps} />
        </div>
      </div>

      {/* Scrollable content area */}
      <div className="flex-1 overflow-y-auto px-4 py-8 sm:px-6">
        <div className="mx-auto max-w-2xl animate-in fade-in duration-300">
          {/* Welcome back message for returning users */}
          {resumeMessage && (
            <div className="mb-6 flex items-center gap-2 rounded-lg bg-primary/10 px-4 py-2.5 text-sm text-primary animate-in fade-in slide-in-from-top-2 duration-500">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{resumeMessage}</span>
            </div>
          )}
          {children}
        </div>
      </div>

      {/* Navigation bar */}
      <div className="border-t bg-background px-4 py-4">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <div>
            {showBack && currentStep > 0 && (
              <Button variant="ghost" onClick={onBack}>
                Back
              </Button>
            )}
          </div>
          <div className="flex items-center gap-3">
            {canSkip && onSkip && (
              <Button variant="ghost" onClick={onSkip} className="text-muted-foreground">
                Skip
              </Button>
            )}
            <Button onClick={onNext} disabled={isNextLoading || isNextDisabled}>
              {isNextLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {nextLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd jobhunter/frontend && npx next build
```

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/lib/schemas/onboarding.ts jobhunter/frontend/src/components/onboarding/
git commit -m "feat(frontend): add onboarding shared components (tag-input, step-indicator, wizard-shell)"
```

---

## Chunk 4: Frontend — Step Components (Welcome, Profile, Resume, Complete)

### Task 14: Create StepWelcome component

**Files:**
- Create: `jobhunter/frontend/src/components/onboarding/step-welcome.tsx`

- [ ] **Step 1: Write the component**

Welcome screen with app overview. Shows 3 preview cards explaining what the wizard covers and WHY each step matters. Uses the same logo/branding as the auth layout.

```typescript
import { Briefcase, User, MailCheck, Upload, LayoutDashboard } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const previewSteps = [
  {
    icon: User,
    title: "Set up your profile",
    description: "Tell us about your career goals, target roles, and preferred locations. This helps our AI find the best-matching companies and craft personalized outreach.",
  },
  {
    icon: MailCheck,
    title: "Verify your email",
    description: "Confirm your email address so we can send you outreach updates, follow-up reminders, and important notifications about your job search.",
  },
  {
    icon: Upload,
    title: "Upload your resume",
    description: "Our AI analyzes your resume to build your Candidate DNA — a profile of your strengths, skills, and growth areas that powers everything in the platform.",
  },
  {
    icon: LayoutDashboard,
    title: "Explore your dashboard",
    description: "A guided tour of every feature — see how JobHunter AI automates company discovery, personalizes outreach, and tracks your progress.",
  },
];

export function StepWelcome() {
  return (
    <div className="space-y-8 text-center">
      {/* Logo and headline */}
      <div className="flex flex-col items-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/70 shadow-md shadow-primary/25">
          <Briefcase className="h-7 w-7 text-primary-foreground" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Welcome to JobHunter AI</h1>
        <p className="max-w-md text-muted-foreground">
          Let&apos;s get you set up in a few quick steps. We&apos;ll personalize your experience
          so you can start landing interviews faster.
        </p>
      </div>

      {/* Step previews */}
      <div className="space-y-3 text-left">
        <h2 className="text-sm font-medium text-muted-foreground text-center">Here&apos;s what we&apos;ll cover:</h2>
        {previewSteps.map((step) => {
          const Icon = step.icon;
          return (
            <Card key={step.title}>
              <CardContent className="flex items-start gap-4 py-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-medium">{step.title}</h3>
                  <p className="mt-0.5 text-sm text-muted-foreground">{step.description}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
```

### Task 15: Create StepProfile component

**Files:**
- Create: `jobhunter/frontend/src/components/onboarding/step-profile.tsx`

- [ ] **Step 1: Write the component**

Profile form with react-hook-form + zod. All fields optional. Each field has a WHY explanation. Exposes a `formRef` so the parent can trigger submission via the wizard's Next button.

```typescript
"use client";

import { useImperativeHandle, forwardRef, useRef } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "@/providers/auth-provider";
import { onboardingProfileSchema, type OnboardingProfileFormData } from "@/lib/schemas/onboarding";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TagInput } from "@/components/onboarding/tag-input";
import { toast } from "sonner";

export interface StepProfileHandle {
  submit: () => Promise<boolean>;
}

export const StepProfile = forwardRef<StepProfileHandle, { onComplete: () => void }>(
  function StepProfile({ onComplete }, ref) {
    const { user, updateProfile } = useAuth();
    const formRef = useRef<HTMLFormElement>(null);

    const {
      register,
      handleSubmit,
      control,
      formState: { errors, isSubmitting },
    } = useForm<OnboardingProfileFormData>({
      resolver: zodResolver(onboardingProfileSchema),
      defaultValues: {
        headline: user?.headline || "",
        location: user?.location || "",
        target_roles: user?.target_roles || [],
        target_industries: user?.target_industries || [],
        target_locations: user?.target_locations || [],
        salary_min: user?.salary_min ?? ("" as unknown as undefined),
        salary_max: user?.salary_max ?? ("" as unknown as undefined),
      },
    });

    useImperativeHandle(ref, () => ({
      submit: async () => {
        let success = false;
        await handleSubmit(async (data) => {
          try {
            const updates: Record<string, unknown> = {};
            if (data.headline) updates.headline = data.headline;
            if (data.location) updates.location = data.location;
            if (data.target_roles?.length) updates.target_roles = data.target_roles;
            if (data.target_industries?.length) updates.target_industries = data.target_industries;
            if (data.target_locations?.length) updates.target_locations = data.target_locations;
            if (data.salary_min && data.salary_min !== "") updates.salary_min = Number(data.salary_min);
            if (data.salary_max && data.salary_max !== "") updates.salary_max = Number(data.salary_max);

            if (Object.keys(updates).length > 0) {
              await updateProfile(updates);
            }
            success = true;
            onComplete();
          } catch (err: unknown) {
            const message =
              (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
              "Failed to save profile";
            toast.error(message);
          }
        })();
        return success;
      },
    }));

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold">Set up your profile</h2>
          <p className="mt-1 text-muted-foreground">
            Help us understand your career goals. All fields are optional — you can update them later in Settings.
          </p>
        </div>

        <form ref={formRef} className="space-y-5">
          {/* Headline */}
          <div className="space-y-2">
            <Label htmlFor="headline">Professional headline</Label>
            <Input id="headline" placeholder="e.g. Senior Backend Developer" {...register("headline")} />
            <p className="text-xs text-muted-foreground">
              Appears on outreach messages — helps recipients understand who you are at a glance.
            </p>
          </div>

          {/* Location */}
          <div className="space-y-2">
            <Label htmlFor="location">Location</Label>
            <Input id="location" placeholder="e.g. Tel Aviv, Israel" {...register("location")} />
            <p className="text-xs text-muted-foreground">
              Helps us find companies and roles in your area, or filter for remote-friendly positions.
            </p>
          </div>

          {/* Target Roles */}
          <div className="space-y-2">
            <Label>Target roles</Label>
            <Controller
              name="target_roles"
              control={control}
              render={({ field }) => (
                <TagInput
                  value={field.value || []}
                  onChange={field.onChange}
                  placeholder="e.g. Backend Developer, Data Engineer"
                />
              )}
            />
            <p className="text-xs text-muted-foreground">
              What roles are you looking for? We use these to match you with relevant job postings and companies.
            </p>
          </div>

          {/* Target Industries */}
          <div className="space-y-2">
            <Label>Target industries</Label>
            <Controller
              name="target_industries"
              control={control}
              render={({ field }) => (
                <TagInput
                  value={field.value || []}
                  onChange={field.onChange}
                  placeholder="e.g. FinTech, HealthTech, SaaS"
                />
              )}
            />
            <p className="text-xs text-muted-foreground">
              Which industries interest you? Narrows company discovery to sectors you care about.
            </p>
          </div>

          {/* Target Locations */}
          <div className="space-y-2">
            <Label>Preferred work locations</Label>
            <Controller
              name="target_locations"
              control={control}
              render={({ field }) => (
                <TagInput
                  value={field.value || []}
                  onChange={field.onChange}
                  placeholder="e.g. Tel Aviv, Remote, London"
                />
              )}
            />
            <p className="text-xs text-muted-foreground">
              Where would you like to work? Filters opportunities by geography.
            </p>
          </div>

          {/* Salary Range */}
          <div className="space-y-2">
            <Label>Salary range (annual)</Label>
            <div className="grid grid-cols-2 gap-3">
              <Input
                type="number"
                placeholder="Min"
                {...register("salary_min")}
              />
              <Input
                type="number"
                placeholder="Max"
                {...register("salary_max")}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Your expected salary range — used to match positions within your expectations. Never shared externally.
            </p>
          </div>
        </form>
      </div>
    );
  }
);
```

### Task 15b: Create StepEmailVerify component

**Files:**
- Create: `jobhunter/frontend/src/components/onboarding/step-email-verify.tsx`

- [ ] **Step 1: Write the component**

Nudges the user to verify their email. Shows their email address, a "Check your inbox" message, a resend button with cooldown, and allows continuing without verifying. If already verified, shows a green success state.

```typescript
"use client";

import { useState } from "react";
import { useAuth } from "@/providers/auth-provider";
import * as authApi from "@/lib/api/auth";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MailCheck, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export function StepEmailVerify() {
  const { user, refreshUser } = useAuth();
  const [isResending, setIsResending] = useState(false);
  const [cooldown, setCooldown] = useState(false);

  const isVerified = !!user?.email_verified;

  const handleResend = async () => {
    setIsResending(true);
    try {
      await authApi.resendVerification();
      toast.success("Verification email sent!");
      setCooldown(true);
      setTimeout(() => setCooldown(false), 60000); // 60s cooldown
    } catch {
      toast.error("Failed to resend. Please try again in a few minutes.");
    } finally {
      setIsResending(false);
    }
  };

  const handleCheckStatus = async () => {
    await refreshUser();
    if (!user?.email_verified) {
      toast.info("Email not verified yet. Check your inbox and click the verification link.");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Verify your email</h2>
        <p className="mt-1 text-muted-foreground">
          This ensures we can send you outreach updates and important notifications.
        </p>
      </div>

      {isVerified ? (
        <Card className="border-green-500/30 bg-green-500/5">
          <CardContent className="flex items-center gap-3 py-5">
            <CheckCircle2 className="h-6 w-6 text-green-600" />
            <div>
              <p className="font-medium text-green-700 dark:text-green-400">Email verified!</p>
              <p className="text-sm text-muted-foreground">{user?.email}</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="flex items-start gap-4 py-5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                <MailCheck className="h-6 w-6 text-primary" />
              </div>
              <div className="space-y-2">
                <p className="font-medium">Check your inbox</p>
                <p className="text-sm text-muted-foreground">
                  We sent a verification link to <strong>{user?.email}</strong>.
                  Click the link in the email to verify your account.
                </p>
                <div className="flex items-center gap-3 pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleResend}
                    disabled={isResending || cooldown}
                  >
                    {isResending ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    {cooldown ? "Sent — check inbox" : "Resend email"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleCheckStatus}>
                    I&apos;ve verified
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <p className="text-xs text-muted-foreground text-center">
            You can continue without verifying, but some features (like email outreach) work best with a verified account.
          </p>
        </>
      )}
    </div>
  );
}
```

### Task 16: Create StepResume component

**Files:**
- Create: `jobhunter/frontend/src/components/onboarding/step-resume.tsx`

- [ ] **Step 1: Write the component**

Shows an info card explaining WHY the resume matters, then the existing UploadZone. After upload, polls for DNA processing status.

```typescript
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as candidatesApi from "@/lib/api/candidates";
import { UploadZone } from "@/components/resume/upload-zone";
import { Card, CardContent } from "@/components/ui/card";
import { Info, Loader2, CheckCircle2 } from "lucide-react";

export function StepResume() {
  const [uploadDone, setUploadDone] = useState(false);

  const dnaQuery = useQuery({
    queryKey: ["dna"],
    queryFn: candidatesApi.getDNA,
    enabled: uploadDone,
    refetchInterval: (query) => (query.state.data ? false : 3000),
    retry: 1,
  });

  const hasDna = !!dnaQuery.data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Upload your resume</h2>
        <p className="mt-1 text-muted-foreground">
          This is optional — you can always do it later from the Resume &amp; DNA page.
        </p>
      </div>

      {/* Why this matters */}
      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="flex items-start gap-3 py-4">
          <Info className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div className="space-y-1">
            <p className="text-sm font-medium">Why upload your resume?</p>
            <p className="text-sm text-muted-foreground">
              Your resume powers our AI engine. We analyze it to build your <strong>Candidate DNA</strong> — a
              profile of your strengths, skills, transferable abilities, and gaps. This profile drives
              personalized company matching, outreach message generation, and skills gap analysis.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Upload zone */}
      {!hasDna && (
        <UploadZone onUploadSuccess={() => setUploadDone(true)} />
      )}

      {/* Processing state */}
      {uploadDone && !hasDna && (
        <Card>
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <div>
              <p className="text-sm font-medium">Building your Candidate DNA...</p>
              <p className="text-xs text-muted-foreground">
                This usually takes 30-60 seconds. You can continue to the next step while we process.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Success state */}
      {hasDna && (
        <Card className="border-green-500/30 bg-green-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <div>
              <p className="text-sm font-medium text-green-700 dark:text-green-400">
                Candidate DNA profile created!
              </p>
              <p className="text-xs text-muted-foreground">
                Your strengths, skills, and growth areas have been identified. View them on the Resume &amp; DNA page.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd jobhunter/frontend && npx next build
```

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/components/onboarding/
git commit -m "feat(frontend): add onboarding step components (welcome, profile, resume)"
```

---

## Chunk 5: Frontend — Onboarding Layout and Wizard Page

### Task 18: Create the onboarding layout

**Files:**
- Create: `jobhunter/frontend/src/app/(onboarding)/layout.tsx`

- [ ] **Step 1: Write the layout**

Auth guard (redirect to /login if not authenticated). Onboarding guard (redirect to /dashboard if already onboarded). Clean full-page layout — no sidebar, no header, no footer. Mirrors the `(auth)/layout.tsx` guard pattern with `isLoading` checks to prevent flash redirects.

```typescript
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, isOnboarded } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
    if (!isLoading && isAuthenticated && isOnboarded) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, isOnboarded, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated || isOnboarded) return null;

  return <>{children}</>;
}
```

### Task 19: Create the onboarding wizard page

**Files:**
- Create: `jobhunter/frontend/src/app/(onboarding)/onboarding/page.tsx`

- [ ] **Step 1: Write the wizard orchestrator**

Manages `currentStep` state. **Computes the initial step from user data** so returning users resume from where they left off. Renders `WizardShell` with the correct step component. Handles navigation, skipping, loading states, and the final "Go to Dashboard" action.

**Resume logic — derive starting step from data:**
| Condition | Start at |
|---|---|
| No profile data filled, no DNA | Step 0 (Welcome) |
| Any profile field filled (headline, location, target_roles, etc.) but no DNA | Step 2 (Resume) |
| Has profile data AND has DNA | Wizard complete → redirect to dashboard (tour starts there) |

This means:
- Brand new user → sees Welcome
- User who filled profile then closed browser → skips to Email Verify or Resume
- User who uploaded resume AND has DNA → wizard is done, complete onboarding and go to dashboard tour

**The wizard is now 4 steps (Welcome, Profile, Verify Email, Resume). The "Get Started" tour happens on the actual dashboard as a spotlight overlay.**

```typescript
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/providers/auth-provider";
import * as candidatesApi from "@/lib/api/candidates";
import { WizardShell } from "@/components/onboarding/wizard-shell";
import { StepWelcome } from "@/components/onboarding/step-welcome";
import { StepProfile, type StepProfileHandle } from "@/components/onboarding/step-profile";
import { StepEmailVerify } from "@/components/onboarding/step-email-verify";
import { StepResume } from "@/components/onboarding/step-resume";
import { toast } from "sonner";

const STEPS = ["Welcome", "Profile", "Verify Email", "Resume"];

function computeInitialStep(
  user: {
    headline?: string | null;
    location?: string | null;
    target_roles?: string[] | null;
    target_industries?: string[] | null;
    target_locations?: string[] | null;
    salary_min?: number | null;
    salary_max?: number | null;
    email_verified?: boolean;
  } | null,
  hasDna: boolean
): number | "done" {
  if (!user) return 0;

  const hasProfile = !!(
    user.headline ||
    user.location ||
    (user.target_roles && user.target_roles.length > 0) ||
    (user.target_industries && user.target_industries.length > 0) ||
    (user.target_locations && user.target_locations.length > 0) ||
    user.salary_min ||
    user.salary_max
  );

  if (hasProfile && hasDna) return "done"; // Wizard already complete → dashboard tour
  if (hasProfile && !user.email_verified) return 2; // Skip to Verify Email
  if (hasProfile) return 3;                // Skip to Resume
  return 0;                                // Start from Welcome
}

export default function OnboardingPage() {
  const { user, completeOnboarding } = useAuth();
  const router = useRouter();

  // Check if DNA already exists (for resume step)
  const dnaQuery = useQuery({
    queryKey: ["dna"],
    queryFn: candidatesApi.getDNA,
    retry: 1,
    staleTime: Infinity,
  });

  // Wait for DNA query to settle before computing initial step
  const isReady = !dnaQuery.isLoading;
  const initialStep = useMemo(
    () => computeInitialStep(user, !!dnaQuery.data),
    [user, dnaQuery.data]
  );

  // Track whether user resumed from a later step (for "Welcome back" message)
  const isResuming = isReady && typeof initialStep === "number" && initialStep > 0;

  const [currentStep, setCurrentStep] = useState<number | null>(null);
  const [isNextLoading, setIsNextLoading] = useState(false);
  const profileRef = useRef<StepProfileHandle>(null);

  // If user already completed all wizard steps, auto-complete and redirect to dashboard tour
  useEffect(() => {
    if (isReady && initialStep === "done") {
      completeOnboarding().then(() => router.push("/dashboard"));
    }
  }, [isReady, initialStep, completeOnboarding, router]);

  // Set initial step once data is ready
  if (isReady && currentStep === null && initialStep !== "done") {
    setCurrentStep(initialStep);
  }

  // Show loading while computing initial step or auto-completing
  if (currentStep === null) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const goBack = () => {
    setCurrentStep((prev) => Math.max(0, (prev ?? 0) - 1));
  };

  const goForward = () => {
    setCurrentStep((prev) => Math.min(STEPS.length - 1, (prev ?? 0) + 1));
  };

  const handleNext = async () => {
    // Step 0 (Welcome): just advance
    if (currentStep === 0) {
      goForward();
      return;
    }

    // Step 1 (Profile): trigger form submission
    if (currentStep === 1) {
      if (profileRef.current) {
        setIsNextLoading(true);
        try {
          await profileRef.current.submit();
        } finally {
          setIsNextLoading(false);
        }
      }
      return;
    }

    // Step 2 (Verify Email): just advance
    if (currentStep === 2) {
      goForward();
      return;
    }

    // Step 3 (Resume): finish wizard → go to dashboard (tour starts there)
    if (currentStep === 3) {
      setIsNextLoading(true);
      try {
        await completeOnboarding();
        router.push("/dashboard");
      } catch {
        toast.error("Something went wrong. Please try again.");
        setIsNextLoading(false);
      }
    }
  };

  const handleSkip = () => {
    if (currentStep === 3) {
      // Skipping resume = finish wizard without upload
      handleNext();
      return;
    }
    goForward();
  };

  const getNextLabel = () => {
    switch (currentStep) {
      case 0: return "Let's get started";
      case 1: return "Save & continue";
      case 2: return "Continue";
      case 3: return "Go to Dashboard";
      default: return "Next";
    }
  };

  return (
    <WizardShell
      currentStep={currentStep}
      steps={STEPS}
      onBack={goBack}
      onNext={handleNext}
      onSkip={handleSkip}
      showBack={currentStep > 0}
      canSkip={currentStep === 1 || currentStep === 2 || currentStep === 3}
      nextLabel={getNextLabel()}
      isNextLoading={isNextLoading}
      resumeMessage={isResuming && currentStep === initialStep ? "Welcome back — your progress has been saved." : undefined}
    >
      {currentStep === 0 && <StepWelcome />}
      {currentStep === 1 && <StepProfile ref={profileRef} onComplete={goForward} />}
      {currentStep === 2 && <StepEmailVerify />}
      {currentStep === 3 && <StepResume />}
    </WizardShell>
  );
}
```

- [ ] **Step 2: Verify full build**

```bash
cd jobhunter/frontend && npx next build
```
Expected: Build succeeds, `/onboarding` route appears in the route list.

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/\(onboarding\)/
git commit -m "feat(frontend): add onboarding layout and wizard page"
```

---

## Chunk 6: Dashboard Spotlight Tour

The tour is a full-screen overlay that dims the page and spotlights one element at a time. A tooltip next to each spotlight explains WHAT the panel does and WHY it matters. The user clicks "Next" to advance through all panels, or "Skip tour" to dismiss.

### Task 20: Add `data-tour` attributes to dashboard elements

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/dashboard/page.tsx`
- Modify: `jobhunter/frontend/src/components/layout/sidebar.tsx`

- [ ] **Step 1: Add data-tour attributes to dashboard page**

Add `data-tour="..."` to the key sections in the dashboard page. These are the anchors the spotlight overlay will target:

```tsx
{/* Wrap next actions grid */}
<div data-tour="next-actions" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">

{/* Wrap stats cards grid */}
<div data-tour="stats-cards" className="grid gap-4 grid-cols-2 lg:grid-cols-4">

{/* Wrap pipeline card */}
<Card data-tour="pipeline" className="h-full">

{/* Wrap recent companies card */}
<Card data-tour="recent-companies">
```

- [ ] **Step 2: Add data-tour attributes to sidebar nav items**

In the sidebar component, add `data-tour` to each nav section. The simplest approach is to add it to the section wrapper divs. Find where `navSections` are mapped and add:

```tsx
{/* On each section wrapper div */}
<div key={section.label} data-tour={`nav-${section.label.toLowerCase()}`}>
```

This gives us: `data-tour="nav-core"`, `data-tour="nav-outreach"`, `data-tour="nav-insights"`, `data-tour="nav-system"`

### Task 21: Create tour step definitions

**Files:**
- Create: `jobhunter/frontend/src/lib/tour-steps.ts`

- [ ] **Step 1: Write the tour steps config**

Each step defines a `data-tour` selector, tooltip position, title, and description (what + why):

```typescript
export interface TourStep {
  selector: string;        // data-tour value to target
  title: string;
  description: string;
  position: "top" | "bottom" | "left" | "right";
}

export const TOUR_STEPS: TourStep[] = [
  // Sidebar navigation sections
  {
    selector: "nav-core",
    title: "Core Pages",
    description: "Your essential tools — Dashboard for an overview, Resume & DNA to build your AI profile, and Companies to discover opportunities that match your skills.",
    position: "right",
  },
  {
    selector: "nav-outreach",
    title: "Outreach Tools",
    description: "Everything for connecting with companies — AI-crafted messages, interview prep, job application analysis, and an approval queue so nothing sends without your review.",
    position: "right",
  },
  {
    selector: "nav-insights",
    title: "Insights",
    description: "Analytics to track your job search — open rates, reply rates, pipeline trends. Know what's working and where to adjust your approach.",
    position: "right",
  },
  // Dashboard panels
  {
    selector: "next-actions",
    title: "Next Actions",
    description: "Context-aware suggestions for what to do next — upload a resume, review approvals, discover companies, or start outreach. These update as you progress.",
    position: "bottom",
  },
  {
    selector: "stats-cards",
    title: "Your Stats",
    description: "Key metrics at a glance — companies in your pipeline, emails sent, open rate, and reply rate. Click any card to dive deeper.",
    position: "bottom",
  },
  {
    selector: "pipeline",
    title: "Pipeline Overview",
    description: "Your job search funnel — from suggested companies through approval, research, and outreach. See where your opportunities are and what needs attention.",
    position: "top",
  },
  {
    selector: "recent-companies",
    title: "Recent Companies",
    description: "Quick access to companies you've recently interacted with. Click any row to see the full company dossier with research, contacts, and outreach history.",
    position: "top",
  },
];
```

### Task 22: Create TourSpotlight primitive

**Files:**
- Create: `jobhunter/frontend/src/components/dashboard/tour-spotlight.tsx`

- [ ] **Step 1: Write the spotlight component**

Renders a full-screen overlay with a transparent cutout around the target element. Uses `getBoundingClientRect()` to position the cutout. The cutout has a subtle border glow.

```typescript
"use client";

import { useEffect, useState } from "react";

interface SpotlightRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

interface TourSpotlightProps {
  selector: string;
  padding?: number;
}

export function TourSpotlight({ selector, padding = 8 }: TourSpotlightProps) {
  const [rect, setRect] = useState<SpotlightRect | null>(null);

  useEffect(() => {
    const el = document.querySelector(`[data-tour="${selector}"]`);
    if (!el) return;

    const update = () => {
      const r = el.getBoundingClientRect();
      setRect({
        top: r.top - padding,
        left: r.left - padding,
        width: r.width + padding * 2,
        height: r.height + padding * 2,
      });
    };

    update();
    // Scroll element into view
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    // Recalculate after scroll settles
    const timer = setTimeout(update, 400);

    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("resize", update);
      clearTimeout(timer);
    };
  }, [selector, padding]);

  if (!rect) return null;

  return (
    <>
      {/* Dimmed backdrop with cutout */}
      <div
        className="fixed inset-0 z-[60] transition-all duration-300"
        style={{
          background: `radial-gradient(
            ellipse at ${rect.left + rect.width / 2}px ${rect.top + rect.height / 2}px,
            transparent ${Math.max(rect.width, rect.height) * 0.6}px,
            rgba(0, 0, 0, 0.6) ${Math.max(rect.width, rect.height) * 0.8}px
          )`,
        }}
      />
      {/* Highlight border around target */}
      <div
        className="fixed z-[61] rounded-lg border-2 border-primary shadow-[0_0_0_4px_rgba(var(--primary),0.15)] pointer-events-none transition-all duration-300"
        style={{
          top: rect.top,
          left: rect.left,
          width: rect.width,
          height: rect.height,
        }}
      />
    </>
  );
}
```

### Task 23: Create TourTooltip component

**Files:**
- Create: `jobhunter/frontend/src/components/dashboard/tour-tooltip.tsx`

- [ ] **Step 1: Write the tooltip component**

Positioned next to the spotlight. Shows step title, description, step counter, and Next/Skip buttons.

```typescript
"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface TourTooltipProps {
  selector: string;
  position: "top" | "bottom" | "left" | "right";
  title: string;
  description: string;
  currentStep: number;
  totalSteps: number;
  onNext: () => void;
  onSkip: () => void;
  isLast: boolean;
}

export function TourTooltip({
  selector,
  position,
  title,
  description,
  currentStep,
  totalSteps,
  onNext,
  onSkip,
  isLast,
}: TourTooltipProps) {
  const [style, setStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    const el = document.querySelector(`[data-tour="${selector}"]`);
    if (!el) return;

    const update = () => {
      const r = el.getBoundingClientRect();
      const gap = 16;
      const tooltipWidth = 340;

      let top = 0;
      let left = 0;

      switch (position) {
        case "bottom":
          top = r.bottom + gap;
          left = r.left + r.width / 2 - tooltipWidth / 2;
          break;
        case "top":
          top = r.top - gap;
          left = r.left + r.width / 2 - tooltipWidth / 2;
          break;
        case "right":
          top = r.top + r.height / 2;
          left = r.right + gap;
          break;
        case "left":
          top = r.top + r.height / 2;
          left = r.left - gap - tooltipWidth;
          break;
      }

      // Clamp to viewport
      left = Math.max(16, Math.min(left, window.innerWidth - tooltipWidth - 16));
      top = Math.max(16, top);

      setStyle({
        position: "fixed",
        top,
        left,
        width: tooltipWidth,
        zIndex: 62,
        transform: position === "top" ? "translateY(-100%)" : position === "right" || position === "left" ? "translateY(-50%)" : undefined,
      });
    };

    // Wait for scroll to settle
    const timer = setTimeout(update, 450);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("resize", update);
      clearTimeout(timer);
    };
  }, [selector, position]);

  return (
    <div style={style} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <Card className="shadow-xl border-primary/20">
        <CardContent className="space-y-3 py-4">
          <div className="flex items-start justify-between">
            <h3 className="font-semibold text-base">{title}</h3>
            <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={onSkip}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-muted-foreground">
              {currentStep + 1} of {totalSteps}
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={onSkip}>
                Skip tour
              </Button>
              <Button size="sm" onClick={onNext}>
                {isLast ? "Finish" : "Next"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

### Task 24: Create TourOverlay orchestrator

**Files:**
- Create: `jobhunter/frontend/src/components/dashboard/tour-overlay.tsx`

- [ ] **Step 1: Write the overlay component**

Orchestrates the full tour: manages current step, renders spotlight + tooltip, and calls `completeTour()` when done. **Filters out sidebar steps on mobile** (sidebar is hidden below `lg` breakpoint).

```typescript
"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { useAuth } from "@/providers/auth-provider";
import { TourSpotlight } from "@/components/dashboard/tour-spotlight";
import { TourTooltip } from "@/components/dashboard/tour-tooltip";
import { TOUR_STEPS } from "@/lib/tour-steps";

export function TourOverlay() {
  const { isTourCompleted, completeTour } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile (sidebar hidden below lg = 1024px)
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1024);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Filter out sidebar (nav-*) steps on mobile
  const steps = useMemo(
    () => isMobile ? TOUR_STEPS.filter((s) => !s.selector.startsWith("nav-")) : TOUR_STEPS,
    [isMobile]
  );

  const handleNext = useCallback(() => {
    if (currentStep >= steps.length - 1) {
      completeTour();
      setDismissed(true);
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep, steps.length, completeTour]);

  const handleSkip = useCallback(() => {
    completeTour();
    setDismissed(true);
  }, [completeTour]);

  if (isTourCompleted || dismissed || steps.length === 0) return null;

  const step = steps[currentStep];

  return (
    <>
      <TourSpotlight selector={step.selector} />
      <TourTooltip
        selector={step.selector}
        position={step.position}
        title={step.title}
        description={step.description}
        currentStep={currentStep}
        totalSteps={steps.length}
        onNext={handleNext}
        onSkip={handleSkip}
        isLast={currentStep === steps.length - 1}
      />
    </>
  );
}
```

### Task 25: Render TourOverlay in dashboard layout

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Import and render TourOverlay**

Add the import and render the overlay inside the dashboard layout, after the main content:

```typescript
import { TourOverlay } from "@/components/dashboard/tour-overlay";

// Inside the return, after <Footer />:
<TourOverlay />
```

- [ ] **Step 2: Verify build**

```bash
cd jobhunter/frontend && npx next build
```

- [ ] **Step 3: Commit**

```bash
git add jobhunter/frontend/src/lib/tour-steps.ts jobhunter/frontend/src/components/dashboard/tour-overlay.tsx jobhunter/frontend/src/components/dashboard/tour-spotlight.tsx jobhunter/frontend/src/components/dashboard/tour-tooltip.tsx jobhunter/frontend/src/app/\(dashboard\)/dashboard/page.tsx jobhunter/frontend/src/components/layout/sidebar.tsx jobhunter/frontend/src/app/\(dashboard\)/layout.tsx
git commit -m "feat(frontend): add live dashboard spotlight tour with 7-step guided walkthrough"
```

### Task 25b: Add "Replay guided tour" button to Settings page

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: Add replay tour button**

Read the existing settings page first. Find the appropriate section (likely near the bottom, or in a "Preferences" or "Account" section) and add a button:

```typescript
import { useAuth } from "@/providers/auth-provider";
import { useRouter } from "next/navigation";
import { RotateCcw } from "lucide-react";

// Inside the component:
const { resetTour } = useAuth();
const router = useRouter();

// In the JSX, add a section:
<Card>
  <CardHeader>
    <CardTitle>Guided Tour</CardTitle>
  </CardHeader>
  <CardContent>
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm">Replay the dashboard guided tour</p>
        <p className="text-xs text-muted-foreground">
          Walk through each feature again with spotlight explanations.
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          resetTour();
          router.push("/dashboard");
        }}
      >
        <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
        Replay tour
      </Button>
    </div>
  </CardContent>
</Card>
```

- [ ] **Step 2: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/settings/page.tsx
git commit -m "feat(frontend): add replay guided tour button to settings page"
```

---

## Chunk 7: Integration Testing and Final Verification

### Task 26: Run the migration in Docker

- [ ] **Step 1: Apply migration**

```bash
cd jobhunter && docker compose exec backend /app/.venv/bin/alembic upgrade head
```
Expected: `INFO  [alembic.runtime.migration] Running upgrade 022 -> 023, Add onboarding_completed_at and tour_completed_at to candidates`

### Task 27: End-to-end smoke test

- [ ] **Step 1: Verify existing user flow (fresh user)**

Log in with test@example.com / testpass123. Because `onboarding_completed_at` is NULL, the dashboard should redirect to `/onboarding`. Verify the wizard renders with 4 steps (Welcome, Profile, Verify Email, Resume), starting at Step 0 (Welcome).

- [ ] **Step 2: Walk through the wizard**

1. Welcome step: verify 4 preview cards shown (Profile, Verify Email, Resume, Dashboard tour). Click "Let's get started"
2. Profile step: fill in at least one field (e.g. headline), click "Save & continue"
3. Verify Email step: verify user's email is shown, resend button works, "Continue" advances. Click "Continue"
4. Resume step: click "Go to Dashboard" (skip upload for now)
5. Verify you land on `/dashboard` with the **spotlight tour** overlay active
6. Click through all 7 tour steps — verify each spotlight highlights the correct panel
7. Click "Finish" on the last step — tour dismisses

- [ ] **Step 3: Verify re-entry guards**

1. Navigate to `/onboarding` manually → should redirect to `/dashboard` (onboarding complete)
2. Refresh `/dashboard` → tour should NOT appear again (tour_completed is true)

- [ ] **Step 4: Test resume from mid-wizard (critical)**

To test the resume behavior:
1. Reset: `UPDATE candidates SET onboarding_completed_at = NULL, tour_completed_at = NULL WHERE email = 'test@example.com';`
2. Navigate to `/onboarding` — since the user already has profile data AND DNA, the wizard should auto-complete and redirect to `/dashboard` with the tour overlay
3. If only profile was filled but no resume was uploaded, wizard should start at Step 2 (Resume)
4. Verify the Back button still works to revisit earlier steps

- [ ] **Step 5: Test tour dismissal**

1. Reset again: `UPDATE candidates SET onboarding_completed_at = NULL, tour_completed_at = NULL WHERE email = 'test@example.com';`
2. Walk through wizard to dashboard, then click "Skip tour" on the first tour step
3. Verify tour dismisses and `tour_completed_at` is set
4. Refresh page — tour should not reappear

- [ ] **Step 6: Test "Welcome back" message**

1. Reset: `UPDATE candidates SET onboarding_completed_at = NULL, tour_completed_at = NULL WHERE email = 'test@example.com';`
2. Navigate to `/onboarding` — since profile data exists, wizard should skip to Verify Email (step 2) or Resume (step 3)
3. Verify the green "Welcome back — your progress has been saved." banner appears at the top of the step
4. Navigate away and back — banner should only show on the initial resume step

- [ ] **Step 7: Test "Replay tour" from Settings**

1. Navigate to `/settings`
2. Find the "Guided Tour" card with the "Replay tour" button
3. Click "Replay tour" — should redirect to `/dashboard` with the tour overlay active again
4. Complete or skip the tour — should work normally

- [ ] **Step 8: Test mobile tour (sidebar steps skipped)**

1. Resize browser to < 1024px width (or use mobile emulation)
2. Reset tour: use "Replay tour" button in Settings
3. Verify tour starts with "Next Actions" (not sidebar nav steps)
4. Verify tour has fewer steps than desktop (4 instead of 7)

### Task 28: Run all existing tests

- [ ] **Step 1: Backend tests**

```bash
cd jobhunter/backend && python -m pytest tests/ -v --tb=short
```
Expected: All existing tests pass. If any fail due to missing `onboarding_completed_at` / `tour_completed_at` fields in response assertions, update those assertions.

- [ ] **Step 2: Frontend build**

```bash
cd jobhunter/frontend && npx next build
```
Expected: Clean build, no type errors.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "test: verify onboarding wizard and dashboard tour integration"
```

---

## Critical Notes for Implementation

1. **Two-phase onboarding**: The onboarding wizard (3 steps) and the dashboard tour (7 steps) are tracked separately via `onboarding_completed_at` and `tour_completed_at`. This allows independent behavior — the wizard gates dashboard access, while the tour is a non-blocking overlay on the dashboard.

2. **Redirect loop prevention**: All three layouts (`(auth)`, `(dashboard)`, `(onboarding)`) MUST check `isLoading` before redirecting. Without this, the user object hasn't loaded yet and `isOnboarded` is `false`, causing a flash redirect to `/onboarding` on every page load.

3. **CandidateResponse construction sites**: There are 3+ places in `auth.py` where `CandidateResponse(...)` is manually constructed. ALL of them must get the four new fields (`onboarding_completed_at`, `onboarding_completed`, `tour_completed_at`, `tour_completed`). Missing even one will cause a 500 error on that endpoint.

4. **StepProfile form ref pattern**: The profile step uses `forwardRef` + `useImperativeHandle` to expose a `submit()` method. The wizard page's Next button calls `profileRef.current.submit()` rather than having a submit button inside the form. This keeps the navigation buttons consistent across all steps.

5. **Existing users**: After deploying migration 023, all existing users will have both fields as NULL. The **resume logic will auto-complete the wizard** for users who already have profile data + DNA — they'll be redirected directly to the dashboard where the tour overlay starts. To skip everything for existing users, run: `UPDATE candidates SET onboarding_completed_at = NOW(), tour_completed_at = NOW();`

6. **The existing `OnboardingChecklist` component** (`src/components/dashboard/onboarding-checklist.tsx`) remains unchanged. It serves a different purpose — post-onboarding task tracking (upload resume, discover companies, send outreach). The wizard handles first-time setup; the checklist handles ongoing progress.

7. **Tour spotlight positioning**: The `TourSpotlight` component uses `getBoundingClientRect()` and recalculates after scroll. Sidebar nav items may be partially off-screen — `scrollIntoView({ block: "center" })` handles this. On mobile, sidebar tour steps should be skipped (sidebar is hidden on mobile). Add a check: `if (window.innerWidth < 1024) skip sidebar steps`.

8. **data-tour attributes**: These must be added to the OUTER wrapper element of each section, not to inner components. The spotlight calculates its cutout from this element's bounding rect. If the attribute is on a deeply nested element, the spotlight will be too small.
