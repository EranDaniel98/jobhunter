"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Briefcase } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, isOnboarded } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(isOnboarded ? "/dashboard" : "/onboarding");
    }
  }, [isAuthenticated, isLoading, isOnboarded, router]);

  if (isLoading) return null;
  if (isAuthenticated) return null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted px-4">
      <div className="w-full max-w-md space-y-6">
        <div className="flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/70 shadow-md shadow-primary/25">
            <Briefcase className="h-6 w-6 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold">JobHunter AI</h1>
          <p className="text-sm text-muted-foreground">
            AI-powered job search platform
          </p>
        </div>
        {children}
      </div>
    </div>
  );
}
