# UX Enhancements Design Spec

**Goal:** Improve user experience across 4 areas — progress feedback, loading skeletons, empty states, and side panel consistency.

**Scope:** Frontend only. No backend changes. All operations use existing real statuses from the API.

---

## A. Progress Feedback — Inline Status Indicators

### Approach

Replace silent waits with **prominent inline progress indicators** that appear where the user triggered the action. Only show real statuses from the backend — no fake steps.

### Operations & Their Real Statuses

| Operation | States | Source | Current UX |
|-----------|--------|--------|------------|
| Company Discovery | `isPending` → success/error | Mutation state (single POST) | Button text changes to "Discovering..." — easy to miss |
| Company Research | `pending` → `in_progress` → `completed` / `failed` | `research_status` field, polled every 3s | Generic "Researching company..." spinner in dossier tab |
| Resume Parsing | `pending` → `completed` / `failed` | `parse_status` field | Upload button spinner, then toast. No visible processing state |
| Interview Generation | `pending` → `generating` → `in_progress` → `completed` | `status` field, polled every 3s | Skeleton loaders replace content, button spinner |
| Job Analysis | `pending` → `analyzed` / `failed` | `status` field, polled every 3s | Indeterminate progress bar + "Analysis in progress" text |

### Component: `<OperationProgress>`

A shared component used by all 5 operations.

**Props:**
- `status: string` — current operation status
- `label: string` — e.g., "Discovering companies..."
- `steps?: { key: string; label: string }[]` — optional step definitions for multi-state operations
- `onRetry?: () => void` — shown on `failed` status
- `errorMessage?: string` — custom error text for failed state

**Behavior:**
- **Single-state operations** (discovery, resume parsing, job analysis): Show a Loader2 spinner + label + indeterminate progress bar. No step indicators.
- **Multi-state operations** (research, interview): Show step indicators with the current step highlighted. Completed steps get a checkmark. Uses the real status to determine which step is active. Reuse the existing `StepIndicator` pattern from onboarding for visual consistency.
- **Failed state**: Red alert icon + error message + "Retry" button if `onRetry` provided.
- **Completed state**: Green check + success message. Stays visible until data refreshes and replaces the progress indicator naturally.

**Accessibility:**
- `role="progressbar"` on the progress bar element
- `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"` for determinate progress
- `aria-label="Operation progress"` with dynamic description
- `aria-live="polite"` on status text for screen reader updates
- Respect `prefers-reduced-motion` — disable animations, keep text updates

**Placement (exact locations):**
- **Company Discovery**: Replace discover panel footer (companies/page.tsx ~line 305-314) with `OperationProgress` while mutation is pending
- **Company Research**: Replace the `DossierView` "Researching company..." block (dossier-view.tsx lines 23-30) with `OperationProgress` showing `pending` → `in_progress` steps
- **Resume Parsing**: Add `OperationProgress` card between `UploadZone` and empty state (resume/page.tsx ~line 279) while `parse_status` is `pending`
- **Interview Generation**: Replace skeleton loaders (interview-prep/page.tsx ~lines 344-350) with `OperationProgress` per prep type. The Readiness Tracker (lines 247-293) already shows per-type status — enhance it with live progress for the active type
- **Job Analysis**: Replace the generic loading card (apply/page.tsx ~lines 465-478) with `OperationProgress`

### Visual Design

- Full-width card with rounded corners, subtle border, `p-6` padding
- Left-aligned Loader2 spinner (animate-spin) + bold label + muted sublabel
- For multi-state: horizontal step indicators (circles connected by lines), matching existing onboarding StepIndicator pattern
- Animated indeterminate progress bar for single-state (CSS `shimmer` keyframe matching existing Skeleton animation at 1.5s)
- Colors from existing semantic system:
  - Active: `bg-primary/15 text-primary`
  - Pending: `bg-muted text-muted-foreground`
  - Failed: `bg-destructive/15 text-destructive`
  - Completed: `bg-chart-3/15 text-chart-3`
- Dark mode: all colors use CSS custom properties, no hardcoded values

---

## B. Contextual Loading Skeletons

### Approach

Replace the generic `PageSkeleton` (4 cards + table) with **per-page skeletons that match the actual content layout**. Each page's `loading.tsx` gets a custom skeleton.

### Pages & Their Skeleton Layouts

| Page | Skeleton Layout (verified against actual page) |
|------|----------------|
| **Dashboard** | Greeting header skeleton + 4 stat cards (icon + number + label) + 2-column grid: left 2/3 pipeline card (4 stage bars), right 1/3 usage card + recent companies table (5 rows, 4 columns) |
| **Companies** | 4 stat badges row + search bar + sort dropdown + 4 status filter chips + responsive table (8 rows, 9 columns with responsive hiding) |
| **Company Detail** | Header (name w-48 + 2 badge skeletons + score circle) + tab bar (3 tabs) + 2-column card grid (4 cards) |
| **Resume & DNA** | Upload zone placeholder + section nav bar (3 tabs) + completeness card (circular progress placeholder + 6 checklist items) + skills grid (2-column, 8 pill shapes) |
| **Outreach** | Filter dropdowns (status + channel) + split-pane layout: left message list (8 rows with status dot + avatar + subject + timestamp), right detail panel (message body + timeline skeleton) |
| **Interview Prep** | Company selector dropdown + Readiness Tracker (6 prep type circles in row) + session cards (3 cards with title + status badge + date) |
| **Apply** | URL input bar + postings list (3 cards with title + company + status badge) + analysis panel placeholder |
| **Approvals** | Filter tabs (status + channel) + bulk action bar + table (5 rows with checkbox + user + action type + status + date) |
| **Analytics** | Header with 2 buttons + 6 stat cards in responsive grid + 2-column chart area (h-[250px] each) + channel breakdown rows + insights feed (3 insight cards) |
| **Settings** | Form sections (3 groups of label + input pairs) |
| **Admin** | Tab bar (6 tabs) + 4 stat cards + email health card + 2-column: registration chart (h-[300px]) + top users table (5 rows) |
| **Admin Waitlist** | 4 status count cards + quota indicator + toolbar + table (10 rows) |

### Implementation

- Each `loading.tsx` file imports `Skeleton` from shadcn and builds a layout matching its page
- Use varying skeleton widths (w-24, w-32, w-48, w-full) to hint at real content lengths
- Chart placeholders: use `Skeleton` with explicit height matching the real chart (h-[250px] or h-[300px])
- Maintain the existing `role="status"` and `aria-label` accessibility pattern
- Keep `PageSkeleton` as fallback for any pages not yet converted

---

## C. Actionable Empty States

### Approach

Every empty state gets a **primary CTA button** that guides the user to the next step. The existing `EmptyState` component already supports an `action` prop — most pages just don't use it.

### Top-Level Empty States & Their CTAs

| Page | Current Message | New CTA | Notes |
|------|----------------|---------|-------|
| **Companies** | "Upload a resume and discover companies, or add one manually." | Conditional: "Upload Resume" (if no resume) / "Discover Companies" (if resume exists) | Need to check resume state via existing query |
| **Outreach** | "Your first outreach starts at Companies" | "Go to Companies" → `/companies` | Already implemented correctly — no change needed |
| **Analytics** | "No data yet" (no CTA) | Add: "Discover Companies" → `/companies` | Currently missing action prop |
| **Interview Prep** | "Select a company to begin" (no CTA) | Add: "Browse Companies" → `/companies` | Top-level empty state lacks CTA |
| **Apply** | "No job postings yet" | "Analyze Job" → `setShowForm(true)` | Already implemented correctly — no change needed |
| **Approvals** | "No actions to review" (no CTA) | Add: "Go to Companies" → `/companies` | Currently missing action prop |
| **Resume** | "No DNA profile yet" (UploadZone visible above) | Keep as-is — UploadZone serves as implicit CTA | Upload mechanism already prominent |
| **Admin Activity** | "No activity yet" | No CTA (informational) | Correct — populates automatically |

### Nested/Sub-Section Empty States (missed in original spec)

| Component | Location | Current | New CTA |
|-----------|----------|---------|---------|
| **Dossier tab** (unapproved) | `dossier-view.tsx` | "Approve this company to generate a dossier." | No change — already has guidance text |
| **Contacts tab** (empty) | Company detail contacts tab | "No contacts found" | Add: "Discover Contacts" button |
| **Interview per-tab** | Each prep type tab | "No {type} prep yet" | Add: "Generate {type}" → trigger generate mutation |
| **Outreach detail panel** | Right side of split-pane | "Select a message to view details" | No change — instructional |
| **Analytics charts** | Funnel/pipeline charts | "No outreach data yet" | No change — charts populate from activity |

### Implementation

- Update 3 pages to add `action` prop: Analytics, Interview Prep, Approvals
- Add conditional CTA to Companies page (check resume existence)
- Add CTA to Interview Prep per-tab empty states
- For cross-page navigation, use `router.push()`
- For in-page actions, call existing mutation/dialog opener

---

## D. Side Panel Consistency

### Approach

Create a **shared panel layout pattern** used by all side panels (User Details, Incident Form, and any future drawers). Consistent spacing, section grouping, and visual hierarchy.

### Shared Pattern: `<PanelSection>`

A lightweight wrapper for grouping content inside drawers:

```tsx
interface PanelSectionProps {
  title: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
}
```

```tsx
<PanelSection title="Details" icon={Calendar}>
  {/* section content */}
</PanelSection>
```

**Renders:**
- Outer: `pt-5` top padding. First section gets no top border; subsequent sections get `border-t` divider.
- Title row: `flex items-center gap-2 mb-3` — icon (`h-4 w-4 text-muted-foreground`) + title (`text-xs font-medium uppercase tracking-wider text-muted-foreground`)
- Content: no extra padding (children control their own spacing)

**Accessibility:** `role="region"` + `aria-label={title}` on the section wrapper.

### Panel Width Standard

- Default: `sm:max-w-xl` (576px) — used by User Details and future drawers
- Wide: `sm:max-w-2xl` (672px) — Incident Form only (wider form fields)
- Base Sheet component already set to `sm:max-w-lg` (512px), overridden per-panel

### User Details Panel — Redesign

Current layout: SheetHeader (name, email, badges) → joined date → invited by → plan tier with inline edit → 2 stat cards (cramped) → Remove admin / Suspend / Delete buttons

New layout:
1. **Header section**: Name (text-xl font-bold), email (text-sm text-muted-foreground), badges (Admin amber, Active green) — add `pb-4` bottom padding + border-b separator
2. **Info section** (`<PanelSection title="Details" icon={Calendar}>`): Joined date, invited by, invite code — each row as `flex justify-between py-2`. Plan tier row: read mode shows label + badge + "Edit" ghost button (ml-auto); edit mode replaces badge with Select dropdown + "Cancel" text button. Tier change triggers existing AlertDialog confirmation.
3. **Stats section** (`<PanelSection title="Activity" icon={BarChart3}>`): Two stat cards side by side in `grid grid-cols-2 gap-3` — each card `rounded-lg border p-4 text-center` with icon + count (text-2xl font-bold) + label (text-xs muted)
4. **Actions section** (`<PanelSection title="Actions" icon={Settings}>`): Full-width buttons in vertical stack (`space-y-2`). "Remove admin" and "Suspend" as outline variant. "Delete user" as destructive variant at bottom with `mt-4 pt-4 border-t` separator. Both AlertDialogs (delete + tier change) remain as-is — they're separate components that overlay the panel.

### Incident Form Panel — Redesign

Current layout: SheetHeader → category radio cards (tight 2x2) → title input → description textarea → attachments → submit button

New layout:
1. **Header**: Title + description + `pb-4 border-b` separator
2. **Category section** (`<PanelSection title="Category">`): 2x2 grid with `gap-3` (up from current tight spacing). Each card gets `p-4` padding
3. **Details section** (`<PanelSection title="Details">`): Title + Description with `space-y-4` between fields (up from space-y-2). Description textarea gets `min-h-[120px]`
4. **Attachments section** (`<PanelSection title="Attachments">`): Upload area with dashed border (`border-2 border-dashed rounded-lg p-6`)
5. **Footer**: Submit button full-width, sticky to bottom (`sticky bottom-0 bg-background pt-4 pb-4 border-t`)

### Approvals Detail Panel — Redesign

The approvals page has a right-side Sheet (`approvals/page.tsx`) showing action details. Current layout: hand-rolled with `px-4 pb-6 space-y-4`. Should use `PanelSection` for consistency.

New layout:
1. **Header section**: Status badge + action type badge — `pb-4 border-b`
2. **Contact section** (`<PanelSection title="Contact" icon={User}>`): Name, email, company — each row `flex justify-between py-2`
3. **AI Reasoning section** (`<PanelSection title="AI Reasoning" icon={Brain}>`): Full-text reasoning in muted text block
4. **Message section** (`<PanelSection title="Message" icon={Mail}>`): Subject (font-medium) + body (prose style, border-l-2 pl-4)
5. **Actions section** (`<PanelSection title="Actions" icon={CheckCircle}>`): Approve (default variant) + Reject (outline variant) buttons full-width

Width: `sm:max-w-xl` (matches User Details standard).

### Other Sheet Usages

The mobile navigation Sheet (`components/layout/mobile-nav.tsx`, `side="left"`) does NOT use `PanelSection` — it has its own nav-specific layout and should remain unchanged.

---

## Cross-Cutting Concerns

### Color Consistency

All new components use semantic color tokens from `constants.ts` and CSS custom properties:
- Active/in-progress: `bg-primary/15 text-primary`
- Pending/idle: `bg-muted text-muted-foreground`
- Success/completed: `bg-chart-3/15 text-chart-3`
- Failed/error: `bg-destructive/15 text-destructive`

No hardcoded color values (no `bg-green-500`, `bg-red-500`, etc.).

### Animation Consistency

- Spinners: use existing `animate-spin` on `Loader2` icon
- Skeleton shimmer: use existing `shimmer` keyframe (1.5s ease-in-out)
- Progress bars: use existing `shimmer` keyframe for indeterminate state
- Transitions: `transition-all duration-200` for state changes
- `prefers-reduced-motion`: all animations disabled, text updates remain

### Dark Mode

All designs work in dark mode automatically via CSS custom properties. No `dark:` overrides needed since we use semantic tokens exclusively.

### Accessibility

- Loading skeletons: `role="status"` + `aria-label` (existing pattern)
- Progress bars: `role="progressbar"` + `aria-valuenow/min/max`
- Panel sections: `role="region"` + `aria-label`
- Status changes: `aria-live="polite"` on dynamic text
- Empty state CTAs: proper `button` elements with descriptive labels

---

## Component Summary

| New Component | Location | Purpose |
|--------------|----------|---------|
| `OperationProgress` | `src/components/shared/operation-progress.tsx` | Inline progress indicator for long-running operations |
| `PanelSection` | `src/components/shared/panel-section.tsx` | Grouped section inside side panels |
| 12 custom `loading.tsx` | `src/app/(dashboard)/*/loading.tsx` | Per-page contextual skeletons |

**Modified components:** ~8 pages (empty state CTAs + progress indicators), `dossier-view.tsx`, `user-detail-drawer.tsx`, `incident-form.tsx`, `approvals/page.tsx` (detail sheet)

---

## Out of Scope

- No backend changes — no new API endpoints or status fields
- No navigation/breadcrumb changes (user didn't prioritize)
- No mobile-specific changes beyond responsive skeleton layouts
- No new animations beyond existing patterns
