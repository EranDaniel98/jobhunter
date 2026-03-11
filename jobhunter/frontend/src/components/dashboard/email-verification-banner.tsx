"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Mail, Loader2 } from "lucide-react";
import { resendVerification } from "@/lib/api/auth";
import { toast } from "sonner";
import { toastError } from "@/lib/api/error-utils";

const COOLDOWN_KEY = "verify_resend_until";
const COOLDOWN_SECONDS = 300; // 5 minutes

export function EmailVerificationBanner() {
  const [loading, setLoading] = useState(false);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);

  // Restore cooldown from localStorage
  useEffect(() => {
    const until = localStorage.getItem(COOLDOWN_KEY);
    if (until) {
      const remaining = Math.max(0, Math.floor((Number(until) - Date.now()) / 1000));
      setCooldownRemaining(remaining);
    }
  }, []);

  // Countdown timer
  useEffect(() => {
    if (cooldownRemaining <= 0) return;
    const timer = setInterval(() => {
      setCooldownRemaining((prev) => {
        if (prev <= 1) {
          localStorage.removeItem(COOLDOWN_KEY);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldownRemaining]);

  const handleResend = useCallback(async () => {
    setLoading(true);
    try {
      await resendVerification();
      toast.success("Verification email sent — check your inbox");
      const until = Date.now() + COOLDOWN_SECONDS * 1000;
      localStorage.setItem(COOLDOWN_KEY, String(until));
      setCooldownRemaining(COOLDOWN_SECONDS);
    } catch (err) {
      toastError(err, "Failed to send verification email");
    } finally {
      setLoading(false);
    }
  }, []);

  const minutes = Math.floor(cooldownRemaining / 60);
  const seconds = cooldownRemaining % 60;

  return (
    <Card className="border-chart-3/30 bg-accent">
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Mail className="h-5 w-5 text-chart-3 shrink-0" />
          <p className="text-sm text-accent-foreground">
            Please verify your email address. Check your inbox for the verification link.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={handleResend}
          disabled={loading || cooldownRemaining > 0}
        >
          {loading && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
          {cooldownRemaining > 0
            ? `Resend in ${minutes}:${String(seconds).padStart(2, "0")}`
            : "Didn't receive an email?"}
        </Button>
      </CardContent>
    </Card>
  );
}
