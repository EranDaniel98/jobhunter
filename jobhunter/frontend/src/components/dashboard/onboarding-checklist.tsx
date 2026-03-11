"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check, Circle, X, Upload, Search, Send } from "lucide-react";

interface OnboardingChecklistProps {
  hasResume: boolean;
  hasCompanies: boolean;
  hasSentMessages: boolean;
}

export function OnboardingChecklist({ hasResume, hasCompanies, hasSentMessages }: OnboardingChecklistProps) {
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("onboarding_dismissed") === "true";
  });

  const steps = [
    { label: "Upload your resume", done: hasResume, href: "/resume", icon: Upload },
    { label: "Discover companies", done: hasCompanies, href: "/companies", icon: Search },
    { label: "Send your first outreach", done: hasSentMessages, href: "/outreach", icon: Send },
  ];

  const allDone = steps.every((s) => s.done);
  if (dismissed || allDone) return null;

  const completedCount = steps.filter((s) => s.done).length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div>
          <CardTitle className="text-base">Getting Started</CardTitle>
          <p className="text-sm text-muted-foreground">{completedCount} of {steps.length} complete</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => { localStorage.setItem("onboarding_dismissed", "true"); setDismissed(true); }}
          aria-label="Dismiss getting started"
        >
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="h-2 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${(completedCount / steps.length) * 100}%` }}
          />
        </div>
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <Link key={step.href} href={step.href} className="flex items-center gap-3 rounded-md p-2 transition-colors hover:bg-muted">
              {step.done ? (
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary">
                  <Check className="h-3.5 w-3.5 text-primary-foreground" />
                </div>
              ) : (
                <Circle className="h-6 w-6 text-primary/30" />
              )}
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 ${step.done ? "text-muted-foreground" : "text-primary/50"}`} />
                <span className={step.done ? "line-through text-muted-foreground" : ""}>{step.label}</span>
              </div>
            </Link>
          );
        })}
      </CardContent>
    </Card>
  );
}
