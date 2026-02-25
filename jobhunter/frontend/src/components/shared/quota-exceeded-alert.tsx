"use client";

import Link from "next/link";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertTriangle } from "lucide-react";

const QUOTA_LABELS: Record<string, string> = {
  discovery: "company discovery",
  research: "company research",
  hunter: "contact lookup",
  email: "email",
};

interface QuotaExceededAlertProps {
  quotaType: string;
  limit: number;
}

export function QuotaExceededAlert({ quotaType, limit }: QuotaExceededAlertProps) {
  const label = QUOTA_LABELS[quotaType] || quotaType;

  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Limit reached</AlertTitle>
      <AlertDescription>
        You&apos;ve used all {limit} daily {label} actions.{" "}
        <Link href="/plans" className="font-medium underline">
          Upgrade your plan
        </Link>{" "}
        for higher limits, or try again tomorrow.
      </AlertDescription>
    </Alert>
  );
}
