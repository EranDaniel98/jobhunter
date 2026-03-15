import { Check } from "lucide-react";

interface StepIndicatorProps {
  currentStep: number;
  steps: string[];
}

export function StepIndicator({ currentStep, steps }: StepIndicatorProps) {
  return (
    <div>
      {/* Mobile: compact */}
      <div className="flex items-center justify-center gap-2 sm:hidden">
        <span className="text-sm font-medium text-primary">
          Step {currentStep + 1} of {steps.length}
        </span>
        <span className="text-sm text-muted-foreground">— {steps[currentStep]}</span>
      </div>

      {/* Desktop: full stepper */}
      <div className="hidden sm:flex items-center justify-center">
        {steps.map((label, i) => {
          const isCompleted = i < currentStep;
          const isCurrent = i === currentStep;

          return (
            <div key={label} className="flex items-center">
              <div className="flex flex-col items-center gap-1.5">
                {isCompleted ? (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary">
                    <Check className="h-4 w-4 text-primary-foreground" />
                  </div>
                ) : isCurrent ? (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-primary bg-background">
                    <span className="text-sm font-semibold text-primary">{i + 1}</span>
                  </div>
                ) : (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-muted-foreground/30 bg-background">
                    <span className="text-sm text-muted-foreground">{i + 1}</span>
                  </div>
                )}
                <span
                  className={`text-xs whitespace-nowrap ${
                    isCurrent ? "font-medium text-foreground" : "text-muted-foreground"
                  }`}
                >
                  {label}
                </span>
              </div>

              {i < steps.length - 1 && (
                <div
                  className={`mx-3 mt-[-1.25rem] h-0.5 w-12 lg:w-20 ${
                    i < currentStep ? "bg-primary" : "bg-muted-foreground/20"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
