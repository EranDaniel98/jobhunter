"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { TourSpotlight } from "@/components/dashboard/tour-spotlight";
import { TourTooltip } from "@/components/dashboard/tour-tooltip";
import { TOUR_STEPS } from "@/lib/tour-steps";

export function TourOverlay() {
  const { isTourCompleted, completeTour } = useAuth();
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const navigatingRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Detect mobile (sidebar hidden below lg = 1024px)
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1024);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Lock scroll + compensate for scrollbar width to prevent layout shift
  useEffect(() => {
    if (!isTourCompleted && !dismissed) {
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
      document.body.style.overflow = "hidden";
      document.body.style.paddingRight = `${scrollbarWidth}px`;
      return () => {
        document.body.style.overflow = "";
        document.body.style.paddingRight = "";
      };
    }
  }, [isTourCompleted, dismissed]);

  // Cleanup pending navigation timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  // Filter out sidebar (nav-*) steps on mobile and clamp currentStep
  const steps = useMemo(
    () => isMobile ? TOUR_STEPS.filter((s) => !s.selector.startsWith("nav-")) : TOUR_STEPS,
    [isMobile]
  );

  const clampedStep = Math.min(currentStep, steps.length - 1);

  const navigateToStep = useCallback((idx: number) => {
    if (navigatingRef.current) return;
    const step = steps[idx];
    if (step.route && step.route !== window.location.pathname) {
      navigatingRef.current = true;
      router.push(step.route);
      timerRef.current = setTimeout(() => {
        setCurrentStep(idx);
        navigatingRef.current = false;
      }, 600);
    } else {
      setCurrentStep(idx);
    }
  }, [steps, router]);

  const handleNext = useCallback(() => {
    const nextIdx = clampedStep + 1;
    if (nextIdx >= steps.length) {
      if (timerRef.current) clearTimeout(timerRef.current);
      completeTour().catch(() => {
      console.warn("Failed to persist tour completion — will retry on next visit");
    });
      setDismissed(true);
      router.push("/dashboard");
      return;
    }
    navigateToStep(nextIdx);
  }, [clampedStep, steps.length, completeTour, router, navigateToStep]);

  const handleBack = useCallback(() => {
    if (clampedStep <= 0) return;
    navigateToStep(clampedStep - 1);
  }, [clampedStep, navigateToStep]);

  const handleSkip = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    completeTour().catch(() => {
      console.warn("Failed to persist tour completion — will retry on next visit");
    });
    setDismissed(true);
    router.push("/dashboard");
  }, [completeTour, router]);

  // Keyboard navigation
  useEffect(() => {
    if (isTourCompleted || dismissed) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleSkip();
      } else if (e.key === "Enter" || e.key === "ArrowRight") {
        handleNext();
      } else if (e.key === "ArrowLeft") {
        handleBack();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isTourCompleted, dismissed, handleNext, handleBack, handleSkip]);

  if (isTourCompleted || dismissed || steps.length === 0) return null;

  const step = steps[clampedStep];

  return (
    <>
      {/* Full-screen click blocker — blocks all interaction behind the tour */}
      <div className="fixed inset-0 z-[59]" />
      <TourSpotlight selector={step.selector} />
      <TourTooltip
        title={step.title}
        description={step.description}
        currentStep={clampedStep}
        totalSteps={steps.length}
        onNext={handleNext}
        onBack={handleBack}
        onSkip={handleSkip}
        isLast={clampedStep === steps.length - 1}
        isFirst={clampedStep === 0}
      />
    </>
  );
}
