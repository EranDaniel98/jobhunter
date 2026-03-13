# JobHunter AI - Frontend

Next.js 16 frontend for the JobHunter AI platform.

## Tech Stack

- **Framework**: Next.js 16 (App Router, Turbopack)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui (Radix primitives)
- **State**: React Query (TanStack Query) for server state
- **Auth**: JWT tokens stored in localStorage via AuthProvider context
- **Charts**: Recharts (registration trend, analytics)

## Pages

| Route | Description |
|-------|-------------|
| `/` | Landing page |
| `/login` | Authentication |
| `/register` | Invite-only registration |
| `/dashboard` | Home dashboard |
| `/companies` | Company pipeline (add, discover, approve/reject) |
| `/companies/[id]` | Company detail with dossier, contacts, outreach |
| `/outreach` | Message inbox (drafts, sent, RTL support) |
| `/resume` | Resume upload & DNA profile |
| `/analytics` | Pipeline funnel & outreach stats |
| `/admin` | Admin dashboard (5 tabs: Overview, Users, Invites, Activity, Broadcast) |
| `/settings` | Profile, preferences, notifications, invite management |

## Getting Started

```bash
# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build

# Type check
npx tsc --noEmit
```

## Project Structure

```
src/
├── app/
│   ├── (auth)/              # Login & register pages
│   ├── (dashboard)/         # All authenticated pages
│   │   ├── admin/           # Admin dashboard
│   │   ├── analytics/       # Pipeline & outreach analytics
│   │   ├── companies/       # Company pipeline & detail
│   │   ├── dashboard/       # Home
│   │   ├── outreach/        # Message management
│   │   ├── resume/          # Resume upload & DNA
│   │   └── settings/        # Profile & preferences
│   └── page.tsx             # Landing page
├── components/
│   ├── admin/               # Admin-specific components
│   │   ├── activity-feed    # Cross-tenant event stream
│   │   ├── audit-log-table  # Admin action audit trail
│   │   ├── broadcast-form   # Email broadcast composer
│   │   ├── invite-chain     # Invite relationship graph
│   │   ├── overview-stats   # System metrics cards
│   │   ├── registration-chart # 30-day trend chart
│   │   ├── user-detail-drawer # User profile slide-over
│   │   └── users-table      # User management with actions
│   ├── layout/              # Sidebar, mobile nav
│   ├── shared/              # PageHeader, FitScore, skeletons
│   └── ui/                  # shadcn/ui primitives
├── lib/
│   ├── api/                 # Typed Axios API clients
│   │   ├── admin.ts         # Admin endpoints
│   │   ├── auth.ts          # Auth endpoints
│   │   ├── client.ts        # Axios instance with interceptors
│   │   ├── companies.ts     # Company endpoints
│   │   ├── invites.ts       # Invite endpoints
│   │   └── outreach.ts      # Outreach endpoints
│   ├── hooks/               # React Query hooks (mutations + queries)
│   └── types.ts             # Shared TypeScript interfaces
└── providers/
    └── auth-provider.tsx    # JWT auth context with auto-refresh
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL (e.g. `http://localhost:8000/api/v1`) |
