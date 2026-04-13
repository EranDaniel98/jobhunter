export const ROUTES = {
  LOGIN: "/login",
  REGISTER: "/register",
  DASHBOARD: "/dashboard",
  RESUME: "/resume",
  COMPANIES: "/companies",
  OUTREACH: "/outreach",
  ANALYTICS: "/analytics",
  SETTINGS: "/settings",
} as const;

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

export const COMPANY_STATUS_LABELS: Record<string, string> = {
  suggested: "Suggested",
  approved: "Approved",
  rejected: "Rejected",
};

export const RESEARCH_STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  in_progress: "Researching",
  completed: "Completed",
  failed: "Failed",
};

export const MESSAGE_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  sent: "Sent",
  delivered: "Delivered",
  opened: "Opened",
  replied: "Replied",
  bounced: "Bounced",
  failed: "Failed",
};

// Site
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://hunter-job.com";
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL ?? "support@hunter-job.com";
export const GITHUB_ISSUES_URL = "https://github.com/EranDaniel98/jobhunter/issues";

// Score thresholds
export const FIT_SCORE_HIGH = 0.7;
export const FIT_SCORE_LOW = 0.4;
export const READINESS_SCORE_HIGH = 80;
export const READINESS_SCORE_LOW = 60;
export const QUOTA_UPGRADE_THRESHOLD = 0.7;

// Polling intervals (ms)
export const POLL_FAST = 3_000;
export const POLL_NORMAL = 60_000;
export const POLL_SLOW = 120_000;
