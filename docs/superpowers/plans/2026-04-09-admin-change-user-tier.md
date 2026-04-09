# Admin — Change User Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up a frontend UI in the admin user-detail drawer so admins can change any user's `plan_tier` between `free`, `explorer`, and `hunter`.

**Architecture:** Frontend-only change. Backend endpoint `PATCH /admin/users/{id}/plan` and audit logging already exist. We add: (1) an API client function, (2) a React Query mutation hook, (3) a "Plan tier" row + confirmation dialog in the existing `UserDetailDrawer`, and (4) the missing `plan_tier` field on the `AdminUser` TS type.

**Tech Stack:** Next.js + React, TanStack Query, shadcn/ui (`Select`, `AlertDialog`, `Badge`), sonner toasts, axios (`api` client).

**Spec:** `docs/superpowers/specs/2026-04-09-admin-change-user-tier-design.md`

---

## File Structure

- **Modify** `jobhunter/frontend/src/lib/types.ts` — add `plan_tier: PlanTier` to `AdminUser`
- **Modify** `jobhunter/frontend/src/lib/api/admin.ts` — add `updateUserPlan()` function
- **Modify** `jobhunter/frontend/src/lib/hooks/use-admin.ts` — add `useUpdateUserPlan()` mutation hook
- **Modify** `jobhunter/frontend/src/components/admin/user-detail-drawer.tsx` — add tier display row, edit mode with `Select`, confirmation `AlertDialog`, self-guard

No tests — the admin frontend has no test infra in this repo. Verification is manual (see Task 5).

---

## Task 1: Add `plan_tier` to `AdminUser` type

**Files:**
- Modify: `jobhunter/frontend/src/lib/types.ts` (around line 175, `AdminUser` interface)

`PlanTier` is already exported from this file at line 278, so no new type definition is needed.

- [ ] **Step 1: Add `plan_tier` field to `AdminUser`**

In `jobhunter/frontend/src/lib/types.ts`, change the `AdminUser` interface from:

```ts
export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  is_admin: boolean;
  created_at: string;
  companies_count: number;
  messages_sent_count: number;
  is_active: boolean;
}
```

to:

```ts
export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  is_admin: boolean;
  created_at: string;
  companies_count: number;
  messages_sent_count: number;
  is_active: boolean;
  plan_tier: PlanTier;
}
```

`PlanTier` is already defined at line 278 of the same file as `"free" | "explorer" | "hunter"`. No import needed (same file).

- [ ] **Step 2: Typecheck**

Run: `cd jobhunter/frontend && rtk tsc --noEmit`
Expected: PASS (no new errors — the field is additive and the backend already returns it).

- [ ] **Step 3: Commit**

```bash
rtk git add jobhunter/frontend/src/lib/types.ts
rtk git commit -m "types(admin): add plan_tier to AdminUser"
```

---

## Task 2: Add `updateUserPlan` API client function

**Files:**
- Modify: `jobhunter/frontend/src/lib/api/admin.ts` (after `toggleActive`, around line 57)

- [ ] **Step 1: Add the function and import `PlanTier`**

In `jobhunter/frontend/src/lib/api/admin.ts`, add `PlanTier` to the existing type import block at the top:

```ts
import type {
  SystemOverview,
  AdminUserList,
  AdminUserDetail,
  RegistrationTrend,
  InviteChainItem,
  TopUserItem,
  ActivityFeedItem,
  AuditLogItem,
  BroadcastResponse,
  WaitlistListResponse,
  WaitlistInviteResponse,
  WaitlistBatchInviteResponse,
  WaitlistStatus,
  EmailHealthResponse,
  PlanTier,
} from "../types";
```

Then add this function immediately after `toggleActive` (which ends around line 57):

```ts
export async function updateUserPlan(
  id: string,
  planTier: PlanTier
): Promise<AdminUserDetail> {
  const { data } = await api.patch<AdminUserDetail>(
    `/admin/users/${id}/plan`,
    { plan_tier: planTier }
  );
  return data;
}
```

Note the URL: the backend route is `PATCH /admin/users/{user_id}/plan` (see `jobhunter/backend/app/api/admin.py:166`). The axios `api` client already prefixes `/api/v1`.

- [ ] **Step 2: Typecheck**

Run: `cd jobhunter/frontend && rtk tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
rtk git add jobhunter/frontend/src/lib/api/admin.ts
rtk git commit -m "feat(admin-api): add updateUserPlan client"
```

---

## Task 3: Add `useUpdateUserPlan` mutation hook

**Files:**
- Modify: `jobhunter/frontend/src/lib/hooks/use-admin.ts` (after `useDeleteUser`, around line 75)

- [ ] **Step 1: Add the hook**

In `jobhunter/frontend/src/lib/hooks/use-admin.ts`, add `PlanTier` to the existing types import:

```ts
import type { WaitlistStatus, PlanTier } from "@/lib/types";
```

Then add this hook immediately after `useDeleteUser`:

```ts
export function useUpdateUserPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, planTier }: { id: string; planTier: PlanTier }) =>
      adminApi.updateUserPlan(id, planTier),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      qc.invalidateQueries({ queryKey: ["admin", "user", vars.id] });
      qc.invalidateQueries({ queryKey: ["admin", "audit-log"] });
    },
  });
}
```

Mirrors the existing `useToggleAdmin` / `useToggleActive` pattern but also invalidates the specific user-detail query, since the drawer reads from it.

- [ ] **Step 2: Typecheck**

Run: `cd jobhunter/frontend && rtk tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
rtk git add jobhunter/frontend/src/lib/hooks/use-admin.ts
rtk git commit -m "feat(admin-hooks): add useUpdateUserPlan"
```

---

## Task 4: Wire up the Plan tier row in `UserDetailDrawer`

**Files:**
- Modify: `jobhunter/frontend/src/components/admin/user-detail-drawer.tsx`

This is the only user-visible change. It touches imports, component state, a handler, and the JSX between the existing "Details" block (line 126) and the "Stats" grid (line 151).

- [ ] **Step 1: Update imports**

Replace the existing hook import at line 3:

```ts
import { useAdminUser, useToggleAdmin, useToggleActive, useDeleteUser } from "@/lib/hooks/use-admin";
```

with:

```ts
import {
  useAdminUser,
  useToggleAdmin,
  useToggleActive,
  useDeleteUser,
  useUpdateUserPlan,
} from "@/lib/hooks/use-admin";
```

Add a `PlanTier` type import (new import line, after line 3):

```ts
import type { PlanTier } from "@/lib/types";
```

Add `Select` primitives to the UI imports (new block near the other `@/components/ui/*` imports):

```ts
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
```

Add `CreditCard` to the `lucide-react` import list (it's already importing `Shield`, `ShieldOff`, etc.):

```ts
import {
  Shield,
  ShieldOff,
  UserCheck,
  UserX,
  Trash2,
  Loader2,
  Building2,
  Mail,
  Calendar,
  Link2,
  CreditCard,
} from "lucide-react";
```

- [ ] **Step 2: Add state, constants, mutation, and handler**

At the top of the component body (after the existing `deleteUser` / `showDeleteConfirm` declarations around line 50), add:

```ts
const updatePlan = useUpdateUserPlan();
const [isEditingTier, setIsEditingTier] = useState(false);
const [pendingTier, setPendingTier] = useState<PlanTier | null>(null);

const TIER_OPTIONS: { value: PlanTier; label: string }[] = [
  { value: "free", label: "Free" },
  { value: "explorer", label: "Explorer" },
  { value: "hunter", label: "Hunter" },
];

const handleTierSelect = (value: string) => {
  if (!user) return;
  const next = value as PlanTier;
  if (next === user.plan_tier) {
    setIsEditingTier(false);
    return;
  }
  setPendingTier(next);
};

const handleConfirmTierChange = () => {
  if (!user || !pendingTier) return;
  const newTier = pendingTier;
  updatePlan.mutate(
    { id: user.id, planTier: newTier },
    {
      onSuccess: () => {
        toast.success(`Tier updated to ${newTier}`);
        setIsEditingTier(false);
        setPendingTier(null);
      },
      onError: (err: unknown) => {
        const message =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? "Failed to update tier";
        toast.error(message);
        setPendingTier(null);
      },
    }
  );
};

const handleCancelTierEdit = () => {
  setIsEditingTier(false);
  setPendingTier(null);
};
```

- [ ] **Step 3: Add the Plan tier row to the JSX**

Between the `Details` block (the `<div className="space-y-3">...</div>` ending around line 146) and the `<Separator />` before the Stats grid (line 148), insert a new separator + tier section. The result should look like:

```tsx
              {/* Details */}
              <div className="space-y-3">
                {/* ...existing calendar/invite rows... */}
              </div>

              <Separator />

              {/* Plan tier */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <CreditCard className="h-4 w-4 text-muted-foreground" />
                  <span className="text-muted-foreground">Plan tier:</span>
                  {!isEditingTier ? (
                    <>
                      <Badge variant="outline" className="capitalize">
                        {user.plan_tier}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="ml-auto h-7 px-2"
                        disabled={isSelf}
                        title={isSelf ? "You cannot change your own tier" : undefined}
                        onClick={() => setIsEditingTier(true)}
                      >
                        Edit
                      </Button>
                    </>
                  ) : (
                    <div className="ml-auto flex items-center gap-2">
                      <Select
                        value={user.plan_tier}
                        onValueChange={handleTierSelect}
                        disabled={updatePlan.isPending}
                      >
                        <SelectTrigger className="h-8 w-[130px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {TIER_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2"
                        onClick={handleCancelTierEdit}
                        disabled={updatePlan.isPending}
                      >
                        Cancel
                      </Button>
                    </div>
                  )}
                </div>
              </div>

              <Separator />

              {/* Stats */}
              <div className="grid grid-cols-2 gap-4">
                {/* ...existing companies/messages grid... */}
              </div>
```

Don't modify the existing Details or Stats contents — only insert the new Separator + Plan tier block between them.

- [ ] **Step 4: Add the tier-change confirmation `AlertDialog`**

At the bottom of the component, next to the existing delete-confirmation `AlertDialog` (around line 221), add a sibling `AlertDialog`:

```tsx
      <AlertDialog
        open={pendingTier !== null}
        onOpenChange={(open) => {
          if (!open) setPendingTier(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Change plan tier?</AlertDialogTitle>
            <AlertDialogDescription>
              Change {user?.email}'s tier from{" "}
              <span className="font-medium capitalize">{user?.plan_tier}</span>{" "}
              to{" "}
              <span className="font-medium capitalize">{pendingTier}</span>.
              This takes effect immediately and is recorded in the audit log.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={updatePlan.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmTierChange}
              disabled={updatePlan.isPending}
            >
              {updatePlan.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
```

- [ ] **Step 5: Typecheck and lint**

Run: `cd jobhunter/frontend && rtk tsc --noEmit`
Expected: PASS.

Run: `cd jobhunter/frontend && rtk lint`
Expected: PASS (or only pre-existing warnings — no new errors).

- [ ] **Step 6: Commit**

```bash
rtk git add jobhunter/frontend/src/components/admin/user-detail-drawer.tsx
rtk git commit -m "feat(admin): change user plan tier from detail drawer"
```

---

## Task 5: Manual verification

**Files:** none

- [ ] **Step 1: Start the stack**

Run: `cd jobhunter && docker compose up -d`
Wait for backend healthcheck to pass, then: `cd frontend && rtk pnpm dev`

- [ ] **Step 2: Verify happy path**

1. Log in as an admin user.
2. Go to `/admin`.
3. Click a non-self user row. The drawer opens.
4. Confirm a new "Plan tier" row shows with the user's current tier as a badge.
5. Click **Edit**. A `Select` appears.
6. Pick a different tier. Confirmation dialog opens quoting the old and new tier.
7. Click **Confirm**. Toast reads `Tier updated to <new>`. Row returns to display mode with the new badge.
8. Close and reopen the drawer — the new tier persists.
9. Go to the admin audit log and confirm a `plan_tier_changed` (or equivalent) entry exists.

- [ ] **Step 3: Verify self-guard**

1. Open your own user row in the drawer.
2. The "Plan tier" row's Edit button is disabled with a tooltip "You cannot change your own tier".

- [ ] **Step 4: Verify cancel flows**

1. Click Edit, pick a new tier, then click **Cancel** in the confirmation dialog. Drawer returns to edit mode with the original tier; no mutation fires.
2. Click Edit, then click the inline **Cancel** button next to the Select. Row returns to display mode unchanged.

- [ ] **Step 5: Verify error handling**

Temporarily edit `updateUserPlan` in `lib/api/admin.ts` to send `{ plan_tier: "bogus" }`, reload, attempt a tier change. The backend returns 400 `Invalid tier: bogus`, and the toast surfaces that detail. Revert the change afterward.

- [ ] **Step 6: Final commit (if any verification fixes were needed)**

If any issues surfaced and required follow-up edits, commit them as a fixup:

```bash
rtk git add -A
rtk git commit -m "fix(admin): address manual verification findings"
```

Otherwise skip this step.

---

## Self-Review Notes

- **Spec coverage:** UX (drawer row + Edit + Select + confirmation) → Task 4. API client → Task 2. Hook → Task 3. Type → Task 1. Self-guard → Task 4 Step 3. Error handling (backend detail surfaced) → Task 4 Step 2. Manual test plan → Task 5. All spec items mapped.
- **Type consistency:** Hook parameter `planTier`, API function parameter `planTier`, backend body `plan_tier` (snake_case) — naming is consistent at each boundary.
- **No placeholders:** All code blocks are complete and copy-pasteable.
