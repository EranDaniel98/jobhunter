# CI/CD, Email Verification, A/B Testing & Resume Bullets — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add CI/CD pipeline, email verification flow, A/B outreach testing, and resume bullet suggestions to complete the production-readiness and AI differentiation features.

**Architecture:** GitHub Actions for CI with service containers (Postgres + Redis). Email verification uses existing JWT infrastructure with Redis-based rate limiting. A/B testing adds a `variant` field to OutreachMessage and generates two tone variants per draft. Resume bullets extend the company dossier prompt and schema.

**Tech Stack:** GitHub Actions, FastAPI, SQLAlchemy async, PyJWT, Redis, Alembic, React, shadcn/ui, Tailwind CSS.

---

## Files Summary

| # | Task | Action | Files |
|---|------|--------|-------|
| 1 | CI/CD | CREATE | `.github/workflows/ci.yml` |
| 2 | Email Verify — Backend | CREATE | `backend/alembic/versions/008_email_verified.py` |
| | | MODIFY | `backend/app/models/candidate.py` |
| | | MODIFY | `backend/app/schemas/auth.py` |
| | | MODIFY | `backend/app/utils/security.py` |
| | | MODIFY | `backend/app/services/auth_service.py` |
| | | MODIFY | `backend/app/api/auth.py` |
| | | MODIFY | `backend/app/dependencies.py` |
| 3 | Email Verify — Frontend | CREATE | `frontend/src/components/dashboard/email-verification-banner.tsx` |
| | | MODIFY | `frontend/src/app/(dashboard)/dashboard/page.tsx` |
| | | MODIFY | `frontend/src/lib/api/auth.ts` |
| | | MODIFY | `frontend/src/lib/types.ts` |
| 4 | A/B Testing — Backend | CREATE | `backend/alembic/versions/009_outreach_variant.py` |
| | | MODIFY | `backend/app/models/outreach.py` |
| | | MODIFY | `backend/app/services/outreach_service.py` |
| | | MODIFY | `backend/app/api/outreach.py` |
| | | MODIFY | `backend/app/services/analytics_service.py` |
| 5 | A/B Testing — Frontend | CREATE | `frontend/src/components/companies/variant-picker.tsx` |
| | | MODIFY | `frontend/src/components/companies/contacts-list.tsx` |
| | | MODIFY | `frontend/src/lib/api/outreach.ts` |
| | | MODIFY | `frontend/src/lib/hooks/use-outreach.ts` |
| | | MODIFY | `frontend/src/lib/types.ts` |
| 6 | Resume Bullets — Backend | CREATE | `backend/alembic/versions/010_resume_bullets.py` |
| | | MODIFY | `backend/app/models/company.py` |
| | | MODIFY | `backend/app/services/company_service.py` |
| | | MODIFY | `backend/app/schemas/company.py` |
| 7 | Resume Bullets — Frontend | MODIFY | `frontend/src/components/companies/dossier-view.tsx` |
| | | MODIFY | `frontend/src/lib/types.ts` |

**7 tasks, ~7 new files, ~18 modified files.**

---

## Task 1: CI/CD Pipeline

**CREATE** `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: jobhunter
          POSTGRES_PASSWORD: jobhunter
          POSTGRES_DB: jobhunter
        options: >-
          --health-cmd "pg_isready -U jobhunter"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    defaults:
      run:
        working-directory: jobhunter/backend
    env:
      DATABASE_URL: postgresql+asyncpg://jobhunter:jobhunter@localhost:5432/jobhunter
      REDIS_URL: redis://localhost:6379/0
      JWT_SECRET: ci-test-secret-not-for-production
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      - run: uv sync --frozen
      - run: uv run pytest tests/ -x -q --tb=short

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: jobhunter/frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: jobhunter/frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run build
```

**Verification:** Push a branch and confirm both jobs pass on GitHub Actions.

**Commit:** `ci: add GitHub Actions workflow for backend tests and frontend build`

---

## Task 2: Email Verification — Backend

### Step 1: Add migration

**CREATE** `jobhunter/backend/alembic/versions/008_email_verified.py`

```python
"""add email_verified to candidates"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    # Existing users are considered verified; new users will be set to False by app code


def downgrade() -> None:
    op.drop_column("candidates", "email_verified")
```

Note: `server_default=true` so existing users aren't locked out. New registrations will explicitly set `email_verified=False` in app code.

### Step 2: Update Candidate model

**MODIFY** `jobhunter/backend/app/models/candidate.py`

Add after line 27 (`is_active`):
```python
email_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

### Step 3: Add verification token utility

**MODIFY** `jobhunter/backend/app/utils/security.py`

Add after `decode_token`:
```python
def create_verification_token(candidate_id: str) -> str:
    """Create a short-lived JWT for email verification (24h)."""
    payload = {
        "sub": candidate_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "type": "verify",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
```

### Step 4: Update auth schemas

**MODIFY** `jobhunter/backend/app/schemas/auth.py`

Add `email_verified` to `CandidateResponse`:
```python
class CandidateResponse(BaseModel):
    # ...existing fields...
    email_verified: bool = True  # <-- ADD after is_admin
```

### Step 5: Update auth service — send verification email on register

**MODIFY** `jobhunter/backend/app/services/auth_service.py`

Add imports at top:
```python
from app.dependencies import get_email_client
from app.config import settings
from app.utils.security import create_verification_token
```

In the `register` function, after creating the candidate, set `email_verified=False` and send email:
```python
candidate = Candidate(
    id=uuid.uuid4(),
    email=data.email,
    password_hash=hash_password(data.password),
    full_name=data.full_name,
    preferences=data.preferences.model_dump() if data.preferences else None,
    email_verified=False,  # <-- ADD
)
```

After `await db.refresh(candidate)`, add:
```python
# Send verification email (best-effort, don't block registration)
try:
    token = create_verification_token(str(candidate.id))
    verify_url = f"{settings.FRONTEND_URL}/login?verify={token}"
    email_client = get_email_client()
    await email_client.send(
        to=candidate.email,
        from_email=settings.SENDER_EMAIL,
        subject=f"Verify your {settings.APP_NAME} account",
        body=f"Hi {candidate.full_name},\n\nPlease verify your email by clicking: {verify_url}\n\nThis link expires in 24 hours.",
    )
    logger.info("verification_email_sent", candidate_id=str(candidate.id))
except Exception as e:
    logger.warning("verification_email_failed", candidate_id=str(candidate.id), error=str(e))
```

### Step 6: Add verify and resend endpoints

**MODIFY** `jobhunter/backend/app/api/auth.py`

Add imports:
```python
from fastapi import Query
from jwt import PyJWTError as JWTError
from app.utils.security import create_verification_token, decode_token
from app.config import settings
from app.dependencies import get_email_client
from app.infrastructure.redis_client import get_redis
```

Add after the `change_password` endpoint:

```python
@router.post("/verify", status_code=200)
async def verify_email(token: str = Query(...), db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    if payload.get("type") != "verify":
        raise HTTPException(status_code=400, detail="Invalid token type")

    candidate_id = payload.get("sub")
    result = await db.execute(
        select(Candidate).where(Candidate.id == uuid.UUID(candidate_id))
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Account not found")

    candidate.email_verified = True
    await db.commit()
    logger.info("email_verified", candidate_id=candidate_id)
    return {"message": "Email verified successfully"}


@router.post("/resend-verification", status_code=200)
async def resend_verification(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    if candidate.email_verified:
        return {"message": "Email already verified"}

    # Rate limit: 1 per 5 minutes
    redis = get_redis()
    cooldown_key = f"verify_cooldown:{candidate.id}"
    ttl = await redis.ttl(cooldown_key)
    if ttl and ttl > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {ttl // 60} min {ttl % 60}s before requesting another email",
        )

    await redis.setex(cooldown_key, 300, "1")  # 5 min cooldown

    token = create_verification_token(str(candidate.id))
    verify_url = f"{settings.FRONTEND_URL}/login?verify={token}"
    email_client = get_email_client()
    await email_client.send(
        to=candidate.email,
        from_email=settings.SENDER_EMAIL,
        subject=f"Verify your {settings.APP_NAME} account",
        body=f"Hi {candidate.full_name},\n\nPlease verify your email by clicking: {verify_url}\n\nThis link expires in 24 hours.",
    )
    logger.info("verification_email_resent", candidate_id=str(candidate.id))
    return {"message": "Verification email sent"}
```

Add `import uuid` and `from sqlalchemy import select` to the imports (add `uuid` if not already imported; `select` via `from sqlalchemy import select`).

### Step 7: Add email_verified to all CandidateResponse returns

**MODIFY** `jobhunter/backend/app/api/auth.py`

Add `email_verified=candidate.email_verified` to ALL `CandidateResponse(...)` constructors:
- In `register` endpoint
- In `get_me` endpoint
- In `update_me` endpoint

### Step 8: Guard protected routes (soft block)

**MODIFY** `jobhunter/backend/app/dependencies.py`

In `get_current_candidate`, after the `if not candidate` check, add:
```python
# Note: We don't block unverified users — we let the frontend show a banner.
# This keeps the UX smooth while encouraging verification.
```

We intentionally do NOT add a hard 403 block. The frontend will show a banner instead. This avoids locking users out of the app.

**Commit:** `feat: add email verification flow with JWT tokens and rate-limited resend`

---

## Task 3: Email Verification — Frontend

### Step 1: Add API functions

**MODIFY** `jobhunter/frontend/src/lib/api/auth.ts`

Add:
```typescript
export async function verifyEmail(token: string): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>("/auth/verify", null, {
    params: { token },
  });
  return data;
}

export async function resendVerification(): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>("/auth/resend-verification");
  return data;
}
```

### Step 2: Add email_verified to CandidateResponse type

**MODIFY** `jobhunter/frontend/src/lib/types.ts`

Add to `CandidateResponse` interface:
```typescript
email_verified: boolean;  // after is_admin
```

### Step 3: Handle verify token on login page

**MODIFY** `jobhunter/frontend/src/app/(auth)/login/page.tsx`

Add logic to check for `?verify=` query param on mount. If present, call `verifyEmail(token)` and show success/error toast. This handles the email link click.

```tsx
import { useSearchParams } from "next/navigation";
import { verifyEmail } from "@/lib/api/auth";

// Inside component:
const searchParams = useSearchParams();
const [verifying, setVerifying] = useState(false);

useEffect(() => {
  const token = searchParams.get("verify");
  if (token) {
    setVerifying(true);
    verifyEmail(token)
      .then(() => toast.success("Email verified! You can now log in."))
      .catch(() => toast.error("Verification link is invalid or expired"))
      .finally(() => setVerifying(false));
  }
}, [searchParams]);
```

### Step 4: Create verification banner component

**CREATE** `jobhunter/frontend/src/components/dashboard/email-verification-banner.tsx`

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Mail, Loader2 } from "lucide-react";
import { resendVerification } from "@/lib/api/auth";
import { toast } from "sonner";
import { toastError } from "@/lib/api/error-utils";

const COOLDOWN_KEY = "verify_resend_until";
const COOLDOWN_SECONDS = 300; // 5 minutes

export function EmailVerificationBanner() {
  const [loading, setLoading] = useState(false);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);

  // Restore cooldown from localStorage
  useEffect(() => {
    const until = localStorage.getItem(COOLDOWN_KEY);
    if (until) {
      const remaining = Math.max(0, Math.floor((Number(until) - Date.now()) / 1000));
      setCooldownRemaining(remaining);
    }
  }, []);

  // Countdown timer
  useEffect(() => {
    if (cooldownRemaining <= 0) return;
    const timer = setInterval(() => {
      setCooldownRemaining((prev) => {
        if (prev <= 1) {
          localStorage.removeItem(COOLDOWN_KEY);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldownRemaining]);

  const handleResend = useCallback(async () => {
    setLoading(true);
    try {
      await resendVerification();
      toast.success("Verification email sent — check your inbox");
      const until = Date.now() + COOLDOWN_SECONDS * 1000;
      localStorage.setItem(COOLDOWN_KEY, String(until));
      setCooldownRemaining(COOLDOWN_SECONDS);
    } catch (err) {
      toastError(err, "Failed to send verification email");
    } finally {
      setLoading(false);
    }
  }, []);

  const minutes = Math.floor(cooldownRemaining / 60);
  const seconds = cooldownRemaining % 60;

  return (
    <Card className="border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30">
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Mail className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
          <p className="text-sm text-amber-800 dark:text-amber-200">
            Please verify your email address. Check your inbox for the verification link.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={handleResend}
          disabled={loading || cooldownRemaining > 0}
        >
          {loading && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
          {cooldownRemaining > 0
            ? `Resend in ${minutes}:${String(seconds).padStart(2, "0")}`
            : "Didn't receive an email?"}
        </Button>
      </CardContent>
    </Card>
  );
}
```

### Step 5: Add banner to dashboard

**MODIFY** `jobhunter/frontend/src/app/(dashboard)/dashboard/page.tsx`

Import and render conditionally:
```tsx
import { EmailVerificationBanner } from "@/components/dashboard/email-verification-banner";

// Inside component, right after PageHeader and before quick actions:
{user && !user.email_verified && <EmailVerificationBanner />}
```

**Commit:** `feat: add email verification banner with resend cooldown timer`

---

## Task 4: A/B Testing — Backend

### Step 1: Add migration

**CREATE** `jobhunter/backend/alembic/versions/009_outreach_variant.py`

```python
"""add variant to outreach_messages"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outreach_messages", sa.Column("variant", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("outreach_messages", "variant")
```

### Step 2: Update OutreachMessage model

**MODIFY** `jobhunter/backend/app/models/outreach.py`

Add after `personalization_data` (line 24):
```python
variant: Mapped[str | None] = mapped_column(String(50))  # professional, conversational
```

### Step 3: Add variant drafting to outreach service

**MODIFY** `jobhunter/backend/app/services/outreach_service.py`

Add tone instructions after `MESSAGE_TYPE_INSTRUCTIONS`:
```python
VARIANT_INSTRUCTIONS = {
    "professional": "Use a formal, polished tone. Lead with credentials and mutual value. Structured and concise.",
    "conversational": "Use a warm, casual tone. Lead with genuine curiosity about the company. Friendly and authentic.",
}
```

Add `variant` parameter to `draft_message`:
```python
async def draft_message(
    db: AsyncSession, candidate_id: uuid.UUID, contact_id: uuid.UUID,
    language: str = "en", variant: str | None = None
) -> OutreachMessage:
```

In the prompt formatting, append variant instruction if provided:
```python
variant_instruction = ""
if variant and variant in VARIANT_INSTRUCTIONS:
    variant_instruction = f"\n- TONE: {VARIANT_INSTRUCTIONS[variant]}"

prompt = OUTREACH_PROMPT.format(
    # ...existing params...
    message_type_instructions=MESSAGE_TYPE_INSTRUCTIONS.get(message_type, "") + variant_instruction,
    # ...
)
```

Set variant on the created message:
```python
message = OutreachMessage(
    # ...existing fields...
    variant=variant,  # <-- ADD
)
```

Add new function for drafting variants:
```python
async def draft_variants(
    db: AsyncSession, candidate_id: uuid.UUID, contact_id: uuid.UUID, language: str = "en"
) -> list[OutreachMessage]:
    """Draft two message variants (professional + conversational) for A/B comparison."""
    variants = []
    for tone in ("professional", "conversational"):
        msg = await draft_message(db, candidate_id, contact_id, language=language, variant=tone)
        variants.append(msg)
    return variants
```

### Step 4: Add draft-variants endpoint

**MODIFY** `jobhunter/backend/app/api/outreach.py`

Add endpoint:
```python
@router.post("/{contact_id}/draft-variants", response_model=list[OutreachMessageResponse], status_code=201)
async def draft_message_variants(
    contact_id: str,
    language: str = Query(default="en"),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Draft two message variants for A/B comparison."""
    variants = await outreach_service.draft_variants(
        db, candidate.id, uuid.UUID(contact_id), language=language
    )
    return [_message_to_response(m) for m in variants]
```

### Step 5: Add variant to analytics

**MODIFY** `jobhunter/backend/app/services/analytics_service.py`

Add a new function for variant stats:
```python
async def get_variant_stats(db: AsyncSession, candidate_id: uuid.UUID) -> dict:
    """Get outreach stats grouped by variant for A/B analysis."""
    sent_statuses = ("sent", "delivered", "opened", "replied")
    opened_statuses = ("opened", "replied")

    result = await db.execute(
        select(
            OutreachMessage.variant,
            func.count(case((OutreachMessage.status.in_(sent_statuses), 1))).label("sent"),
            func.count(case((OutreachMessage.status.in_(opened_statuses), 1))).label("opened"),
            func.count(case((OutreachMessage.status == "replied", 1))).label("replied"),
        )
        .where(
            OutreachMessage.candidate_id == candidate_id,
            OutreachMessage.variant.isnot(None),
        )
        .group_by(OutreachMessage.variant)
    )
    rows = result.all()

    by_variant = {}
    for r in rows:
        sent = r.sent or 0
        by_variant[r.variant] = {
            "sent": sent,
            "opened": r.opened or 0,
            "replied": r.replied or 0,
            "open_rate": (r.opened or 0) / sent if sent > 0 else 0.0,
            "reply_rate": (r.replied or 0) / sent if sent > 0 else 0.0,
        }
    return by_variant
```

**Commit:** `feat: add A/B testing with variant drafting and analytics`

---

## Task 5: A/B Testing — Frontend

### Step 1: Update types

**MODIFY** `jobhunter/frontend/src/lib/types.ts`

Add `variant` to `OutreachMessageResponse`:
```typescript
variant: string | null;  // after personalization_data or status
```

### Step 2: Add API function

**MODIFY** `jobhunter/frontend/src/lib/api/outreach.ts`

Add:
```typescript
export async function draftVariants(
  contactId: string,
  language = "en"
): Promise<OutreachMessageResponse[]> {
  const { data } = await api.post<OutreachMessageResponse[]>(
    `/outreach/${contactId}/draft-variants`,
    null,
    { params: { language } }
  );
  return data;
}
```

### Step 3: Add hook

**MODIFY** `jobhunter/frontend/src/lib/hooks/use-outreach.ts`

Add:
```typescript
export function useDraftVariants() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, language }: { contactId: string; language?: string }) =>
      outreachApi.draftVariants(contactId, language),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages"] });
    },
  });
}
```

### Step 4: Create variant picker component

**CREATE** `jobhunter/frontend/src/components/companies/variant-picker.tsx`

A dialog that shows two message variants side-by-side. User clicks "Use this" on their preferred variant. The other draft is deleted.

```tsx
"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import type { OutreachMessageResponse } from "@/lib/types";
import { useDeleteMessage } from "@/lib/hooks/use-outreach";
import { toast } from "sonner";

interface VariantPickerProps {
  variants: OutreachMessageResponse[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPicked: () => void;
}

export function VariantPicker({ variants, open, onOpenChange, onPicked }: VariantPickerProps) {
  const deleteMutation = useDeleteMessage();

  function pickVariant(keep: OutreachMessageResponse, discard: OutreachMessageResponse) {
    deleteMutation.mutate(discard.id, {
      onSuccess: () => {
        toast.success(`Kept ${keep.variant || "message"} variant as draft`);
        onPicked();
        onOpenChange(false);
      },
      onError: () => {
        // Even if delete fails, the pick is fine — user has both drafts
        onPicked();
        onOpenChange(false);
      },
    });
  }

  if (variants.length < 2) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Pick a message variant</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          {variants.map((v, i) => {
            const other = variants[1 - i];
            return (
              <div key={v.id} className="flex flex-col gap-3 rounded-lg border p-4">
                <Badge variant="secondary" className="w-fit capitalize">
                  {v.variant || `Variant ${i + 1}`}
                </Badge>
                {v.subject && (
                  <p className="text-sm font-medium">{v.subject}</p>
                )}
                <p className="text-sm text-muted-foreground whitespace-pre-wrap flex-1">
                  {v.body}
                </p>
                <Button
                  size="sm"
                  onClick={() => pickVariant(v, other)}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
                  Use this
                </Button>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

### Step 5: Wire into contacts list

**MODIFY** `jobhunter/frontend/src/components/companies/contacts-list.tsx`

Add a "Draft with A/B" button next to the existing "Draft Email" button for each contact. When clicked, calls `useDraftVariants`, then opens the `VariantPicker` dialog with the two results. User picks one, the other is deleted.

Import:
```tsx
import { useDraftVariants } from "@/lib/hooks/use-outreach";
import { VariantPicker } from "@/components/companies/variant-picker";
```

Add state:
```tsx
const [abVariants, setAbVariants] = useState<OutreachMessageResponse[]>([]);
const [showPicker, setShowPicker] = useState(false);
const variantsMutation = useDraftVariants();
```

Add button:
```tsx
<Button
  size="sm"
  variant="outline"
  onClick={() =>
    variantsMutation.mutate(
      { contactId: contact.id },
      {
        onSuccess: (variants) => { setAbVariants(variants); setShowPicker(true); },
        onError: (err) => toastError(err, "Failed to draft variants"),
      }
    )
  }
  disabled={variantsMutation.isPending}
>
  {variantsMutation.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
  A/B Draft
</Button>
```

Add dialog at the end:
```tsx
<VariantPicker variants={abVariants} open={showPicker} onOpenChange={setShowPicker} onPicked={() => setAbVariants([])} />
```

**Commit:** `feat: add A/B variant picker for outreach messages`

---

## Task 6: Resume Bullets — Backend

### Step 1: Add migration

**CREATE** `jobhunter/backend/alembic/versions/010_resume_bullets.py`

```python
"""add resume_bullets to company_dossiers"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_dossiers", sa.Column("resume_bullets", ARRAY(sa.String(500)), nullable=True))


def downgrade() -> None:
    op.drop_column("company_dossiers", "resume_bullets")
```

### Step 2: Update CompanyDossier model

**MODIFY** `jobhunter/backend/app/models/company.py`

Add after `recent_news` (line 54):
```python
resume_bullets: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
```

### Step 3: Update dossier prompt and schema

**MODIFY** `jobhunter/backend/app/services/company_service.py`

Update `DOSSIER_PROMPT` — add to the "Generate a JSON dossier" section:
```
- resume_bullets: array of 3-5 specific bullet points the candidate should add or emphasize on their resume to be a stronger match for THIS company. Reference specific skills, technologies, or experiences that align with the company's needs. Each bullet should be actionable (e.g. "Highlight your experience with distributed systems — their tech stack relies heavily on microservices").
```

Update `DOSSIER_SCHEMA` — add to `properties`:
```python
"resume_bullets": {
    "type": "array",
    "items": {"type": "string"},
},
```

Add `"resume_bullets"` to the `required` list.

Update `research_company` function — add after `dossier.recent_news = ...`:
```python
dossier.resume_bullets = dossier_data.get("resume_bullets")
```

### Step 4: Update schema

**MODIFY** `jobhunter/backend/app/schemas/company.py`

Add to `CompanyDossierResponse`:
```python
resume_bullets: list[str] | None = None  # after recent_news
```

**Commit:** `feat: add resume bullet suggestions to company dossier`

---

## Task 7: Resume Bullets — Frontend

### Step 1: Update types

**MODIFY** `jobhunter/frontend/src/lib/types.ts`

Add to `CompanyDossierResponse`:
```typescript
resume_bullets: string[] | null;  // after recent_news
```

### Step 2: Add card to dossier view

**MODIFY** `jobhunter/frontend/src/components/companies/dossier-view.tsx`

Add import:
```tsx
import { Lightbulb } from "lucide-react";
```

Add a new card after the "Why Hire Me" card (after line 94):
```tsx
{dossier.resume_bullets && dossier.resume_bullets.length > 0 && (
  <Card className="md:col-span-2">
    <CardHeader>
      <CardTitle className="flex items-center gap-2 text-base">
        <Lightbulb className="h-4 w-4" />
        Resume Tips for This Company
      </CardTitle>
    </CardHeader>
    <CardContent>
      <ul className="space-y-2">
        {dossier.resume_bullets.map((bullet, i) => (
          <li key={i} className="flex gap-2 text-sm text-muted-foreground">
            <span className="shrink-0 text-primary">•</span>
            {bullet}
          </li>
        ))}
      </ul>
    </CardContent>
  </Card>
)}
```

The `md:col-span-2` makes it span the full width of the 2-column grid.

**Commit:** `feat: display resume bullet suggestions in company dossier`

---

## Verification

After all 7 tasks:

1. `cd jobhunter/frontend && npm run build` — no TypeScript errors
2. `cd jobhunter/backend && uv run pytest tests/test_auth.py -x -q` — all pass
3. Push to GitHub and verify CI workflow runs and passes
4. Manual checks:
   - Registration sends verification email, login page handles `?verify=` token
   - Dashboard shows amber verification banner for unverified users
   - "Didn't receive an email?" button has 5-minute cooldown with countdown
   - Company contacts list has "A/B Draft" button, opens side-by-side picker
   - Picking a variant keeps one draft, deletes the other
   - Company dossier shows "Resume Tips" card with 3-5 bullet points
   - CI runs backend tests and frontend build on push/PR
