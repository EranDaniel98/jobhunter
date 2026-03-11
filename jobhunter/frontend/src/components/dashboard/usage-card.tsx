"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getUsage } from "@/lib/api/candidates";
import type { QuotaItem, PlanTier } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

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

type Period = "daily" | "weekly" | "monthly";

const PERIOD_LABELS: Record<Period, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
};

const PERIOD_RESET: Record<Period, string> = {
  daily: "Resets daily at midnight UTC",
  weekly: "Rolling 7-day window",
  monthly: "Rolling 30-day window",
};

export function UsageCard() {
  const [period, setPeriod] = useState<Period>("daily");

  const { data } = useQuery({
    queryKey: ["usage"],
    queryFn: getUsage,
    refetchInterval: 60_000,
    retry: 1,
  });

  if (!data) return null;

  const tier = data.plan_tier || "free";
  const plan = PLAN_DISPLAY[tier] || PLAN_DISPLAY.free;

  const quotaMap: Record<Period, Record<string, QuotaItem> | undefined> = {
    daily: data.quotas,
    weekly: data.weekly,
    monthly: data.monthly,
  };
  const activeQuotas = quotaMap[period] ?? data.quotas;

  return (
    <Card>
      <CardHeader className="pb-2 space-y-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Usage</CardTitle>
          {plan.className ? (
            <Badge className={plan.className}>{plan.name}</Badge>
          ) : (
            <Badge variant="secondary">{plan.name}</Badge>
          )}
        </div>
        <Tabs value={period} onValueChange={(v) => setPeriod(v as Period)}>
          <TabsList className="h-7 w-full">
            {(Object.keys(PERIOD_LABELS) as Period[]).map((p) => (
              <TabsTrigger key={p} value={p} className="flex-1 text-xs h-6">
                {PERIOD_LABELS[p]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </CardHeader>
      <CardContent className="space-y-3">
        {Object.entries(QUOTA_LABELS).map(([key, label]) => {
          const quota = activeQuotas?.[key];
          if (!quota) return null;
          return <QuotaRow key={key} label={label} quota={quota} />;
        })}
        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-muted-foreground">
            {PERIOD_RESET[period]}
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
