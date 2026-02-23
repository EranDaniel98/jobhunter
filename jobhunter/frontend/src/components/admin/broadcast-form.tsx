"use client";

import { useState } from "react";
import { useBroadcast } from "@/lib/hooks/use-admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Send, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export function BroadcastForm() {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [result, setResult] = useState<{ sent_count: number; skipped_count: number } | null>(null);
  const broadcast = useBroadcast();

  const handleSend = async () => {
    setShowConfirm(false);
    try {
      const res = await broadcast.mutateAsync({ subject, body });
      setResult(res);
      setSubject("");
      setBody("");
      toast.success(`Broadcast sent to ${res.sent_count} users`);
    } catch {
      toast.error("Failed to send broadcast");
    }
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Send Broadcast Email</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="broadcast-subject">Subject</Label>
            <Input
              id="broadcast-subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Platform Update: New Features Available"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="broadcast-body">Message body</Label>
            <Textarea
              id="broadcast-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Write your message here..."
              rows={6}
            />
          </div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Will be sent to all active users who haven&apos;t opted out of emails.
            </p>
            <Button
              onClick={() => setShowConfirm(true)}
              disabled={!subject.trim() || !body.trim() || broadcast.isPending}
            >
              {broadcast.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Send broadcast
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card className="border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <div>
                <p className="font-medium">Broadcast sent successfully</p>
                <p className="text-sm text-muted-foreground">
                  Sent to {result.sent_count} users, {result.skipped_count} skipped (opted out or failed)
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <AlertDialog open={showConfirm} onOpenChange={setShowConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Send broadcast email?</AlertDialogTitle>
            <AlertDialogDescription>
              This will send an email to all active users who have not opted out of
              email notifications. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleSend}>Send</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
