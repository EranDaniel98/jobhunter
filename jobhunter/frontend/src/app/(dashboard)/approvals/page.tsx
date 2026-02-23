"use client";

import { useState } from "react";
import { useApprovals, useApproveAction, useRejectAction } from "@/lib/hooks/use-approvals";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { StatusBadge } from "@/components/shared/status-badge";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { toast } from "sonner";
import {
  ClipboardCheck,
  Check,
  X,
  Mail,
  Linkedin,
  Loader2,
} from "lucide-react";
import type { PendingAction } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

function detectDir(text: string): "rtl" | "ltr" {
  const rtlChars = /[\u0590-\u05FF\u0600-\u06FF\uFE70-\uFEFF]/;
  return rtlChars.test(text) ? "rtl" : "ltr";
}

const ACTION_TYPE_LABELS: Record<string, string> = {
  send_email: "Send Email",
  send_followup: "Send Follow-up",
  send_linkedin: "Send LinkedIn",
};

export default function ApprovalsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [selectedAction, setSelectedAction] = useState<PendingAction | null>(null);

  const params = {
    status: statusFilter === "all" ? undefined : statusFilter,
  };
  const { data, isLoading } = useApprovals(params);
  const approveMutation = useApproveAction();
  const rejectMutation = useRejectAction();

  function handleApprove(id: string) {
    approveMutation.mutate(id, {
      onSuccess: () => {
        toast.success("Action approved — message sent");
        setSelectedAction(null);
      },
      onError: () => toast.error("Failed to approve"),
    });
  }

  function handleReject(id: string) {
    rejectMutation.mutate(id, {
      onSuccess: () => {
        toast.success("Action rejected");
        setSelectedAction(null);
      },
      onError: () => toast.error("Failed to reject"),
    });
  }

  const actions = data?.actions || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Approvals"
        description="Review and approve outreach messages before they are sent"
      />

      <Tabs value={statusFilter} onValueChange={setStatusFilter}>
        <TabsList>
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="rejected">Rejected</TabsTrigger>
          <TabsTrigger value="all">All</TabsTrigger>
        </TabsList>
      </Tabs>

      {isLoading && <TableSkeleton />}

      {!isLoading && actions.length === 0 && (
        <EmptyState
          icon={ClipboardCheck}
          title="No actions to review"
          description={
            statusFilter === "pending"
              ? "All caught up! No pending approvals."
              : "No actions match this filter."
          }
        />
      )}

      {!isLoading && actions.length > 0 && (
        <div className="grid gap-3">
          {actions.map((action) => (
            <Card
              key={action.id}
              className="cursor-pointer transition-colors hover:bg-muted/50"
              onClick={() => setSelectedAction(action)}
            >
              <CardContent className="flex items-center gap-4 py-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted">
                  {action.channel === "linkedin" ? (
                    <Linkedin className="h-4 w-4" />
                  ) : (
                    <Mail className="h-4 w-4" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">
                      {action.contact_name || "Unknown contact"}
                    </span>
                    {action.company_name && (
                      <span className="text-xs text-muted-foreground">
                        at {action.company_name}
                      </span>
                    )}
                    <Badge variant="secondary" className="text-xs">
                      {ACTION_TYPE_LABELS[action.action_type] || action.action_type}
                    </Badge>
                    <StatusBadge type="message" status={action.status} />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {action.message_subject || "(No subject)"}
                  </p>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  {action.status === "pending" && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-green-600"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleApprove(action.id);
                        }}
                        disabled={approveMutation.isPending}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-red-600"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleReject(action.id);
                        }}
                        disabled={rejectMutation.isPending}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {formatDateTime(action.created_at)}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Action detail sheet */}
      <Sheet
        open={!!selectedAction}
        onOpenChange={(open) => !open && setSelectedAction(null)}
      >
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          {selectedAction && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  <ClipboardCheck className="h-4 w-4" />
                  Action Details
                </SheetTitle>
              </SheetHeader>
              <div className="mt-6 space-y-4">
                <div className="flex items-center gap-2">
                  <StatusBadge type="message" status={selectedAction.status} />
                  <Badge variant="secondary">
                    {ACTION_TYPE_LABELS[selectedAction.action_type] || selectedAction.action_type}
                  </Badge>
                  {selectedAction.message_type && (
                    <Badge variant="outline">{selectedAction.message_type}</Badge>
                  )}
                </div>

                {selectedAction.contact_name && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Contact</p>
                    <p className="text-sm">
                      {selectedAction.contact_name}
                      {selectedAction.company_name && (
                        <span className="text-muted-foreground"> at {selectedAction.company_name}</span>
                      )}
                    </p>
                  </div>
                )}

                {selectedAction.ai_reasoning && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">AI Reasoning</p>
                    <p className="text-sm text-muted-foreground italic">
                      {selectedAction.ai_reasoning}
                    </p>
                  </div>
                )}

                {selectedAction.message_subject && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Subject</p>
                    <p
                      className="text-sm"
                      dir={detectDir(selectedAction.message_subject)}
                    >
                      {selectedAction.message_subject}
                    </p>
                  </div>
                )}

                {selectedAction.message_body && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Body</p>
                    <div
                      className="whitespace-pre-wrap rounded-md bg-muted p-3 text-sm"
                      dir={detectDir(selectedAction.message_body)}
                    >
                      {selectedAction.message_body}
                    </div>
                  </div>
                )}

                <div className="space-y-1 text-xs text-muted-foreground">
                  <p>Created: {formatDateTime(selectedAction.created_at)}</p>
                  {selectedAction.reviewed_at && (
                    <p>Reviewed: {formatDateTime(selectedAction.reviewed_at)}</p>
                  )}
                </div>

                {selectedAction.status === "pending" && (
                  <div className="flex gap-2 pt-2">
                    <Button
                      onClick={() => handleApprove(selectedAction.id)}
                      disabled={approveMutation.isPending}
                    >
                      {approveMutation.isPending && (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      )}
                      <Check className="mr-1 h-4 w-4" />
                      Approve & Send
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => handleReject(selectedAction.id)}
                      disabled={rejectMutation.isPending}
                    >
                      {rejectMutation.isPending && (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      )}
                      <X className="mr-1 h-4 w-4" />
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
