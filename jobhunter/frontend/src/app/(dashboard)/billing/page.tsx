"use client";

import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { useSubscription, usePortal } from "@/lib/hooks/use-billing";
import { useQuery } from "@tanstack/react-query";
import { getUsage } from "@/lib/api/candidates";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import { CreditCard, ExternalLink, ArrowUpRight, Loader2, Calendar, Zap, Rocket, Crown } from "lucide-react";

const QUOTA_USER_LABELS: Record<string, string> = {
  discovery: "Company Discoveries",
  research: "Company Research",
  hunter: "Contact Lookups",
  email: "Emails Sent",
};

const TIER_ICONS: Record<string, React.ElementType> = {
  free: Zap,
  explorer: Rocket,
  hunter: Crown,
};

const TIER_DISPLAY: Record<string, string> = {
  free: "Free",
  explorer: "Explorer",
  hunter: "Hunter",
};

export default function BillingPage() {
  const { user } = useAuth();
  const { data: subscription, isLoading: subLoading } = useSubscription();
  const { data: usage, isLoading: usageLoading } = useQuery({
    queryKey: ["usage"],
    queryFn: getUsage,
  });
  const portal = usePortal();

  const currentTier = user?.plan_tier || "free";
  const TierIcon = TIER_ICONS[currentTier] || Zap;
  const isActive = subscription?.status === "active";
  const isLoading = subLoading || usageLoading;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing"
        description="Manage your subscription and billing details"
      >
        <Button variant="outline" asChild>
          <Link href="/plans">
            View Plans
            <ArrowUpRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </PageHeader>

      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Current Plan Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TierIcon className="h-5 w-5 text-primary" />
                Current Plan
              </CardTitle>
              <CardDescription>
                Your active subscription details
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold">
                    {TIER_DISPLAY[currentTier] || currentTier}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {currentTier === "free"
                      ? "No charge"
                      : currentTier === "explorer"
                        ? "$29/month"
                        : "$99/month"}
                  </p>
                </div>
                <Badge
                  variant={isActive ? "default" : "secondary"}
                  className={isActive ? "bg-green-600" : ""}
                >
                  {isActive ? "Active" : currentTier === "free" ? "Free Tier" : subscription?.status || "Inactive"}
                </Badge>
              </div>

              {subscription?.current_period_end && (
                <div className="flex items-center gap-2 rounded-lg bg-muted/50 p-3 text-sm">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span>
                    {isActive ? "Renews" : "Expires"} on{" "}
                    <span className="font-medium">
                      {new Date(subscription.current_period_end).toLocaleDateString(
                        "en-US",
                        { month: "long", day: "numeric", year: "numeric" }
                      )}
                    </span>
                  </span>
                </div>
              )}

              <div className="flex gap-2 pt-2">
                {isActive && (
                  <Button
                    variant="outline"
                    onClick={() => portal.mutate()}
                    disabled={portal.isPending}
                    className="flex-1"
                  >
                    {portal.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <CreditCard className="mr-2 h-4 w-4" />
                    )}
                    Manage Billing
                  </Button>
                )}
                <Button asChild variant="outline" className="flex-1">
                  <Link href="/plans">
                    View Plans
                    <ExternalLink className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Usage Overview Card */}
          <Card>
            <CardHeader>
              <CardTitle>Today&apos;s Usage</CardTitle>
              <CardDescription>
                Daily quota consumption for your current plan
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {usage ? (
                Object.entries(usage.quotas).map(([key, q]) => {
                  const pct = q.limit > 0 ? (q.used / q.limit) * 100 : 0;
                  const isNearLimit = pct >= 80;
                  return (
                    <div key={key} className="space-y-1.5">
                      <div className="flex justify-between text-sm">
                        <span className="font-medium">
                          {QUOTA_USER_LABELS[key] || key}
                        </span>
                        <span
                          className={`tabular-nums ${
                            isNearLimit ? "text-destructive font-medium" : "text-muted-foreground"
                          }`}
                        >
                          {q.used}/{q.limit}
                        </span>
                      </div>
                      <Progress
                        value={pct}
                        className={`h-2 ${isNearLimit ? "[&>div]:bg-destructive" : ""}`}
                      />
                    </div>
                  );
                })
              ) : (
                <p className="text-sm text-muted-foreground">No usage data available</p>
              )}

              {usage && Object.values(usage.quotas).some(
                (q) => q.limit > 0 && q.used / q.limit >= 0.7
              ) && (
                <div className="rounded-lg bg-primary/5 border border-primary/20 p-3 text-sm">
                  <p className="font-medium text-primary">Running low on quotas?</p>
                  <p className="text-muted-foreground mt-1">
                    Paid plans with higher limits are coming soon! Quotas reset daily at midnight UTC.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
