"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { Loader2, Eye, EyeOff, Check, X } from "lucide-react";

function stripHtml(value: string): string {
  return value.replace(/<[^>]*>/g, "");
}

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

const passwordRequirements = [
  { label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { label: "At least one uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { label: "At least one lowercase letter", test: (p: string) => /[a-z]/.test(p) },
  { label: "At least one number", test: (p: string) => /\d/.test(p) },
];

function getStrengthColor(count: number): string {
  if (count <= 1) return "bg-destructive";
  if (count === 2) return "bg-chart-5";
  if (count === 3) return "bg-chart-3";
  return "bg-primary";
}

interface RegisterFormProps {
  inviteCode: string;
  invitedByName?: string | null;
}

export function RegisterForm({ inviteCode, invitedByName }: RegisterFormProps) {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);

  const trimmedName = stripHtml(fullName).trim();
  const trimmedEmail = email.trim().toLowerCase();
  const metRequirements = passwordRequirements.filter((r) => r.test(password));
  const allPasswordRequirementsMet = metRequirements.length === passwordRequirements.length;
  const passwordsMatch = password === confirmPassword;

  const nameError = touched.fullName && !trimmedName ? "Name is required" : null;
  const emailError =
    touched.email && !trimmedEmail
      ? "Email is required"
      : touched.email && !isValidEmail(trimmedEmail)
        ? "Enter a valid email address"
        : null;
  const confirmError =
    touched.confirmPassword && confirmPassword && !passwordsMatch
      ? "Passwords do not match"
      : null;

  function markTouched(field: string) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched({ fullName: true, email: true, password: true, confirmPassword: true });

    if (!trimmedName || !isValidEmail(trimmedEmail) || !allPasswordRequirementsMet || !passwordsMatch) {
      return;
    }

    setLoading(true);
    try {
      await register(trimmedEmail, password, trimmedName, inviteCode, {
        email_notifications: emailNotifications,
      });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Registration failed";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create account</CardTitle>
        {invitedByName && (
          <CardDescription>Invited by {invitedByName}</CardDescription>
        )}
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          {/* Full Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Full name</Label>
            <Input
              id="name"
              placeholder="John Doe"
              value={fullName}
              onChange={(e) => setFullName(stripHtml(e.target.value))}
              onBlur={() => markTouched("fullName")}
              required
              aria-invalid={!!nameError}
              aria-describedby={nameError ? "name-error" : undefined}
            />
            {nameError && <p id="name-error" className="text-sm text-destructive">{nameError}</p>}
          </div>

          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => markTouched("email")}
              required
              aria-invalid={!!emailError}
              aria-describedby={emailError ? "email-error" : undefined}
            />
            {emailError && <p id="email-error" className="text-sm text-destructive">{emailError}</p>}
          </div>

          {/* Password */}
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onBlur={() => markTouched("password")}
                required
                className="pr-10"
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>

            {/* Password Strength */}
            {password && (
              <div className="space-y-2">
                <div className="flex gap-1">
                  {passwordRequirements.map((_, i) => (
                    <div
                      key={i}
                      className={`h-1.5 flex-1 rounded-full transition-colors ${
                        i < metRequirements.length
                          ? getStrengthColor(metRequirements.length)
                          : "bg-muted"
                      }`}
                    />
                  ))}
                </div>
                <ul className="space-y-1">
                  {passwordRequirements.map((req) => {
                    const met = req.test(password);
                    return (
                      <li key={req.label} className="flex items-center gap-2 text-xs">
                        {met ? (
                          <Check className="h-3 w-3 text-primary" />
                        ) : (
                          <X className="h-3 w-3 text-muted-foreground" />
                        )}
                        <span className={met ? "text-primary" : "text-muted-foreground"}>
                          {req.label}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>

          {/* Confirm Password */}
          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm password</Label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showConfirmPassword ? "text" : "password"}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                onBlur={() => markTouched("confirmPassword")}
                required
                className="pr-10"
                aria-invalid={!!confirmError}
                aria-describedby={confirmError ? "confirm-error" : undefined}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                aria-label={showConfirmPassword ? "Hide password" : "Show password"}
              >
                {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {confirmError && <p id="confirm-error" className="text-sm text-destructive">{confirmError}</p>}
          </div>

          {/* Notification Opt-in */}
          <div className="flex items-start gap-2">
            <Checkbox
              id="notifications"
              checked={emailNotifications}
              onCheckedChange={(checked) => setEmailNotifications(checked === true)}
            />
            <Label htmlFor="notifications" className="text-sm font-normal leading-snug cursor-pointer">
              Email me about follow-up reminders and outreach updates
            </Label>
          </div>
          <p className="text-xs text-muted-foreground">
            By creating an account, you agree to our{" "}
            <a href="/terms" target="_blank" className="underline underline-offset-4 hover:text-foreground">
              Terms of Service
            </a>{" "}
            and{" "}
            <a href="/privacy" target="_blank" className="underline underline-offset-4 hover:text-foreground">
              Privacy Policy
            </a>
            .
          </p>
        </CardContent>
        <CardFooter className="flex flex-col gap-3">
          <Button type="submit" className="w-full" disabled={loading}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create account
          </Button>
          <p className="text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="text-primary underline-offset-4 hover:underline">
              Sign in
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
