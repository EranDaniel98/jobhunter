"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, isOnboarded } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
    if (!isLoading && isAuthenticated && isOnboarded) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, isOnboarded, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated || isOnboarded) return null;

  return <>{children}</>;
}
