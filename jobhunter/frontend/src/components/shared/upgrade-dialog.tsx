"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { PlanDefinition } from "@/lib/types";

const QUOTA_USER_LABELS: Record<string, string> = {
  discovery: "Company Discoveries",
  research: "Company Research",
  hunter: "Contact Lookups",
  email: "Emails Sent",
};

interface UpgradeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan: PlanDefinition | null;
}

export function UpgradeDialog({ open, onOpenChange, plan }: UpgradeDialogProps) {
  if (!plan) return null;

  const price =
    plan.price_monthly_cents === 0
      ? "Free"
      : `$${(plan.price_monthly_cents / 100).toFixed(0)}/mo`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{plan.display_name} Plan</DialogTitle>
          <DialogDescription>
            {price} &mdash; {plan.description}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 py-4">
          <p className="text-sm font-medium">What&apos;s included:</p>
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            {Object.entries(plan.limits).map(([key, value]) => (
              <li key={key} className="flex justify-between">
                <span>{QUOTA_USER_LABELS[key] || key}</span>
                <span className="font-medium text-foreground">{value}/day</span>
              </li>
            ))}
          </ul>
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <Button disabled className="w-full">
            Coming Soon
          </Button>
          <Button
            variant="ghost"
            className="w-full"
            onClick={() => onOpenChange(false)}
          >
            Maybe later
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
