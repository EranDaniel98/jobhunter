"use client";

import { StepIndicator } from "@/components/onboarding/step-indicator";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Loader2 } from "lucide-react";

interface WizardShellProps {
  currentStep: number;
  steps: string[];
  children: React.ReactNode;
  onBack: () => void;
  onNext: () => void;
  onSkip?: () => void;
  showBack?: boolean;
  canSkip?: boolean;
  nextLabel?: string;
  isNextLoading?: boolean;
  isNextDisabled?: boolean;
  resumeMessage?: string;
}

export function WizardShell({
  currentStep,
  steps,
  children,
  onBack,
  onNext,
  onSkip,
  showBack = true,
  canSkip = false,
  nextLabel = "Next",
  isNextLoading = false,
  isNextDisabled = false,
  resumeMessage,
}: WizardShellProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="border-b bg-background/95 backdrop-blur px-4 py-4">
        <div className="mx-auto max-w-2xl">
          <StepIndicator currentStep={currentStep} steps={steps} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-8 sm:px-6">
        <div className="mx-auto max-w-2xl animate-in fade-in duration-300">
          {resumeMessage && (
            <div className="mb-6 flex items-center gap-2 rounded-lg bg-primary/10 px-4 py-2.5 text-sm text-primary animate-in fade-in slide-in-from-top-2 duration-500">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{resumeMessage}</span>
            </div>
          )}
          {children}
        </div>
      </div>

      <div className="border-t bg-background px-4 py-4">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <div>
            {showBack && currentStep > 0 && (
              <Button variant="ghost" onClick={onBack}>
                Back
              </Button>
            )}
          </div>
          <div className="flex items-center gap-3">
            {canSkip && onSkip && (
              <Button variant="ghost" onClick={onSkip} className="text-muted-foreground">
                Skip
              </Button>
            )}
            <Button onClick={onNext} disabled={isNextLoading || isNextDisabled}>
              {isNextLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {nextLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
