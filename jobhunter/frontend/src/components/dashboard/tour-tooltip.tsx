"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

interface TourTooltipProps {
  title: string;
  description: string;
  currentStep: number;
  totalSteps: number;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
  isLast: boolean;
  isFirst: boolean;
}

export function TourTooltip({
  title,
  description,
  currentStep,
  totalSteps,
  onNext,
  onBack,
  onSkip,
  isLast,
  isFirst,
}: TourTooltipProps) {
  const progress = ((currentStep + 1) / totalSteps) * 100;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[62] w-full max-w-md px-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <Card className="shadow-xl border-primary/20 overflow-hidden">
        {/* Progress bar */}
        <div className="h-1 bg-muted">
          <div
            className="h-full bg-primary transition-all duration-500 ease-in-out"
            style={{ width: `${progress}%` }}
          />
        </div>
        <CardContent className="space-y-3 py-4">
          <div className="flex items-start justify-between">
            <h3 className="font-semibold text-base">{title}</h3>
            <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={onSkip}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-muted-foreground">
              {currentStep + 1} of {totalSteps}
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={onSkip}>
                Skip tour
              </Button>
              {!isFirst && (
                <Button variant="outline" size="sm" onClick={onBack}>
                  <ChevronLeft className="mr-1 h-3.5 w-3.5" />
                  Back
                </Button>
              )}
              <Button size="sm" onClick={onNext}>
                {isLast ? "Finish" : "Next"}
                {!isLast && <ChevronRight className="ml-1 h-3.5 w-3.5" />}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
