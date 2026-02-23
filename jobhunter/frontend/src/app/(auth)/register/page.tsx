"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { RegisterForm } from "@/components/auth/register-form";
import { useValidateInvite } from "@/lib/hooks/use-invites";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

function RegisterContent() {
  const searchParams = useSearchParams();
  const code = searchParams.get("invite");
  const { data, isLoading, isError } = useValidateInvite(code);

  if (!code) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Invite required</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Registration is invite-only. Ask an existing user for an invite link.
          </p>
          <Button asChild variant="outline" className="w-full">
            <Link href="/login">Back to login</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data?.valid) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Invalid invite</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            This invite link is invalid, expired, or has already been used.
          </p>
          <Button asChild variant="outline" className="w-full">
            <Link href="/login">Back to login</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return <RegisterForm inviteCode={code} invitedByName={data.invited_by_name} />;
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <Card>
          <CardContent className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      }
    >
      <RegisterContent />
    </Suspense>
  );
}
