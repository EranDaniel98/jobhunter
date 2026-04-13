"use client";

import { useState, useEffect } from "react";
import { QUOTA_UPGRADE_THRESHOLD } from "@/lib/constants";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { getPlans, getUsage } from "@/lib/api/candidates";
import { useCheckout, usePortal, useSubscription } from "@/lib/hooks/use-billing";
import { PageHeader } from "@/components/shared/page-header";
import { UpgradeDialog } from "@/components/shared/upgrade-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import type { PlanDefinition, PlanTier } from "@/lib/types";
import { Check, Zap, Rocket, Crown, CreditCard, Loader2, ExternalLink } from "lucide-react";
import { toast } from "sonner";

const QUOTA_USER_LABELS: Record<string, string> = {
  discovery: "Company Discoveries",
  research: "Company Research",
  hunter: "Contact Lookups",
  email: "Emails Sent",
};

const TIER_ORDER: PlanTier[] = ["free", "explorer", "hunter"];

const TIER_ICONS: Record<string, React.ElementType> = {
  free: Zap,
  explorer: Rocket,
  hunter: Crown,
};

const PAID_TIERS = new Set(["explorer", "hunter"]);

function formatPrice(cents: number): string {
  if (cents === 0) return "$0";
  return `$${(cents / 100).toFixed(0)}`;
}

export default function PlansPage() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const { data: plans, isLoading } = useQuery({
    queryKey: ["plans"],
    queryFn: getPlans,
  });
  const { data: usage } = useQuery({
    queryKey: ["usage"],
    queryFn: getUsage,
  });
  const { data: subscription } = useSubscription();
  const checkout = useCheckout();
  const portal = usePortal();
  const [selectedPlan, setSelectedPlan] = useState<PlanDefinition | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Handle success/canceled URL params from Stripe redirect
  const router = useRouter();
  useEffect(() => {
    if (searchParams.get("success")) {
      toast.success("Subscription activated! Welcome to your new plan.");
      router.replace("/plans", { scroll: false });
    } else if (searchParams.get("canceled")) {
      toast.info("Checkout canceled. No changes were made.");
      router.replace("/plans", { scroll: false });
    }
  }, [searchParams, router]);

  const currentTier = user?.plan_tier || "free";

  function handleSelectPlan(plan: PlanDefinition) {
    if (plan.tier === currentTier) return;
    const tierIdx = TIER_ORDER.indexOf(plan.tier as PlanTier);
    const currentIdx = TIER_ORDER.indexOf(currentTier);

    if (tierIdx < currentIdx) {
      const currentPlan = sortedPlans.find((p) => p.tier === currentTier);
      if (currentPlan) {
        const decreases = Object.entries(plan.limits)
          .filter(([key, value]) => (currentPlan.limits[key] ?? 0) > value)
          .map(
            ([key, value]) =>
              `${QUOTA_USER_LABELS[key] || key}: ${currentPlan.limits[key]} → ${value}`
          )
          .join(", ");
        if (decreases) {
          toast.warning(`Downgrading will reduce: ${decreases}`);
        }
      }
    }

    // If it's a paid tier, start Stripe checkout
    if (PAID_TIERS.has(plan.tier)) {
      checkout.mutate(plan.tier);
      return;
    }

    // For free tier (downgrade), open dialog
    setSelectedPlan(plan);
    setDialogOpen(true);
  }

  // Sort plans in tier order
  const sortedPlans = plans
    ? [...plans].sort(
        (a, b) =>
          TIER_ORDER.indexOf(a.tier as PlanTier) -
          TIER_ORDER.indexOf(b.tier as PlanTier)
      )
    : [];

  // Calculate recommendation
  const recommendedTier = (() => {
    if (!usage) return null;
    const currentIdx = TIER_ORDER.indexOf(currentTier);
    const quotaEntries = Object.entries(usage.quotas);
    const atCapacity = quotaEntries.some(
      ([, q]) => q.limit > 0 && q.used / q.limit >= QUOTA_UPGRADE_THRESHOLD
    );
    if (atCapacity && currentIdx < TIER_ORDER.length - 1) {
      return TIER_ORDER[currentIdx + 1];
    }
    return null;
  })();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Plans & Pricing"
        description="Choose the plan that fits your job search intensity"
      >
        {subscription && subscription.status === "active" && (
          <Button
            variant="outline"
            onClick={() => portal.mutate()}
            disabled={portal.isPending}
          >
            {portal.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CreditCard className="mr-2 h-4 w-4" />
            )}
            Manage Billing
          </Button>
        )}
      </PageHeader>

      {/* Subscription status banner */}
      {subscription && subscription.status === "active" && subscription.current_period_end && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="flex items-center justify-between py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10">
                <CreditCard className="h-4 w-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium">
                  Active subscription &mdash;{" "}
                  <span className="capitalize">{subscription.tier}</span> plan
                </p>
                <p className="text-xs text-muted-foreground">
                  Renews on{" "}
                  {new Date(subscription.current_period_end).toLocaleDateString(
                    "en-US",
                    { month: "long", day: "numeric", year: "numeric" }
                  )}
                </p>
              </div>
            </div>
            <Badge variant="outline" className="border-primary/40 text-primary">
              Active
            </Badge>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-3">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-3">
          {sortedPlans.map((plan) => {
            const isCurrent = plan.tier === currentTier;
            const isPopular = plan.tier === "explorer";
            const tierIdx = TIER_ORDER.indexOf(plan.tier as PlanTier);
            const currentIdx = TIER_ORDER.indexOf(currentTier);
            const isUpgrade = tierIdx > currentIdx;
            const isCheckingOut =
              checkout.isPending &&
              checkout.variables === plan.tier;

            return (
              <Card
                key={plan.tier}
                className={`relative flex flex-col ${
                  isPopular ? "border-primary shadow-md shadow-primary/10" : ""
                } ${isCurrent ? "ring-2 ring-primary/20" : ""}`}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-primary text-primary-foreground">
                      Popular
                    </Badge>
                  </div>
                )}
                {plan.tier === recommendedTier && (
                  <div className="absolute -top-3 right-4">
                    <Badge className="bg-chart-3 text-white">
                      Recommended
                    </Badge>
                  </div>
                )}
                <CardHeader className="text-center pb-2 pt-8">
                  {(() => {
                    const TierIcon = TIER_ICONS[plan.tier] || Zap;
                    return (
                      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                        <TierIcon className="h-6 w-6 text-primary" />
                      </div>
                    );
                  })()}
                  <CardTitle className="text-lg">{plan.display_name}</CardTitle>
                  <div className="mt-2">
                    <span className="text-3xl font-bold">
                      {formatPrice(plan.price_monthly_cents)}
                    </span>
                    {plan.price_monthly_cents > 0 && (
                      <span className="text-muted-foreground">/mo</span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {plan.description}
                  </p>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col">
                  <ul className="space-y-2.5 flex-1">
                    {Object.entries(plan.limits).map(([key, value]) => (
                      <li
                        key={key}
                        className="flex items-center gap-2 text-sm"
                      >
                        <Check className="h-4 w-4 text-primary shrink-0" />
                        <span>
                          <span className="font-medium">{value}</span>{" "}
                          {QUOTA_USER_LABELS[key] || key}/day
                        </span>
                      </li>
                    ))}
                  </ul>
                  {isCurrent && usage && (
                    <div className="mt-4 space-y-2 rounded-lg bg-muted/50 p-3">
                      <p className="text-xs font-medium text-muted-foreground">Today&apos;s Usage</p>
                      {Object.entries(usage.quotas).map(([key, q]) => (
                        <div key={key} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span>{QUOTA_USER_LABELS[key] || key}</span>
                            <span className="tabular-nums">{q.used}/{q.limit}</span>
                          </div>
                          <Progress value={q.limit > 0 ? (q.used / q.limit) * 100 : 0} className="h-1.5" />
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="mt-6">
                    <Button
                      variant="outline"
                      className="w-full"
                      disabled
                    >
                      {isCurrent ? "Current Plan" : "Coming Soon"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {sortedPlans && sortedPlans.length > 0 && (
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
                      <TableCell key={p.tier} className="text-center">
                        <div className="space-y-1">
                          <span className="font-medium">{p.limits[key] ?? "-"}/day</span>
                          {p.tier === currentTier && usage?.quotas[key] && (
                            <div className="space-y-0.5">
                              <Progress
                                value={(usage.quotas[key].used / usage.quotas[key].limit) * 100}
                                className="h-1.5 mx-auto max-w-[80px]"
                              />
                              <span className="text-[10px] text-muted-foreground block">
                                {usage.quotas[key].used}/{usage.quotas[key].limit} used
                              </span>
                            </div>
                          )}
                        </div>
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <UpgradeDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        plan={selectedPlan}
      />
    </div>
  );
}
