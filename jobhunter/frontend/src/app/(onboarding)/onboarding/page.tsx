"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/providers/auth-provider";
import * as candidatesApi from "@/lib/api/candidates";
import { WizardShell } from "@/components/onboarding/wizard-shell";
import { StepWelcome } from "@/components/onboarding/step-welcome";
import { StepProfile, type StepProfileHandle } from "@/components/onboarding/step-profile";
import { StepEmailVerify } from "@/components/onboarding/step-email-verify";
import { StepResume } from "@/components/onboarding/step-resume";
import { toast } from "sonner";

const STEPS = ["Welcome", "Profile", "Verify Email", "Resume"];

function computeInitialStep(
  user: {
    headline?: string | null;
    location?: string | null;
    target_roles?: string[] | null;
    target_industries?: string[] | null;
    target_locations?: string[] | null;
    salary_min?: number | null;
    salary_max?: number | null;
    email_verified?: boolean;
  } | null,
  hasDna: boolean
): number | "done" {
  if (!user) return 0;

  const hasProfile = !!(
    user.headline ||
    user.location ||
    (user.target_roles && user.target_roles.length > 0) ||
    (user.target_industries && user.target_industries.length > 0) ||
    (user.target_locations && user.target_locations.length > 0) ||
    user.salary_min ||
    user.salary_max
  );

  if (hasProfile && hasDna) return "done"; // Wizard already complete → dashboard tour
  if (hasProfile && !user.email_verified) return 2; // Skip to Verify Email
  if (hasProfile) return 3;                // Skip to Resume
  return 0;                                // Start from Welcome
}

export default function OnboardingPage() {
  const { user, completeOnboarding } = useAuth();
  const router = useRouter();

  // Check if DNA already exists (for resume step)
  const dnaQuery = useQuery({
    queryKey: ["dna"],
    queryFn: candidatesApi.getDNA,
    retry: 1,
    staleTime: Infinity,
  });

  // Wait for DNA query to settle before computing initial step
  const isReady = !dnaQuery.isLoading;
  const initialStep = useMemo(
    () => computeInitialStep(user, !!dnaQuery.data),
    [user, dnaQuery.data]
  );

  // Track whether user resumed from a later step (for "Welcome back" message)
  const isResuming = isReady && typeof initialStep === "number" && initialStep > 0;

  const [currentStep, setCurrentStep] = useState<number | null>(null);
  const [isNextLoading, setIsNextLoading] = useState(false);
  const profileRef = useRef<StepProfileHandle>(null);

  // If user already completed all wizard steps, auto-complete and redirect to dashboard tour
  useEffect(() => {
    if (isReady && initialStep === "done") {
      completeOnboarding()
        .then(() => router.push("/dashboard"))
        .catch(() => toast.error("Could not complete setup. Please refresh and try again."));
    }
  }, [isReady, initialStep, completeOnboarding, router]);

  // Set initial step once data is ready
  if (isReady && currentStep === null && initialStep !== "done") {
    setCurrentStep(initialStep);
  }

  // Show loading while computing initial step or auto-completing
  if (currentStep === null) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const goBack = () => {
    setCurrentStep((prev) => Math.max(0, (prev ?? 0) - 1));
  };

  const goForward = () => {
    setCurrentStep((prev) => Math.min(STEPS.length - 1, (prev ?? 0) + 1));
  };

  const handleNext = async () => {
    // Step 0 (Welcome): just advance
    if (currentStep === 0) {
      goForward();
      return;
    }

    // Step 1 (Profile): trigger form submission
    if (currentStep === 1) {
      if (profileRef.current) {
        setIsNextLoading(true);
        try {
          await profileRef.current.submit();
        } finally {
          setIsNextLoading(false);
        }
      }
      return;
    }

    // Step 2 (Verify Email): just advance
    if (currentStep === 2) {
      goForward();
      return;
    }

    // Step 3 (Resume): finish wizard → go to dashboard (tour starts there)
    if (currentStep === 3) {
      setIsNextLoading(true);
      try {
        await completeOnboarding();
        router.push("/dashboard");
      } catch {
        toast.error("Something went wrong. Please try again.");
        setIsNextLoading(false);
      }
    }
  };

  const handleSkip = () => {
    if (currentStep === 3) {
      // Skipping resume = finish wizard without upload
      handleNext();
      return;
    }
    goForward();
  };

  const getNextLabel = () => {
    switch (currentStep) {
      case 0: return "Let's get started";
      case 1: return "Save & continue";
      case 2: return "Continue";
      case 3: return "Go to Dashboard";
      default: return "Next";
    }
  };

  return (
    <WizardShell
      currentStep={currentStep}
      steps={STEPS}
      onBack={goBack}
      onNext={handleNext}
      onSkip={handleSkip}
      showBack={currentStep > 0}
      canSkip={currentStep === 1 || currentStep === 2 || currentStep === 3}
      nextLabel={getNextLabel()}
      isNextLoading={isNextLoading}
      resumeMessage={isResuming && currentStep === initialStep ? "Welcome back — your progress has been saved." : undefined}
    >
      {currentStep === 0 && <StepWelcome />}
      {currentStep === 1 && <StepProfile ref={profileRef} onComplete={goForward} />}
      {currentStep === 2 && <StepEmailVerify />}
      {currentStep === 3 && <StepResume />}
    </WizardShell>
  );
}
