# UX Enhancements Design Spec

**Goal:** Improve user experience across 4 areas — progress feedback, loading skeletons, empty states, and side panel consistency.

**Scope:** Frontend only. No backend changes. All operations use existing real statuses from the API.

---

## A. Progress Feedback — Inline Status Indicators

### Approach

Replace silent waits with **prominent inline progress indicators** that appear where the user triggered the action. Only show real statuses from the backend — no fake steps.

### Operations & Their Real Statuses

| Operation | States | Source |
|-----------|--------|--------|
| Company Discovery | `isPending` → success/error | Mutation state (single POST) |
| Company Research | `pending` → `in_progress` → `completed` / `failed` | `research_status` field, polled every 3s |
| Resume Parsing | `pending` → `completed` / `failed` | `parse_status` field |
| Interview Generation | `pending` → `generating` → `in_progress` → `completed` | `status` field, polled every 3s |
| Job Analysis | `pending` → `analyzed` / `failed` | `status` field, polled every 3s |

### Component: `<OperationProgress>`

A shared component used by all 5 operations.

**Props:**
- `status: string` — current operation status
- `label: string` — e.g., "Discovering companies..."
- `steps?: { key: string; label: string }[]` — optional step definitions for multi-state operations
- `onRetry?: () => void` — shown on `failed` status

**Behavior:**
- **Single-state operations** (discovery, resume parsing, job analysis): Show a Loader2 spinner + label + indeterminate progress bar. No step indicators.
- **Multi-state operations** (research, interview): Show step indicators with the current step highlighted. Completed steps get a checkmark. Uses the real status to determine which step is active.
- **Failed state**: Red alert icon + error message + "Retry" button if `onRetry` provided.
- **Completed state**: Green check + success message. Stays visible until data refreshes and replaces the progress indicator naturally.

**Placement:**
- Company Discovery: replaces the discover panel content while running
- Company Research: replaces the dossier tab loading spinner (the current "Researching company..." that we already fixed)
- Resume Parsing: shown below the upload zone while parsing
- Interview Generation: replaces the session area while generating
- Job Analysis: shown in the apply page while analyzing

### Visual Design

- Full-width card with rounded corners, subtle border
- Left-aligned spinner/icon + bold label + muted sublabel
- For multi-state: horizontal step indicators (circles connected by lines, matching existing shadcn style)
- Animated indeterminate progress bar for single-state (CSS animation, no JS timer)
- Uses existing `primary` color for active, `muted` for pending, `destructive` for failed, `chart-3` for completed

---

## B. Contextual Loading Skeletons

### Approach

Replace the generic `PageSkeleton` (4 cards + table) with **per-page skeletons that match the actual content layout**. Each page's `loading.tsx` gets a custom skeleton.

### Pages & Their Skeleton Layouts

| Page | Skeleton Layout |
|------|----------------|
| **Dashboard** | 4 stat cards (top row) + 2-column grid (usage card + recent activity list) |
| **Companies** | Search bar + sort buttons + 3-column grid of company cards (each with logo placeholder, name line, badges) |
| **Company Detail** | Header (name + badges + score) + tab bar + 2-column card grid |
| **Resume & DNA** | Upload zone placeholder + 2 stat cards + skills grid (2-column, 8 pill shapes) |
| **Outreach** | Filter tabs + table with 5 rows (avatar circle + name + email + status badge + date) |
| **Interview Prep** | Session list (3 cards with title line + status badge + date) |
| **Apply** | URL input bar + analysis card placeholder |
| **Approvals** | Filter tabs + table with 5 rows |
| **Analytics** | 4 stat cards + large chart area + 2-column breakdown |
| **Settings** | Form sections (3 groups of label + input pairs) |
| **Admin** | Tab bar + 5 stat cards + chart area + table |
| **Admin Waitlist** | 4 status count cards + toolbar + table |

### Implementation

- Each `loading.tsx` file imports `Skeleton` from shadcn and builds a layout matching its page
- Use varying skeleton widths (w-24, w-32, w-48, w-full) to hint at real content lengths
- Maintain the existing `role="status"` and `aria-label` accessibility pattern
- Delete the generic `PageSkeleton` component after all pages have custom skeletons (or keep as fallback)

---

## C. Actionable Empty States

### Approach

Every empty state gets a **primary CTA button** that guides the user to the next step. The existing `EmptyState` component already supports an `action` prop — most pages just don't use it.

### Empty States & Their CTAs

| Page | Current Message | New CTA |
|------|----------------|---------|
| **Companies** | "Upload a resume and discover companies, or add one manually." | Two buttons: "Upload Resume" (if no resume) / "Discover Companies" (if resume exists) |
| **Outreach** | "No messages yet" | "Go to Companies" → navigate to approve a company first |
| **Analytics** | "Not enough data yet" | "Discover Companies" → start the pipeline |
| **Interview Prep** | "No interview prep sessions" | "Start a Session" → open the new session flow |
| **Apply** | "No applications yet" | "Analyze a Job Posting" → focus the URL input |
| **Approvals** | "No pending approvals" | "Go to Companies" → discover or approve companies |
| **Resume** | "Upload your resume to get started" | "Upload Resume" → trigger file picker |
| **Admin Activity** | "No activity yet" | No CTA (informational — activity populates automatically) |

### Implementation

- Update each page's empty state to pass `action={{ label, onClick }}` to `<EmptyState>`
- For cross-page navigation, use `router.push()`
- For in-page actions (upload, discover), call the existing mutation/dialog opener
- Add secondary text below CTA: brief explanation of what happens next

---

## D. Side Panel Consistency

### Approach

Create a **shared panel layout pattern** used by all side panels (User Details, Incident Form, and any future drawers). Consistent spacing, section grouping, and visual hierarchy.

### Shared Pattern: `<PanelSection>`

A lightweight wrapper for grouping content inside drawers:

```tsx
<PanelSection title="Profile" icon={User}>
  {/* section content */}
</PanelSection>
```

**Renders:** Icon + title in muted uppercase label style, content below with consistent padding.

### Panel Width Standard

All side panels use `sm:max-w-xl` (576px) as the standard width override. This is already set for the User Details drawer. The Incident Form uses `sm:max-w-2xl` (672px) because it has wider form fields — this is acceptable as the one exception.

### User Details Panel — Redesign

Current: flat list of fields, cramped stats.

New layout:
1. **Header section**: Name (large), email, badges (Admin/Active) — existing, add more vertical padding
2. **Info section** (`<PanelSection title="Details">`): Joined date, invited by, plan tier — each on its own row with label + value, consistent spacing
3. **Stats section** (`<PanelSection title="Activity">`): Two stat cards side by side (Companies / Messages Sent) — existing cards but with more padding
4. **Actions section** (`<PanelSection title="Actions">`): Remove admin / Suspend / Delete buttons — vertical stack with full-width buttons, destructive actions at bottom with separator

### Incident Form Panel — Redesign

Current: category cards feel tight, form fields crowded.

New layout:
1. **Header**: existing title + description — add bottom border separator
2. **Category section** (`<PanelSection title="Category">`): 2x2 grid of category cards with more padding between them
3. **Details section** (`<PanelSection title="Details">`): Title + Description fields with proper label spacing (gap-4 between fields instead of gap-2)
4. **Attachments section** (`<PanelSection title="Attachments">`): File upload area with dashed border zone
5. **Footer**: Submit button pinned to bottom of panel (sticky)

---

## Component Summary

| New Component | Location | Purpose |
|--------------|----------|---------|
| `OperationProgress` | `src/components/shared/operation-progress.tsx` | Inline progress indicator for long-running operations |
| `PanelSection` | `src/components/shared/panel-section.tsx` | Grouped section inside side panels |
| 12 custom `loading.tsx` | `src/app/(dashboard)/*/loading.tsx` | Per-page contextual skeletons |

**Modified components:** ~15 pages (empty state CTAs + progress indicators), `user-detail-drawer.tsx`, `incident-form.tsx`

---

## Out of Scope

- No backend changes
- No new API endpoints or status fields
- No navigation/breadcrumb changes (user didn't prioritize)
- No mobile-specific changes
