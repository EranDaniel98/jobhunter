import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "…";
}

export function fitScoreColor(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score < 0.4) return "text-destructive";
  if (score < 0.7) return "text-chart-3";
  return "text-primary";
}

export function fitScoreBarColor(score: number | null): string {
  if (score === null) return "bg-muted";
  if (score < 0.4) return "bg-destructive";
  if (score < 0.7) return "bg-chart-3";
  return "bg-primary";
}
