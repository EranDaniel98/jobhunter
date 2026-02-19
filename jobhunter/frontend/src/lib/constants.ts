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
  suggested: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  approved: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
};

export const RESEARCH_STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  in_progress: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
};

export const MESSAGE_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  sent: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  delivered: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  opened: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  replied: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300",
  bounced: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
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
