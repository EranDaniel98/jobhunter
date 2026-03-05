"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/providers/auth-provider";
import { getPlans } from "@/lib/api/candidates";
import { PageHeader } from "@/components/shared/page-header";
import { UpgradeDialog } from "@/components/shared/upgrade-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import type { PlanDefinition, PlanTier } from "@/lib/types";
import { Check } from "lucide-react";

const QUOTA_USER_LABELS: Record<string, string> = {
  discovery: "Company Discoveries",
  research: "Company Research",
  hunter: "Contact Lookups",
  email: "Emails Sent",
};

const TIER_ORDER: PlanTier[] = ["free", "explorer", "hunter"];

function formatPrice(cents: number): string {
  if (cents === 0) return "$0";
  return `$${(cents / 100).toFixed(0)}`;
}

export default function PlansPage() {
  const { user } = useAuth();
  const { data: plans, isLoading } = useQuery({
    queryKey: ["plans"],
    queryFn: getPlans,
  });
  const [selectedPlan, setSelectedPlan] = useState<PlanDefinition | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const currentTier = user?.plan_tier || "free";

  function handleSelectPlan(plan: PlanDefinition) {
    if (plan.tier === currentTier) return;
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Plans & Pricing"
        description="Choose the plan that fits your job search intensity"
      />

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

            return (
              <Card
                key={plan.tier}
                className={`relative flex flex-col ${
                  isPopular ? "border-primary shadow-md shadow-primary/10" : ""
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-primary text-primary-foreground">
                      Popular
                    </Badge>
                  </div>
                )}
                <CardHeader className="text-center pb-2">
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
                  <div className="mt-6">
                    {isCurrent ? (
                      <Button
                        variant="outline"
                        className="w-full"
                        disabled
                      >
                        Current Plan
                      </Button>
                    ) : isUpgrade ? (
                      <Button
                        className="w-full"
                        onClick={() => handleSelectPlan(plan)}
                      >
                        Upgrade to {plan.display_name}
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={() => handleSelectPlan(plan)}
                      >
                        Downgrade
                      </Button>
                    )}
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
                      <TableCell key={p.tier} className="text-center font-medium">
                        {p.limits[key] ?? "—"}/day
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
