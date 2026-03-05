"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getUsage } from "@/lib/api/candidates";
import type { QuotaItem, PlanTier } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

const QUOTA_LABELS: Record<string, string> = {
  discovery: "Company Discoveries",
  research: "Company Research",
  hunter: "Contact Lookups",
  email: "Emails Sent",
};

const PLAN_DISPLAY: Record<PlanTier, { name: string; className: string }> = {
  free: { name: "Free Plan", className: "" },
  explorer: { name: "Explorer", className: "bg-secondary text-secondary-foreground" },
  hunter: { name: "Hunter", className: "bg-primary/15 text-primary" },
};

// Full class strings so Tailwind can detect them at build time
const COLOR_GREEN = "[&_[data-slot=progress-indicator]]:bg-primary";
const COLOR_YELLOW = "[&_[data-slot=progress-indicator]]:bg-chart-3";
const COLOR_RED = "[&_[data-slot=progress-indicator]]:bg-destructive";

function progressColorClass(used: number, limit: number): string {
  if (limit === 0) return COLOR_GREEN;
  const pct = (used / limit) * 100;
  if (pct >= 90) return COLOR_RED;
  if (pct >= 70) return COLOR_YELLOW;
  return COLOR_GREEN;
}

function QuotaRow({ label, quota }: { label: string; quota: QuotaItem }) {
  const pct = quota.limit > 0 ? (quota.used / quota.limit) * 100 : 0;
  const atLimit = quota.used >= quota.limit && quota.limit > 0;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">
          {quota.used} / {quota.limit}
          {atLimit && (
            <span className="ml-1.5 text-xs text-destructive">Limit reached</span>
          )}
        </span>
      </div>
      <Progress
        value={pct}
        className={`h-2 ${progressColorClass(quota.used, quota.limit)}`}
      />
    </div>
  );
}

export function UsageCard() {
  const { data } = useQuery({
    queryKey: ["usage"],
    queryFn: getUsage,
    refetchInterval: 60_000,
    retry: 1,
  });

  if (!data) return null;

  const tier = data.plan_tier || "free";
  const plan = PLAN_DISPLAY[tier] || PLAN_DISPLAY.free;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Daily Usage</CardTitle>
        {plan.className ? (
          <Badge className={plan.className}>{plan.name}</Badge>
        ) : (
          <Badge variant="secondary">{plan.name}</Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {Object.entries(QUOTA_LABELS).map(([key, label]) => {
          const quota = data.quotas?.[key];
          if (!quota) return null;
          return <QuotaRow key={key} label={label} quota={quota} />;
        })}
        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-muted-foreground">
            Resets daily at midnight UTC
          </p>
          {tier !== "hunter" && (
            <Link
              href="/plans"
              className="text-xs font-medium text-primary hover:underline"
            >
              Upgrade
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
