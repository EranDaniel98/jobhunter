# Admin — Change User Tier

**Date:** 2026-04-09
**Status:** Approved for planning
**Scope:** Frontend-only

## Context

Admins need to change a specific user's plan tier (`free`, `explorer`, `hunter`) from the admin UI — e.g. to comp a beta user, upgrade a support case, or revert after a refund.

The backend endpoint already exists:

- `PATCH /admin/users/{user_id}/plan` in `jobhunter/backend/app/api/admin.py:166`
- Body: `{ "plan_tier": "free" | "explorer" | "hunter" }`
- Validates via `PlanTier(new_tier)` in `app/services/admin_service.py:418`
- Writes to the admin audit log
- Returns `UserDetail`

No frontend wiring or UI exists for it. This spec covers only that gap.

## UX

The control lives in the existing `UserDetailDrawer` at `jobhunter/frontend/src/components/admin/user-detail-drawer.tsx`, alongside the current admin/active toggles.

- A new "Plan tier" row shows the current tier as a badge with an "Edit" button.
- Clicking Edit reveals a `<Select>` with options: `free`, `explorer`, `hunter`.
- Selecting a new tier opens an `AlertDialog` confirmation:
  > "Change {user.email}'s tier from {old} to {new}? This takes effect immediately and is recorded in the audit log."
- Confirm → mutation fires. Cancel → select reverts, row collapses back to display mode.
- The control is disabled while the mutation is in-flight.
- The control is disabled entirely if the admin is viewing their own user row (mirrors the existing `toggleAdmin` self-guard).
- On success: toast "Tier updated to {new}", invalidate user-detail and users-list queries, collapse back to display mode.
- On error: toast the backend error message (surfacing 400 "Invalid tier" and 404 "User not found"). Row stays in edit mode so the admin can retry or cancel.

No optimistic update — wait for the server response, then refetch. Simpler, and tier changes are rare enough that perceived latency doesn't matter.

## Implementation

### 1. API client — `jobhunter/frontend/src/lib/api/admin.ts`

Add:

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

Follows the same shape as `toggleAdmin` / `toggleActive` already in the file.

### 2. Type — `jobhunter/frontend/src/lib/types.ts`

If `PlanTier` is not already exported from types, add:

```ts
export type PlanTier = "free" | "explorer" | "hunter";
```

(Check first — the plans page may already define this. Reuse if so.)

### 3. Drawer — `jobhunter/frontend/src/components/admin/user-detail-drawer.tsx`

- Import `updateUserPlan`, `PlanTier`, the `Select` primitive, and `AlertDialog`.
- Add local state: `isEditingTier: boolean`, `pendingTier: PlanTier | null`.
- Add a React Query `useMutation` for `updateUserPlan`, keyed like the existing `toggleAdmin` mutation. `onSuccess`: invalidate `["admin", "user", userId]` and `["admin", "users"]`, toast, collapse edit state. `onError`: toast the error message.
- Render a new row in the drawer body:
  - Label: "Plan tier"
  - Display mode: current tier badge + "Edit" button
  - Edit mode: `<Select>` with the three tier options + Cancel button
- When the admin picks a new tier (different from current), open `AlertDialog`. Confirm → run mutation. Cancel → revert.
- Self-guard: if `userId === currentUserId`, render the display row with the Edit button disabled and a tooltip "You cannot change your own tier".

### 4. No backend changes

The endpoint, validation, and audit logging are already in place.

## Error handling

| Case | Backend response | Frontend behavior |
|------|------------------|-------------------|
| Invalid tier string | 400 `{detail: "Invalid tier: ..."}` | Toast the detail. Shouldn't happen (select is typed) but surface defensively. |
| User not found | 404 `{detail: "User not found"}` | Toast the detail. Drawer stays open. |
| Network error | — | Toast "Failed to update tier". Row stays in edit mode. |

## Testing

Manual smoke test via the admin UI, matching how other admin drawer controls are verified in this repo (there is no frontend test infra for admin components):

1. Log in as admin, open admin page, click a non-self user row.
2. Change tier from `free` → `hunter`, confirm dialog, verify toast + badge updates.
3. Refresh drawer, verify tier persisted.
4. Check audit log entry exists for the change.
5. Open own user row, verify tier edit is disabled.
6. Simulate backend 400 (e.g. temporarily send bad payload via devtools) and confirm the error toast surfaces.

## Out of scope

- Bulk tier changes
- Scheduled/time-bound tier changes (e.g. "downgrade in 30 days")
- Notifying the user of the tier change via email
- Adding new tiers
