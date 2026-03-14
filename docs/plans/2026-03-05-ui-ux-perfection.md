# UI/UX Perfection Plan - From 7/10 to 10/10

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix every issue identified in the 4-agent UI/UX review - accessibility violations, navigation gaps, page-level UX issues, and polish items - to achieve a 10/10 score.

**Architecture:** Pure frontend changes across ~30 files. Four phases: (1) Critical WCAG fixes, (2) High-impact UX gaps, (3) Medium polish, (4) Nice-to-have premium features. Each phase builds on the last and can be committed independently.

**Tech Stack:** Next.js 16, Tailwind CSS 4, shadcn/ui (radix-ui), React Query, Recharts, Sonner, lucide-react

---

## Phase 1: Critical Accessibility Fixes (WCAG AA)

---

### Task 1: Fix muted-foreground contrast in both modes

**Files:**
- Modify: `frontend/src/app/globals.css`

**Context:** `muted-foreground` is used on ~30+ elements (descriptions, placeholders, secondary labels). Current light mode value `oklch(0.450)` yields ~3.8:1 on background - fails WCAG AA 4.5:1. Dark mode `oklch(0.560)` is also borderline.

**Step 1: Edit light mode muted-foreground**

In `:root`, change:
```css
--muted-foreground:    oklch(0.450 0.004 265);
```
to:
```css
--muted-foreground:    oklch(0.385 0.004 265);
```

**Step 2: Edit dark mode muted-foreground**

In `.dark`, change:
```css
--muted-foreground:    oklch(0.560 0.004 265);
```
to:
```css
--muted-foreground:    oklch(0.620 0.004 265);
```

**Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit`
Visual: Check that secondary text (descriptions, placeholders) is readable but still clearly secondary.

**Step 4: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "fix(a11y): bump muted-foreground contrast to pass WCAG AA 4.5:1"
```

---

### Task 2: Fix password toggle accessibility

**Files:**
- Modify: `frontend/src/components/auth/register-form.tsx:151-158,211-218`

**Context:** Password visibility toggle buttons have `tabIndex={-1}` (removing from tab order) and no `aria-label`. Keyboard-only users cannot toggle, screen readers announce empty buttons. WCAG 2.1.1 violation.

**Step 1: Fix first password toggle (line 151-158)**

Replace:
```tsx
<button
  type="button"
  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
  onClick={() => setShowPassword(!showPassword)}
  tabIndex={-1}
>
  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
</button>
```
with:
```tsx
<button
  type="button"
  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
  onClick={() => setShowPassword(!showPassword)}
  aria-label={showPassword ? "Hide password" : "Show password"}
>
  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
</button>
```

**Step 2: Fix second password toggle (line 211-218)**

Same change for confirm password toggle - remove `tabIndex={-1}`, add `aria-label={showConfirmPassword ? "Hide password" : "Show password"}`.

**Step 3: Link form errors to inputs via aria-describedby**

For each field with an error message, add `id` to the error `<p>` and `aria-describedby` + `aria-invalid` to the `<Input>`:

Name field (lines 111-119):
```tsx
<Input
  id="name"
  placeholder="John Doe"
  value={fullName}
  onChange={(e) => setFullName(stripHtml(e.target.value))}
  onBlur={() => markTouched("fullName")}
  required
  aria-invalid={!!nameError}
  aria-describedby={nameError ? "name-error" : undefined}
/>
{nameError && <p id="name-error" className="text-sm text-destructive">{nameError}</p>}
```

Email field (lines 125-134):
```tsx
<Input
  id="email"
  type="email"
  placeholder="you@example.com"
  value={email}
  onChange={(e) => setEmail(e.target.value)}
  onBlur={() => markTouched("email")}
  required
  aria-invalid={!!emailError}
  aria-describedby={emailError ? "email-error" : undefined}
/>
{emailError && <p id="email-error" className="text-sm text-destructive">{emailError}</p>}
```

Confirm password field (lines 201-220):
```tsx
<Input
  id="confirmPassword"
  type={showConfirmPassword ? "text" : "password"}
  placeholder="••••••••"
  value={confirmPassword}
  onChange={(e) => setConfirmPassword(e.target.value)}
  onBlur={() => markTouched("confirmPassword")}
  required
  className="pr-10"
  aria-invalid={!!confirmError}
  aria-describedby={confirmError ? "confirm-error" : undefined}
/>
```
And the error `<p>`:
```tsx
{confirmError && <p id="confirm-error" className="text-sm text-destructive">{confirmError}</p>}
```

**Step 4: Commit**

```bash
git add frontend/src/components/auth/register-form.tsx
git commit -m "fix(a11y): password toggles keyboard-accessible, link errors to inputs via aria"
```

---

### Task 3: Add skip-to-content link

**Files:**
- Modify: `frontend/src/app/(dashboard)/layout.tsx`

**Context:** Keyboard users must tab through 9+ sidebar items to reach content. WCAG 2.4.1 violation. Add a visually-hidden skip link that appears on focus.

**Step 1: Add skip link and main landmark**

In `layout.tsx`, add the skip link as the first child of the outer div, and wrap `<main>` with an id:

```tsx
return (
  <div className="min-h-screen bg-background">
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground focus:shadow-lg"
    >
      Skip to main content
    </a>
    <Sidebar lastEvent={lastEvent} />
    <MobileNav open={mobileNavOpen} onOpenChange={setMobileNavOpen} lastEvent={lastEvent} />
    <CommandMenu />
    <div className="lg:pl-64">
      <Header onMenuClick={() => setMobileNavOpen(true)} lastEvent={lastEvent} />
      <main id="main-content" className="p-4 md:p-6 lg:p-8">{children}</main>
      <Footer />
    </div>
  </div>
);
```

**Step 2: Commit**

```bash
git add frontend/src/app/\(dashboard\)/layout.tsx
git commit -m "fix(a11y): add skip-to-content link and main landmark"
```

---

### Task 4: Fix upload zone keyboard accessibility

**Files:**
- Modify: `frontend/src/components/resume/upload-zone.tsx:99-104`

**Context:** Hidden file input with `className="hidden"` is not keyboard-accessible. Use `sr-only` instead so it remains focusable.

**Step 1: Replace hidden with sr-only and add aria-live**

Replace:
```tsx
<input
  type="file"
  accept=".pdf,.docx"
  className="hidden"
  onChange={handleInput}
/>
```
with:
```tsx
<input
  type="file"
  accept=".pdf,.docx"
  className="sr-only"
  onChange={handleInput}
  aria-label="Upload resume file"
/>
```

Also wrap the status text area in an `aria-live` region. Find the `<label>` content and add to the label element:
```tsx
aria-live="polite"
```

**Step 2: Commit**

```bash
git add frontend/src/components/resume/upload-zone.tsx
git commit -m "fix(a11y): make upload zone keyboard-accessible, add aria-live"
```

---

### Task 5: Fix semantic HTML - nav list structure

**Files:**
- Modify: `frontend/src/components/layout/sidebar.tsx:74-97`
- Modify: `frontend/src/components/layout/mobile-nav.tsx:66-89`

**Context:** Nav items are not in a `<ul>/<li>` structure. Screen readers can't announce item count. Also the `<aside>` has redundant `role="navigation"` (the inner `<nav>` already provides it).

**Step 1: Fix sidebar**

In `sidebar.tsx` line 66, remove `role="navigation"` from the `<aside>`:
```tsx
<aside className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground" aria-label="Main navigation">
```

Wrap nav items in `<ul>` and each item in `<li>`. Change line 74-97:
```tsx
<nav className="flex-1 px-3 py-4">
  <ul className="space-y-0.5">
    {[...navItems, ...(user?.is_admin ? [adminNavItem] : [])].map((item) => {
      const Icon = item.icon;
      const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
      return (
        <li key={item.href}>
          <Link href={item.href}>
            <Button
              variant="ghost"
              className={cn(
                "w-full justify-start gap-3 rounded-xl text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-all",
                isActive && "bg-primary/15 text-primary font-semibold border-l-[3px] border-primary pl-2.5"
              )}
            >
              <Icon className={cn("h-4 w-4", isActive && "text-primary")} />
              {item.label}
              {"badge" in item && item.badge && approvalCount?.count ? (
                <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground" aria-label={`${approvalCount.count} pending`}>
                  {approvalCount.count > 99 ? "99+" : approvalCount.count}
                </span>
              ) : null}
            </Button>
          </Link>
        </li>
      );
    })}
  </ul>
</nav>
```

**Step 2: Apply same `<ul>/<li>` structure to mobile-nav.tsx**

Same pattern - wrap nav items in `<ul>/<li>` inside the `<nav>`.

**Step 3: Commit**

```bash
git add frontend/src/components/layout/sidebar.tsx frontend/src/components/layout/mobile-nav.tsx
git commit -m "fix(a11y): semantic nav list structure, remove redundant role, add badge aria-label"
```

---

### Task 6: Add aria attributes to loading skeletons and empty state

**Files:**
- Modify: `frontend/src/components/shared/loading-skeleton.tsx`
- Modify: `frontend/src/components/shared/empty-state.tsx`

**Step 1: Add role and aria-label to PageSkeleton**

```tsx
export function PageSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading page content">
      ...
    </div>
  );
}
```

Also add `role="status"` to `CardSkeleton` and `TableSkeleton`.

**Step 2: Make EmptyState heading level configurable**

```tsx
interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  headingLevel?: "h2" | "h3" | "h4";
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  headingLevel: Heading = "h3",
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 md:py-16 text-center">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/10">
        <Icon className="h-10 w-10 text-primary/60" aria-hidden="true" />
      </div>
      <Heading className="mb-1 text-xl font-bold">{title}</Heading>
      <p className="mb-4 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action && (
        <Button onClick={action.onClick}>{action.label}</Button>
      )}
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/shared/loading-skeleton.tsx frontend/src/components/shared/empty-state.tsx
git commit -m "fix(a11y): add ARIA roles to skeletons, configurable heading level on empty state"
```

---

## Phase 2: High-Impact UX Gaps

---

### Task 7: Extract shared nav config and add section groupings

**Files:**
- Create: `frontend/src/lib/nav-config.ts`
- Modify: `frontend/src/components/layout/sidebar.tsx`
- Modify: `frontend/src/components/layout/mobile-nav.tsx`
- Modify: `frontend/src/components/layout/command-menu.tsx`

**Step 1: Create nav config**

```ts
import {
  LayoutDashboard, FileText, Building2, Mail, GraduationCap,
  FileCheck, ClipboardCheck, BarChart3, Settings, Shield,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: boolean;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    label: "Core",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/resume", label: "Resume & DNA", icon: FileText },
      { href: "/companies", label: "Companies", icon: Building2 },
    ],
  },
  {
    label: "Outreach",
    items: [
      { href: "/outreach", label: "Outreach", icon: Mail },
      { href: "/interview-prep", label: "Interview Prep", icon: GraduationCap },
      { href: "/apply", label: "Apply", icon: FileCheck },
      { href: "/approvals", label: "Approvals", icon: ClipboardCheck, badge: true },
    ],
  },
  {
    label: "Insights",
    items: [
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export const adminNavItem: NavItem = { href: "/admin", label: "Admin", icon: Shield };

// Flat list for command menu
export const allNavItems: NavItem[] = navSections.flatMap((s) => s.items);
```

**Step 2: Update sidebar to use sections with headers**

Replace the flat nav items loop with section-grouped rendering:
```tsx
import { navSections, adminNavItem } from "@/lib/nav-config";

// Inside <nav>:
<nav className="flex-1 overflow-y-auto px-3 py-4">
  {navSections.map((section) => (
    <div key={section.label} className="mb-4">
      <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/40">
        {section.label}
      </p>
      <ul className="space-y-0.5">
        {section.items.map((item) => {
          // ... existing item rendering with <li> wrapper
        })}
      </ul>
    </div>
  ))}
  {user?.is_admin && (
    <div className="mb-4">
      <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/40">Admin</p>
      <ul className="space-y-0.5">
        <li>/* render adminNavItem */</li>
      </ul>
    </div>
  )}
</nav>
```

**Step 3: Update mobile-nav to use same nav config and section structure**

**Step 4: Update command-menu to use `allNavItems` instead of hardcoded `pages` array**

This also fixes the missing Interview Prep and Apply pages in command menu.

**Step 5: Remove duplicate navItems/adminNavItem from sidebar.tsx and mobile-nav.tsx**

**Step 6: Commit**

```bash
git add frontend/src/lib/nav-config.ts frontend/src/components/layout/sidebar.tsx frontend/src/components/layout/mobile-nav.tsx frontend/src/components/layout/command-menu.tsx
git commit -m "refactor: extract shared nav config with section groupings, sync command menu"
```

---

### Task 8: Add page title to mobile header + search button

**Files:**
- Modify: `frontend/src/components/layout/header.tsx`
- Modify: `frontend/src/app/(dashboard)/layout.tsx`
- Modify: `frontend/src/components/layout/command-menu.tsx`

**Step 1: Make command menu externally triggerable**

Add a `useCommandMenu` context or expose a ref. Simplest approach - add a global custom event:

In `command-menu.tsx`, add a listener:
```tsx
useEffect(() => {
  function onOpen() { setOpen(true); }
  window.addEventListener("open-command-menu", onOpen);
  return () => window.removeEventListener("open-command-menu", onOpen);
}, []);
```

**Step 2: Add page title and search button to header**

```tsx
"use client";

import { usePathname } from "next/navigation";
import { Menu, Briefcase, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { NotificationCenter } from "@/components/layout/notification-center";
import { allNavItems } from "@/lib/nav-config";

interface HeaderProps {
  onMenuClick: () => void;
  lastEvent?: { type: string; data: Record<string, unknown> } | null;
}

export function Header({ onMenuClick, lastEvent = null }: HeaderProps) {
  const pathname = usePathname();
  const currentPage = allNavItems.find(
    (item) => pathname === item.href || pathname.startsWith(item.href + "/")
  );

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-sidebar-border bg-sidebar px-4 lg:hidden">
      <Button variant="ghost" size="icon" onClick={onMenuClick} aria-label="Open navigation menu">
        <Menu className="h-5 w-5" />
      </Button>
      <div className="flex flex-1 items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary/70 shadow-sm shadow-primary/20">
          <Briefcase className="h-3.5 w-3.5 text-sidebar-primary-foreground" />
        </div>
        <span className="text-sm font-semibold truncate">
          {currentPage?.label || "JobHunter AI"}
        </span>
      </div>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => window.dispatchEvent(new Event("open-command-menu"))}
        aria-label="Search"
      >
        <Search className="h-4 w-4" />
      </Button>
      <NotificationCenter lastEvent={lastEvent} />
      <ThemeToggle />
    </header>
  );
}
```

**Step 3: Remove duplicate NotificationCenter from mobile-nav bottom area**

In `mobile-nav.tsx`, remove the `<NotificationCenter>` from the bottom section (keep only the header one).

**Step 4: Commit**

```bash
git add frontend/src/components/layout/header.tsx frontend/src/components/layout/command-menu.tsx frontend/src/components/layout/mobile-nav.tsx
git commit -m "feat: page title + search button in mobile header, deduplicate notification center"
```

---

### Task 9: Add Cmd+K hint to sidebar

**Files:**
- Modify: `frontend/src/components/layout/sidebar.tsx`

**Step 1: Add search trigger below logo**

After the logo div (line 72), add:
```tsx
<button
  onClick={() => window.dispatchEvent(new Event("open-command-menu"))}
  className="mx-3 mt-2 flex items-center gap-2 rounded-xl border border-sidebar-border bg-sidebar-accent/50 px-3 py-1.5 text-xs text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
>
  <Search className="h-3.5 w-3.5" />
  <span className="flex-1 text-left">Search...</span>
  <kbd className="rounded border border-sidebar-border bg-sidebar px-1.5 py-0.5 text-[10px] font-mono">
    {typeof navigator !== "undefined" && /Mac/.test(navigator.userAgent) ? "\u2318" : "Ctrl"}+K
  </kbd>
</button>
```

Import `Search` from lucide-react (already imported in the file for other uses - check and add if missing).

**Step 2: Commit**

```bash
git add frontend/src/components/layout/sidebar.tsx
git commit -m "feat: add Cmd+K search trigger in sidebar header"
```

---

### Task 10: Make notification items actionable with links

**Files:**
- Modify: `frontend/src/components/layout/notification-center.tsx`

**Step 1: Add route mapping to eventToMessage**

Extend the `Notification` interface to include an optional `href`:
```tsx
interface Notification {
  id: string;
  type: string;
  message: string;
  timestamp: Date;
  read: boolean;
  href?: string;
}
```

Update the reducer's `add` case to include a href:
```tsx
case "add": {
  const n: Notification = {
    id: `${Date.now()}-${Math.random()}`,
    type: action.event.type,
    message: eventToMessage(action.event.type, action.event.data),
    timestamp: new Date(),
    read: false,
    href: eventToHref(action.event.type, action.event.data),
  };
  return [n, ...state].slice(0, 50);
}
```

Add the href resolver:
```tsx
function eventToHref(type: string, data: Record<string, unknown>): string | undefined {
  const companyId = (data as { company_id?: string }).company_id;
  switch (type) {
    case "research_completed": return companyId ? `/companies/${companyId}` : "/companies";
    case "followup_drafted": return "/approvals";
    case "email_opened":
    case "email_clicked":
    case "email_delivered":
    case "email_sent": return "/outreach";
    case "resume_parsed": return "/resume";
    default: return undefined;
  }
}
```

**Step 2: Make notification items clickable**

Replace the plain `<div>` with a button/link:
```tsx
{notifications.map((n) => {
  const content = (
    <>
      <p className="text-sm">{n.message}</p>
      <p className="text-xs text-muted-foreground mt-1">
        {n.timestamp.toLocaleTimeString()}
      </p>
    </>
  );
  return n.href ? (
    <Link
      key={n.id}
      href={n.href}
      onClick={() => setOpen(false)}
      className="block px-4 py-3 hover:bg-accent transition-colors"
    >
      {content}
    </Link>
  ) : (
    <div key={n.id} className="px-4 py-3">
      {content}
    </div>
  );
})}
```

Import `Link` from `next/link`.

**Step 3: Commit**

```bash
git add frontend/src/components/layout/notification-center.tsx
git commit -m "feat: make notifications actionable with route links per event type"
```

---

### Task 11: Fix footer - remove fake status, add useful links

**Files:**
- Modify: `frontend/src/components/layout/footer.tsx`

**Step 1: Replace the static footer**

```tsx
import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t px-4 py-3 flex items-center justify-between text-xs text-muted-foreground">
      <span>JobHunter AI v{process.env.NEXT_PUBLIC_APP_VERSION || "0.2.0"}</span>
      <div className="flex items-center gap-4">
        <Link href="/settings" className="hover:text-foreground transition-colors">Settings</Link>
        <button
          onClick={() => window.dispatchEvent(new Event("open-command-menu"))}
          className="hover:text-foreground transition-colors"
        >
          <kbd className="font-mono">{typeof navigator !== "undefined" && /Mac/.test(navigator.userAgent) ? "\u2318" : "Ctrl"}+K</kbd> Search
        </button>
      </div>
    </footer>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/layout/footer.tsx
git commit -m "fix: replace fake status footer with useful links and keyboard shortcut hint"
```

---

### Task 12: Add semantic success/warning color tokens

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/lib/constants.ts`

**Step 1: Add success and warning tokens to :root**

After `--destructive-foreground` in `:root`, add:
```css
  --success:             oklch(0.550 0.140 155);
  --success-foreground:  oklch(0.985 0.003 0);
  --warning:             oklch(0.680 0.130 80);
  --warning-foreground:  oklch(0.155 0.004 265);
```

In `.dark`, after `--destructive-foreground`, add:
```css
  --success:             oklch(0.600 0.140 155);
  --success-foreground:  oklch(0.120 0.005 265);
  --warning:             oklch(0.720 0.130 80);
  --warning-foreground:  oklch(0.120 0.005 265);
```

**Step 2: Update status color mappings in constants.ts**

```ts
export const COMPANY_STATUS_COLORS: Record<string, string> = {
  suggested: "bg-secondary text-secondary-foreground",
  approved: "bg-[oklch(var(--success)/0.15)] text-[oklch(var(--success))]",
  rejected: "bg-destructive/15 text-destructive",
};
```

Actually, since Tailwind v4 doesn't have built-in support for custom `--success` unless registered, use the simpler approach - use the chart-3 color (which is green-ish hue 155) as a stand-in for success:

```ts
export const COMPANY_STATUS_COLORS: Record<string, string> = {
  suggested: "bg-secondary text-secondary-foreground",
  approved: "bg-chart-3/15 text-chart-3",
  rejected: "bg-destructive/15 text-destructive",
};

export const RESEARCH_STATUS_COLORS: Record<string, string> = {
  pending: "bg-muted text-muted-foreground",
  in_progress: "bg-primary/15 text-primary",
  completed: "bg-chart-3/15 text-chart-3",
  failed: "bg-destructive/15 text-destructive",
};

export const MESSAGE_STATUS_COLORS: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  sent: "bg-secondary text-secondary-foreground",
  delivered: "bg-chart-2/15 text-chart-2",
  opened: "bg-primary/15 text-primary",
  replied: "bg-chart-3/15 text-chart-3",
  bounced: "bg-destructive/15 text-destructive",
  failed: "bg-destructive/15 text-destructive",
};
```

This gives each status a distinct semantic color: gray (neutral), blue (delivered), orange (active), green (success), red (failure).

**Step 3: Commit**

```bash
git add frontend/src/app/globals.css frontend/src/lib/constants.ts
git commit -m "feat: add success/warning color tokens, use semantic colors in status badges"
```

---

## Phase 3: Medium Polish

---

### Task 13: Unify dark mode hue with light mode

**Files:**
- Modify: `frontend/src/app/globals.css`

**Context:** Light mode uses warm hue 70, dark mode uses cool hue 265. This makes mode switching feel like a personality change. Shift dark mode to warm hue 70 at very low chroma for consistency.

**Step 1: Update all dark mode surface hues from 265 to 70**

In `.dark`, change every surface/border/sidebar variable from hue `265` to `70`. Keep text foregrounds at `265` (cool text on warm surfaces works well in dark mode too). Example changes:

```css
.dark {
  --background:          oklch(0.145 0.005 70);
  --foreground:          oklch(0.930 0.004 265);
  --card:                oklch(0.190 0.005 70);
  --card-foreground:     oklch(0.930 0.004 265);
  --popover:             oklch(0.190 0.005 70);
  --popover-foreground:  oklch(0.930 0.004 265);
  /* primary stays same */
  --primary-foreground:  oklch(0.120 0.005 70);
  --secondary:           oklch(0.225 0.005 70);
  --secondary-foreground: oklch(0.780 0.004 265);
  --muted:               oklch(0.225 0.004 70);
  --muted-foreground:    oklch(0.620 0.004 265);
  --accent:              oklch(0.225 0.005 70);
  --accent-foreground:   oklch(0.930 0.004 265);
  /* destructive stays same */
  --border:              oklch(0.280 0.005 70);
  --input:               oklch(0.290 0.005 70);
  /* ring stays same */
  /* charts stay same */
  --sidebar:             oklch(0.115 0.005 70);
  --sidebar-foreground:  oklch(0.850 0.004 265);
  /* sidebar-primary stays same */
  --sidebar-primary-foreground: oklch(0.120 0.005 70);
  --sidebar-accent:      oklch(0.195 0.005 70);
  --sidebar-accent-foreground: oklch(0.880 0.004 265);
  --sidebar-border:      oklch(0.240 0.005 70);
  /* sidebar-ring stays same */
}
```

**Step 2: Verify**

Toggle dark mode - surfaces should feel like "warm charcoal" instead of "cool slate". The warmth should match light mode's personality.

**Step 3: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "style: unify dark mode hue with light mode (warm 70) for consistent brand personality"
```

---

### Task 14: Add prefers-reduced-motion support

**Files:**
- Modify: `frontend/src/app/globals.css`

**Step 1: Add reduced motion global rules at the end of globals.css**

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

This is the nuclear option - respects the user's OS preference completely. All animations, transitions, and auto-scroll stop. This is standard practice (GitHub uses this exact approach).

**Step 2: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "fix(a11y): respect prefers-reduced-motion for all animations"
```

---

### Task 15: Improve table density and CardTitle typography

**Files:**
- Modify: `frontend/src/components/ui/table.tsx:60,86`
- Modify: `frontend/src/components/ui/card.tsx:35`

**Step 1: Increase table cell padding**

In `TableRow` (line 60), no change needed (hover is already orange from earlier).

In `TableCell` (line 86), change:
```
"p-2 align-middle whitespace-nowrap
```
to:
```
"px-3 py-2.5 align-middle whitespace-nowrap
```

In `TableHead` (line 73), change:
```
"text-muted-foreground h-10 px-2 text-left
```
to:
```
"text-muted-foreground h-10 px-3 text-left
```

**Step 2: Fix CardTitle typography**

In `CardTitle` (line 35), change:
```
className={cn("leading-none font-semibold", className)}
```
to:
```
className={cn("text-base leading-tight font-semibold", className)}
```

**Step 3: Commit**

```bash
git add frontend/src/components/ui/table.tsx frontend/src/components/ui/card.tsx
git commit -m "style: improve table cell spacing and card title typography"
```

---

### Task 16: Add shimmer animation to skeletons

**Files:**
- Modify: `frontend/src/components/ui/skeleton.tsx`
- Modify: `frontend/src/app/globals.css`

**Step 1: Add shimmer keyframes to globals.css**

Before the `@media (prefers-reduced-motion)` rule, add:
```css
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
```

**Step 2: Update skeleton component**

```tsx
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "rounded-md bg-gradient-to-r from-primary/[0.06] via-primary/[0.12] to-primary/[0.06] bg-[length:200%_100%] animate-[shimmer_1.5s_ease-in-out_infinite]",
        className
      )}
      {...props}
    />
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/app/globals.css frontend/src/components/ui/skeleton.tsx
git commit -m "style: replace pulse skeleton with orange-tinted shimmer animation"
```

---

### Task 17: Interview prep - extract content renderers to separate files

**Files:**
- Create: `frontend/src/components/interview/company-qa-content.tsx`
- Create: `frontend/src/components/interview/behavioral-content.tsx`
- Create: `frontend/src/components/interview/technical-content.tsx`
- Create: `frontend/src/components/interview/culture-fit-content.tsx`
- Create: `frontend/src/components/interview/salary-content.tsx`
- Create: `frontend/src/components/interview/mock-interview.tsx`
- Create: `frontend/src/components/interview/generic-content.tsx`
- Modify: `frontend/src/app/(dashboard)/interview-prep/page.tsx`

**Step 1: Extract each content renderer**

Move the `CompanyQAContent`, `BehavioralContent`, `TechnicalContent`, `CultureFitContent`, `SalaryNegotiationContent`, `GenericContent`, and the mock interview chat section into individual component files under `frontend/src/components/interview/`.

Each file should export a single component. Import types from `@/lib/types`.

**Step 2: Fix GenericContent to handle non-string values gracefully**

Instead of `JSON.stringify`, render key-value pairs as a definition list:
```tsx
export function GenericContent({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="space-y-3">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt className="text-sm font-medium capitalize">{key.replace(/_/g, " ")}</dt>
          <dd className="text-sm text-muted-foreground mt-0.5">
            {typeof value === "string" ? value : Array.isArray(value) ? value.join(", ") : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
```

**Step 3: Update interview-prep page to import from new files**

**Step 4: Commit**

```bash
git add frontend/src/components/interview/ frontend/src/app/\(dashboard\)/interview-prep/page.tsx
git commit -m "refactor: extract interview prep content renderers, fix GenericContent JSON leak"
```

---

### Task 18: Apply page - add polling for in-progress analysis

**Files:**
- Modify: `frontend/src/app/(dashboard)/apply/page.tsx`

**Step 1: Add refetchInterval to the analysis query when status is in-progress**

Find the analysis query (or the individual posting detail query) and add:
```tsx
refetchInterval: selectedPosting?.analysis_status === "in_progress" ? 3000 : false,
```

This polls every 3 seconds while analysis is running, then stops.

**Step 2: Commit**

```bash
git add frontend/src/app/\(dashboard\)/apply/page.tsx
git commit -m "feat: poll for analysis completion on Apply page"
```

---

### Task 19: Company detail - add "not found" empty state and retry research button

**Files:**
- Modify: `frontend/src/app/(dashboard)/companies/[id]/page.tsx`

**Step 1: Replace bare "Company not found" `<p>` with EmptyState**

```tsx
if (!company) {
  return (
    <EmptyState
      icon={Building2}
      title="Company not found"
      description="This company may have been removed or the link is incorrect."
      action={{ label: "Back to Companies", onClick: () => router.push("/companies") }}
    />
  );
}
```

**Step 2: Add "Retry Research" button when research_status is "failed"**

In the company header area, after the status badges, add:
```tsx
{company.research_status === "failed" && (
  <Button
    variant="outline"
    size="sm"
    onClick={() => approveMutation.mutate(company.id)}
    disabled={approveMutation.isPending}
  >
    {approveMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
    Retry Research
  </Button>
)}
```

**Step 3: Commit**

```bash
git add frontend/src/app/\(dashboard\)/companies/\[id\]/page.tsx
git commit -m "feat: proper 404 empty state + retry research button on company detail"
```

---

### Task 20: Dashboard - add UsageCard, empty state for recent companies, responsive stat grid

**Files:**
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx`

**Step 1: Import and render UsageCard**

Add `import { UsageCard } from "@/components/dashboard/usage-card";` and render it after the stats grid:
```tsx
<div className="grid gap-4 lg:grid-cols-3">
  <div className="lg:col-span-2">
    {/* Pipeline Overview card (existing) */}
  </div>
  <UsageCard />
</div>
```

**Step 2: Add empty state for recent companies**

After the `recentCompanies.length > 0` block, add an else:
```tsx
{recentCompanies.length === 0 && !companiesQuery.isLoading && (
  <Card>
    <CardContent className="py-8 text-center">
      <p className="text-sm text-muted-foreground">No companies in your pipeline yet.</p>
      <Button variant="outline" className="mt-3" onClick={() => router.push("/companies")}>
        <Search className="mr-2 h-4 w-4" />
        Discover Companies
      </Button>
    </CardContent>
  </Card>
)}
```

**Step 3: Fix responsive stat grid - add `sm:grid-cols-2`**

Change:
```
<div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
```
to:
```
<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
```

**Step 4: Commit**

```bash
git add frontend/src/app/\(dashboard\)/dashboard/page.tsx
git commit -m "feat: add UsageCard to dashboard, empty state for companies, responsive grid"
```

---

## Phase 4: Nice-to-Have Premium Polish

---

### Task 21: Settings - per-section save with sticky save bar

**Files:**
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx`

**Step 1: Track dirty state per section**

Add a `dirty` state that becomes `true` when any profile field changes from initial values. Show a sticky save bar at the bottom:

```tsx
{dirty && (
  <div className="fixed bottom-0 left-0 right-0 z-40 border-t bg-card p-3 shadow-lg lg:left-64">
    <div className="flex items-center justify-end gap-3 max-w-5xl mx-auto">
      <Button variant="ghost" onClick={resetForm}>Discard</Button>
      <Button onClick={handleSave} disabled={loading}>
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Save changes
      </Button>
    </div>
  </div>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/app/\(dashboard\)/settings/page.tsx
git commit -m "feat: sticky save bar for settings page with dirty state tracking"
```

---

### Task 22: Approvals - bulk actions with select all

**Files:**
- Modify: `frontend/src/app/(dashboard)/approvals/page.tsx`

**Step 1: Add selection state**

```tsx
const [selected, setSelected] = useState<Set<string>>(new Set());

function toggleSelect(id: string) {
  setSelected((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
}

function selectAll() {
  const pendingIds = filteredActions.map((a) => a.id);
  setSelected(new Set(pendingIds));
}

function clearSelection() {
  setSelected(new Set());
}
```

**Step 2: Add selection UI - checkbox on each card + bulk action bar**

Add a checkbox to each approval card. When any items are selected, show a floating action bar:

```tsx
{selected.size > 0 && (
  <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 rounded-full bg-card border shadow-lg px-6 py-3 lg:left-[calc(50%+8rem)]">
    <span className="text-sm font-medium">{selected.size} selected</span>
    <Button size="sm" onClick={handleBulkApprove}>
      <Check className="mr-1 h-3.5 w-3.5" /> Approve All
    </Button>
    <Button size="sm" variant="outline" onClick={handleBulkReject}>
      <X className="mr-1 h-3.5 w-3.5" /> Reject All
    </Button>
    <Button size="sm" variant="ghost" onClick={clearSelection}>Cancel</Button>
  </div>
)}
```

**Step 3: Add count badges to filter tabs**

```tsx
<TabsTrigger value="pending">Pending ({pendingCount})</TabsTrigger>
<TabsTrigger value="approved">Approved ({approvedCount})</TabsTrigger>
```

**Step 4: Commit**

```bash
git add frontend/src/app/\(dashboard\)/approvals/page.tsx
git commit -m "feat: bulk approve/reject with selection + count badges on filter tabs"
```

---

### Task 23: Plans page - add feature comparison matrix

**Files:**
- Modify: `frontend/src/app/(dashboard)/plans/page.tsx`

**Step 1: Add feature comparison table below the plan cards**

```tsx
<Card className="mt-6">
  <CardHeader>
    <CardTitle>Feature Comparison</CardTitle>
  </CardHeader>
  <CardContent>
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Feature</TableHead>
          {sortedPlans.map((p) => (
            <TableHead key={p.tier} className="text-center">{p.display_name}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {Object.entries(QUOTA_USER_LABELS).map(([key, label]) => (
          <TableRow key={key}>
            <TableCell className="font-medium">{label}</TableCell>
            {sortedPlans.map((p) => (
              <TableCell key={p.tier} className="text-center font-medium">
                {p.limits[key] ?? "-"}/day
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </CardContent>
</Card>
```

Import `Table, TableBody, TableCell, TableHead, TableHeader, TableRow` from `@/components/ui/table`.

**Step 2: Commit**

```bash
git add frontend/src/app/\(dashboard\)/plans/page.tsx
git commit -m "feat: add feature comparison table to plans page"
```

---

### Task 24: Collapsible sidebar

**Files:**
- Modify: `frontend/src/components/layout/sidebar.tsx`
- Modify: `frontend/src/app/(dashboard)/layout.tsx`

**Step 1: Add collapse state**

Use localStorage-persisted state for sidebar collapse:

```tsx
const [collapsed, setCollapsed] = useState(() => {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("sidebar_collapsed") === "true";
});

function toggleCollapse() {
  const next = !collapsed;
  setCollapsed(next);
  localStorage.setItem("sidebar_collapsed", String(next));
}
```

**Step 2: Conditional width and content**

Change the aside width class:
```tsx
className={cn(
  "hidden lg:flex lg:flex-col lg:fixed lg:inset-y-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-all duration-200",
  collapsed ? "lg:w-16" : "lg:w-64"
)}
```

When collapsed, hide labels and show only icons with tooltips:
```tsx
{collapsed ? (
  <Tooltip>
    <TooltipTrigger asChild>
      <Link href={item.href}>
        <Button variant="ghost" size="icon" className={cn("w-10 h-10", isActive && "bg-primary/15 text-primary")}>
          <Icon className="h-4 w-4" />
        </Button>
      </Link>
    </TooltipTrigger>
    <TooltipContent side="right">{item.label}</TooltipContent>
  </Tooltip>
) : (
  // existing full link
)}
```

Add a collapse toggle button at the bottom of the sidebar.

**Step 3: Update layout.tsx padding**

Pass `collapsed` state up or use a context. Change `lg:pl-64` to be dynamic:
```tsx
<div className={collapsed ? "lg:pl-16" : "lg:pl-64"}>
```

**Step 4: Commit**

```bash
git add frontend/src/components/layout/sidebar.tsx frontend/src/app/\(dashboard\)/layout.tsx
git commit -m "feat: collapsible sidebar with icon-only mode and tooltip labels"
```

---

### Task 25: Auth - add Terms of Service links

**Files:**
- Modify: `frontend/src/components/auth/register-form.tsx`

**Step 1: Add ToS text above submit button**

After the notification checkbox (line 233), add:
```tsx
<p className="text-xs text-muted-foreground">
  By creating an account, you agree to our{" "}
  <a href="/terms" target="_blank" className="underline underline-offset-4 hover:text-foreground">
    Terms of Service
  </a>{" "}
  and{" "}
  <a href="/privacy" target="_blank" className="underline underline-offset-4 hover:text-foreground">
    Privacy Policy
  </a>
  .
</p>
```

**Step 2: Commit**

```bash
git add frontend/src/components/auth/register-form.tsx
git commit -m "feat: add Terms of Service and Privacy Policy links to registration"
```

---

## Final Verification

### Task 26: Full verification pass

**Step 1: TypeScript check**
```bash
cd frontend && npx tsc --noEmit
```

**Step 2: Visual check - light mode**
- [ ] Sidebar has section headers (Core, Outreach, Insights, System)
- [ ] Active nav has orange left border
- [ ] Cmd+K search trigger visible in sidebar
- [ ] Page title shows in mobile header
- [ ] Search icon in mobile header opens command menu
- [ ] Cards hover with orange border tint
- [ ] Table rows hover with faint orange
- [ ] Input/textarea focus rings are orange
- [ ] Skeletons have shimmer animation (not pulse)
- [ ] Status badges use semantic colors (green for success, blue for delivered)
- [ ] Muted text is readable (4.5:1 contrast)
- [ ] Footer shows Settings link + keyboard shortcut hint

**Step 3: Visual check - dark mode**
- [ ] Surfaces feel warm (not cold slate) - hue consistency
- [ ] All hover/focus states work
- [ ] Shimmer skeletons visible on dark backgrounds

**Step 4: Accessibility check**
- [ ] Tab through entire dashboard - skip link appears first
- [ ] Tab reaches all nav items, search, notifications
- [ ] Password toggles reachable via keyboard
- [ ] Upload zone focusable via keyboard
- [ ] Screen reader announces nav item count via `<ul>/<li>`
- [ ] Error messages announced when input focused

**Step 5: Final commit**

```bash
git add -A
git commit -m "style: comprehensive UI/UX polish - accessibility, navigation, semantic colors, shimmer, collapsible sidebar"
```

---

## Summary

| Phase | Tasks | Priority |
|-------|-------|----------|
| 1: Critical A11y | Tasks 1-6 | WCAG AA violations - must fix |
| 2: High UX | Tasks 7-12 | Navigation, discoverability, actionable notifications |
| 3: Medium Polish | Tasks 13-20 | Dark mode unification, shimmer, component extraction, polling |
| 4: Premium | Tasks 21-25 | Bulk actions, collapsible sidebar, feature comparison, sticky save |
| Verification | Task 26 | Full pass |

**Total: 26 tasks across ~35 files. No backend changes. No new dependencies.**
