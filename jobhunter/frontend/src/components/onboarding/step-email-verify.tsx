"use client";

import { useState } from "react";
import { useAuth } from "@/providers/auth-provider";
import * as authApi from "@/lib/api/auth";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MailCheck, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export function StepEmailVerify() {
  const { user, refreshUser } = useAuth();
  const [isResending, setIsResending] = useState(false);
  const [cooldown, setCooldown] = useState(false);

  const isVerified = !!user?.email_verified;

  const handleResend = async () => {
    setIsResending(true);
    try {
      await authApi.resendVerification();
      toast.success("Verification email sent!");
      setCooldown(true);
      setTimeout(() => setCooldown(false), 60000); // 60s cooldown
    } catch {
      toast.error("Failed to resend. Please try again in a few minutes.");
    } finally {
      setIsResending(false);
    }
  };

  const handleCheckStatus = async () => {
    await refreshUser();
    if (!user?.email_verified) {
      toast.info("Email not verified yet. Check your inbox and click the verification link.");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Verify your email</h2>
        <p className="mt-1 text-muted-foreground">
          This ensures we can send you outreach updates and important notifications.
        </p>
      </div>

      {isVerified ? (
        <Card className="border-green-500/30 bg-green-500/5">
          <CardContent className="flex items-center gap-3 py-5">
            <CheckCircle2 className="h-6 w-6 text-green-600" />
            <div>
              <p className="font-medium text-green-700 dark:text-green-400">Email verified!</p>
              <p className="text-sm text-muted-foreground">{user?.email}</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="flex items-start gap-4 py-5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                <MailCheck className="h-6 w-6 text-primary" />
              </div>
              <div className="space-y-2">
                <p className="font-medium">Check your inbox</p>
                <p className="text-sm text-muted-foreground">
                  We sent a verification link to <strong>{user?.email}</strong>.
                  Click the link in the email to verify your account.
                </p>
                <div className="flex items-center gap-3 pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleResend}
                    disabled={isResending || cooldown}
                  >
                    {isResending ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    {cooldown ? "Sent — check inbox" : "Resend email"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleCheckStatus}>
                    I&apos;ve verified
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <p className="text-xs text-muted-foreground text-center">
            You can continue without verifying, but some features (like email outreach) work best with a verified account.
          </p>
        </>
      )}
    </div>
  );
}
