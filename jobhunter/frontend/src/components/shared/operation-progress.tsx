"use client";

import { Loader2, AlertTriangle, CheckCircle2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface OperationStep {
  key: string;
  label: string;
}

export interface OperationProgressProps {
  status: string;
  label: string;
  steps?: OperationStep[];
  onRetry?: () => void;
  errorMessage?: string;
  className?: string;
}

const FAILED_STATES = ["failed"];
const COMPLETED_STATES = ["completed", "analyzed"];

function isFailed(status: string): boolean {
  return FAILED_STATES.includes(status);
}

function isCompleted(status: string): boolean {
  return COMPLETED_STATES.includes(status);
}

export function OperationProgress({
  status,
  label,
  steps,
  onRetry,
  errorMessage,
  className,
}: OperationProgressProps) {
  if (isFailed(status)) {
    return (
      <Card className={className} role="status" aria-live="polite">
        <CardContent className="p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-destructive mt-0.5 flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <p className="font-medium text-sm">{label}</p>
              {errorMessage && (
                <p className="text-sm text-muted-foreground">{errorMessage}</p>
              )}
              {onRetry && (
                <Button variant="outline" size="sm" onClick={onRetry} className="mt-2">
                  <RotateCcw className="mr-2 h-3.5 w-3.5" />
                  Retry
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isCompleted(status)) {
    return (
      <Card className={className} role="status" aria-live="polite">
        <CardContent className="p-6">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-chart-3 flex-shrink-0" />
            <p className="font-medium text-sm">{label}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // In-progress / pending
  if (steps && steps.length > 0) {
    const currentIndex = steps.findIndex((s) => s.key === status);
    const activeIndex = currentIndex >= 0 ? currentIndex : 0;

    return (
      <Card className={className} role="status" aria-live="polite">
        <CardContent className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <Loader2 className="h-5 w-5 animate-spin text-primary flex-shrink-0" />
            <p className="font-medium text-sm" aria-live="polite">{label}</p>
          </div>
          <div
            className="flex items-center gap-2"
            role="progressbar"
            aria-valuenow={activeIndex + 1}
            aria-valuemin={1}
            aria-valuemax={steps.length}
            aria-label={`Step ${activeIndex + 1} of ${steps.length}`}
          >
            {steps.map((step, i) => (
              <div key={step.key} className="flex items-center gap-2 flex-1">
                <div
                  className={cn(
                    "h-2 flex-1 rounded-full transition-colors",
                    i < activeIndex && "bg-chart-3",
                    i === activeIndex && "bg-primary",
                    i > activeIndex && "bg-muted"
                  )}
                />
              </div>
            ))}
          </div>
          <div className="mt-2 flex justify-between text-xs text-muted-foreground">
            {steps.map((step, i) => (
              <span
                key={step.key}
                className={cn(
                  i === activeIndex && "text-primary font-medium",
                  i < activeIndex && "text-chart-3"
                )}
              >
                {step.label}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Single-state in progress
  return (
    <Card className={className} role="status" aria-live="polite">
      <CardContent className="p-6">
        <div className="flex items-center gap-3 mb-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary flex-shrink-0" />
          <p className="font-medium text-sm">{label}</p>
        </div>
        <div
          className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
          role="progressbar"
          aria-label={label}
        >
          <div className="h-full w-1/3 rounded-full bg-primary animate-[indeterminate_1.5s_ease-in-out_infinite]" />
        </div>
      </CardContent>
    </Card>
  );
}
