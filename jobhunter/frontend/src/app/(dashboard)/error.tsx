"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="mb-4 rounded-full bg-destructive/10 p-4">
        <AlertTriangle className="h-8 w-8 text-destructive" />
      </div>
      <h2 className="mb-2 text-lg font-semibold">Something went wrong</h2>
      <p className="mb-6 max-w-md text-sm text-muted-foreground">
        An unexpected error occurred. Please try again or refresh the page.
      </p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
