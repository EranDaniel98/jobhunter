"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { useAuth } from "@/providers/auth-provider";
import { TourSpotlight } from "@/components/dashboard/tour-spotlight";
import { TourTooltip } from "@/components/dashboard/tour-tooltip";
import { TOUR_STEPS } from "@/lib/tour-steps";

export function TourOverlay() {
  const { isTourCompleted, completeTour } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile (sidebar hidden below lg = 1024px)
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1024);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Filter out sidebar (nav-*) steps on mobile
  const steps = useMemo(
    () => isMobile ? TOUR_STEPS.filter((s) => !s.selector.startsWith("nav-")) : TOUR_STEPS,
    [isMobile]
  );

  const handleNext = useCallback(() => {
    if (currentStep >= steps.length - 1) {
      completeTour();
      setDismissed(true);
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep, steps.length, completeTour]);

  const handleSkip = useCallback(() => {
    completeTour();
    setDismissed(true);
  }, [completeTour]);

  if (isTourCompleted || dismissed || steps.length === 0) return null;

  const step = steps[currentStep];

  return (
    <>
      <TourSpotlight selector={step.selector} />
      <TourTooltip
        selector={step.selector}
        position={step.position}
        title={step.title}
        description={step.description}
        currentStep={currentStep}
        totalSteps={steps.length}
        onNext={handleNext}
        onSkip={handleSkip}
        isLast={currentStep === steps.length - 1}
      />
    </>
  );
}
