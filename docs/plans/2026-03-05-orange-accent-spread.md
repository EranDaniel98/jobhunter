# Orange Accent Spread — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Spread orange accent color across the UI so it appears on more interactive/semantic elements beyond just primary buttons. The app should feel "orange-branded" at a glance.

**Architecture:** Pure CSS/Tailwind class changes across ~8 files. Two CSS-variable-level changes in globals.css (`@layer base`), plus targeted className edits in components. No logic changes, no new components.

**Tech Stack:** Tailwind CSS 4, Next.js 16, shadcn/ui (radix-ui), lucide-react icons

---

### Task 1: Active sidebar link — orange left border + stronger tint

**Files:**
- Modify: `frontend/src/components/layout/sidebar.tsx:82-84`

The active nav item currently uses `bg-primary/10 text-primary`. Add a 3px orange left border and bump the background to `/15` for more visual weight.

**Step 1: Edit the active link classes**

In `sidebar.tsx`, find the `isActive &&` class string on line 84:

```tsx
// OLD
isActive && "bg-primary/10 text-primary font-semibold"

// NEW
isActive && "bg-primary/15 text-primary font-semibold border-l-[3px] border-primary pl-2.5"
```

The `pl-2.5` compensates for the border so text doesn't shift. The resting state already has `rounded-xl` which clips the left border nicely — that's fine, it creates a subtle inset bar effect.

**Step 2: Verify visually**

Open `localhost:3000/dashboard`. The active "Dashboard" link in the sidebar should have an orange left bar and a slightly stronger orange tint background.

**Step 3: Commit**

```bash
git add frontend/src/components/layout/sidebar.tsx
git commit -m "style: add orange left-border to active sidebar nav item"
```

---

### Task 2: Active mobile nav link — match sidebar

**Files:**
- Modify: `frontend/src/components/layout/mobile-nav.tsx:76`

Apply the same active style as sidebar.

**Step 1: Edit the active link classes**

In `mobile-nav.tsx`, find the `isActive &&` class string on line 76:

```tsx
// OLD
isActive && "bg-primary/10 text-primary font-semibold"

// NEW
isActive && "bg-primary/15 text-primary font-semibold border-l-[3px] border-primary pl-2.5"
```

**Step 2: Commit**

```bash
git add frontend/src/components/layout/mobile-nav.tsx
git commit -m "style: match mobile nav active state to sidebar orange border"
```

---

### Task 3: Tabs — orange active underline

**Files:**
- Modify: `frontend/src/components/ui/tabs.tsx:70`

The tab underline uses `after:bg-foreground` (dark gray). Change it to orange for the "line" variant active state.

**Step 1: Edit the after pseudo-element color**

In `tabs.tsx` line 70, find:
```
after:bg-foreground
```

Replace with:
```
after:bg-primary
```

This makes the underline indicator orange on active tabs (companies, approvals, interview-prep, admin pages all use tabs).

**Step 2: Verify visually**

Open `localhost:3000/companies`. The active tab filter should have an orange underline instead of dark gray.

**Step 3: Commit**

```bash
git add frontend/src/components/ui/tabs.tsx
git commit -m "style: orange underline on active tab triggers"
```

---

### Task 4: Card hover — subtle orange top-border glow

**Files:**
- Modify: `frontend/src/components/ui/card.tsx:10`

Add a hover state to cards: on hover, show a faint orange top border and slight shadow lift.

**Step 1: Edit the Card base classes**

In `card.tsx` line 10, find:
```
"bg-card text-card-foreground flex flex-col gap-6 rounded-2xl border py-6 shadow-sm transition-shadow duration-200",
```

Replace with:
```
"bg-card text-card-foreground flex flex-col gap-6 rounded-2xl border py-6 shadow-sm transition-all duration-200 hover:shadow-md hover:border-primary/20",
```

This adds a subtle orange border tint + shadow lift on every card hover. The `transition-all` covers both shadow and border-color.

**Step 2: Verify visually**

Hover over any card on the dashboard. It should gain a faint orange border and slightly elevated shadow.

**Step 3: Commit**

```bash
git add frontend/src/components/ui/card.tsx
git commit -m "style: orange border tint + shadow lift on card hover"
```

---

### Task 5: Global link color — orange text links via CSS layer

**Files:**
- Modify: `frontend/src/app/globals.css:127-134`

Add a base style for `<a>` tags inside the app to use orange text, so all inline links (not wrapped in Button/Badge) get orange automatically.

**Step 1: Add anchor styles to `@layer base`**

In `globals.css`, find the `@layer base` block and add anchor styles:

```css
@layer base {
  * {
    @apply border-border outline-ring/50;
  }
  body {
    @apply bg-background text-foreground;
  }
  a:not([data-slot]) {
    @apply text-primary hover:text-primary/80 transition-colors;
  }
}
```

The `:not([data-slot])` selector excludes shadcn/ui components (buttons, badges, etc.) which all use `data-slot` attributes. This means only raw `<a>` and Next.js `<Link>` tags without shadcn wrappers get the orange treatment.

**Step 2: Verify visually**

Check `localhost:3000/dashboard` — the "Upgrade" link in UsageCard and the "View all" links should now be orange. Buttons should NOT change color (they have `data-slot="button"`).

**Important caveat:** If this over-applies (e.g., table row links that shouldn't be orange), the selector can be narrowed to `a:not([data-slot]):not([class*="flex"])` or removed in favor of per-component changes. Check visually before committing.

**Step 3: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "style: global orange link color for non-component anchor tags"
```

---

### Task 6: Stat card icons — all use orange (dashboard consistency)

**Files:**
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx:119-121,145-147,164-166,185-187`

Currently the 4 stat cards use different chart colors for their icons (chart-2, chart-3, chart-5). Unify them all to orange for brand consistency.

**Step 1: Replace chart-color icon backgrounds with primary**

Find and replace these 3 stat card icon containers (the Companies card at line 119 already uses primary):

```tsx
// Emails Sent card (line 145-146) — change chart-2 to primary
// OLD
<div className="flex h-9 w-9 items-center justify-center rounded-xl bg-chart-2/15">
  <Mail className="h-4 w-4 text-chart-2" />

// NEW
<div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
  <Mail className="h-4 w-4 text-primary" />


// Open Rate card (line 164-165) — change chart-3 to primary
// OLD
<div className="flex h-9 w-9 items-center justify-center rounded-xl bg-chart-3/15">
  <Eye className="h-4 w-4 text-chart-3" />

// NEW
<div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
  <Eye className="h-4 w-4 text-primary" />


// Reply Rate card (line 185-186) — change chart-5 to primary
// OLD
<div className="flex h-9 w-9 items-center justify-center rounded-xl bg-chart-5/15">
  <MessageSquare className="h-4 w-4 text-chart-5" />

// NEW
<div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
  <MessageSquare className="h-4 w-4 text-primary" />
```

**Step 2: Verify visually**

All 4 stat cards on the dashboard should now have matching orange icons.

**Step 3: Commit**

```bash
git add frontend/src/app/\(dashboard\)/dashboard/page.tsx
git commit -m "style: unify dashboard stat card icons to orange"
```

---

### Task 7: Page header title accent — orange first word or icon dot

**Files:**
- Modify: `frontend/src/components/shared/page-header.tsx`

Add a small orange dot before page titles for visual branding. This is lightweight and consistent.

**Step 1: Add orange dot before title**

```tsx
// OLD
<h1 className="text-2xl font-bold tracking-tight">{title}</h1>

// NEW
<h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
  <span className="h-2 w-2 rounded-full bg-primary shrink-0" />
  {title}
</h1>
```

**Step 2: Verify visually**

Every page (Dashboard, Companies, Analytics, etc.) should show a small orange dot before the title.

**Step 3: Commit**

```bash
git add frontend/src/components/shared/page-header.tsx
git commit -m "style: add orange dot accent to page header titles"
```

---

### Task 8: Footer status dot — use orange instead of chart-2

**Files:**
- Modify: `frontend/src/components/layout/footer.tsx:7-8`

The "All systems operational" status dot uses `bg-chart-2` (steel blue). Change to orange for brand consistency.

**Step 1: Replace chart-2 with primary**

```tsx
// OLD
<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-chart-2/60 opacity-75" />
<span className="relative inline-flex h-2 w-2 rounded-full bg-chart-2" />

// NEW
<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/60 opacity-75" />
<span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
```

**Step 2: Commit**

```bash
git add frontend/src/components/layout/footer.tsx
git commit -m "style: orange status dot in footer"
```

---

### Task 9: Final verification

**Step 1: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: zero errors (all changes are className strings only).

**Step 2: Visual verification checklist**

Open each page and verify orange appears in these spots:
- [ ] Sidebar: active link has orange left border
- [ ] Mobile nav: same as sidebar (resize to mobile)
- [ ] Tabs: orange underline on active tab (companies, approvals pages)
- [ ] Cards: faint orange border on hover (all cards)
- [ ] Links: raw text links are orange (upgrade link, view-all links)
- [ ] Dashboard stat icons: all 4 icons are orange
- [ ] Page headers: orange dot before every title
- [ ] Footer: orange pulsing status dot
- [ ] Dark mode: all above should work in dark mode too (toggle and check)

**Step 3: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "style: spread orange accent across sidebar, tabs, cards, links, icons, and headers"
```

---

## Summary of files modified

| # | File | Change |
|---|------|--------|
| 1 | `components/layout/sidebar.tsx` | Orange left border on active nav |
| 2 | `components/layout/mobile-nav.tsx` | Match sidebar active style |
| 3 | `components/ui/tabs.tsx` | Orange active tab underline |
| 4 | `components/ui/card.tsx` | Orange border + shadow on hover |
| 5 | `app/globals.css` | Global orange link color in `@layer base` |
| 6 | `app/(dashboard)/dashboard/page.tsx` | Unify stat card icons to orange |
| 7 | `components/shared/page-header.tsx` | Orange dot before page titles |
| 8 | `components/layout/footer.tsx` | Orange status dot |

**No logic changes. No new dependencies. All CSS/className only.**
