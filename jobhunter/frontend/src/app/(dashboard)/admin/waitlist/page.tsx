"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import {
  useWaitlist,
  useInviteWaitlistEntry,
  useInviteWaitlistBatch,
} from "@/lib/hooks/use-admin";
import { PageHeader } from "@/components/shared/page-header";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
import { AlertCircle, Mail, Users } from "lucide-react";
import type { WaitlistStatus, WaitlistEntry } from "@/lib/types";

type FilterStatus = WaitlistStatus | "all";

const STATUS_LABELS: Record<WaitlistStatus, string> = {
  pending: "Pending",
  invited: "Invited",
  invite_failed: "Failed",
  registered: "Registered",
};

const STATUS_VARIANTS: Record<
  WaitlistStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "secondary",
  invited: "default",
  invite_failed: "destructive",
  registered: "outline",
};

function StatusBadge({ status }: { status: WaitlistStatus }) {
  return (
    <Badge variant={STATUS_VARIANTS[status]}>{STATUS_LABELS[status]}</Badge>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function InviteButton({
  entry,
  isPending,
  onInvite,
}: {
  entry: WaitlistEntry;
  isPending: boolean;
  onInvite: (id: string) => void;
}) {
  const isDisabled =
    entry.status === "invited" ||
    entry.status === "registered" ||
    isPending;

  const label =
    entry.status === "invite_failed"
      ? "Retry"
      : entry.status === "invited"
        ? "Invited"
        : entry.status === "registered"
          ? "Registered"
          : "Invite";

  return (
    <Button
      size="sm"
      variant={entry.status === "invite_failed" ? "destructive" : "default"}
      disabled={isDisabled}
      onClick={() => onInvite(entry.id)}
    >
      {isPending ? "Sending..." : label}
    </Button>
  );
}

export default function WaitlistPage() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [filter, setFilter] = useState<FilterStatus>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const waitlistQuery = useWaitlist(
    filter === "all" ? undefined : { status: filter }
  );

  const inviteSingle = useInviteWaitlistEntry();
  const inviteBatch = useInviteWaitlistBatch();

  if (!authLoading && user && !user.is_admin) {
    router.push("/dashboard");
    return null;
  }

  const entries: WaitlistEntry[] = waitlistQuery.data?.entries ?? [];
  const statusCounts = waitlistQuery.data?.status_counts;
  const quotaRemaining = waitlistQuery.data?.quota_remaining ?? 0;

  const allSelectableIds = entries
    .filter((e) => e.status === "pending" || e.status === "invite_failed")
    .map((e) => e.id);

  const allSelected =
    allSelectableIds.length > 0 &&
    allSelectableIds.every((id) => selected.has(id));

  const someSelected = selected.size > 0;

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(allSelectableIds));
    }
  }

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function handleInviteSingle(id: string) {
    try {
      await inviteSingle.mutateAsync(id);
      toast.success("Invite sent");
    } catch {
      toast.error("Failed to send invite");
    }
  }

  async function handleInviteBatch() {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    try {
      const result = await inviteBatch.mutateAsync(ids);
      setSelected(new Set());
      toast.success(
        `${result.invited} invite${result.invited !== 1 ? "s" : ""} sent${result.failed > 0 ? `, ${result.failed} failed` : ""}`
      );
    } catch {
      toast.error("Batch invite failed");
    }
  }

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <PageHeader
          title="Waitlist Management"
          description="Review and invite candidates from the waitlist"
        />

        {/* Status Count Cards */}
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
          {(
            [
              "pending",
              "invited",
              "invite_failed",
              "registered",
            ] as WaitlistStatus[]
          ).map((s) => (
            <Card
              key={s}
              className="cursor-pointer hover:ring-1 hover:ring-primary/40 transition-all"
              onClick={() => setFilter(s)}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {STATUS_LABELS[s]}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <span className="text-2xl font-bold">
                  {statusCounts ? (statusCounts[s] ?? 0) : "—"}
                </span>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Quota and toolbar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Mail className="h-4 w-4" />
            <span>
              Daily quota remaining:{" "}
              <span className="font-medium text-foreground">
                {quotaRemaining}
              </span>
            </span>
          </div>

          <div className="flex items-center gap-3">
            {someSelected && (
              <Button
                size="sm"
                onClick={handleInviteBatch}
                disabled={inviteBatch.isPending}
              >
                <Users className="mr-2 h-4 w-4" />
                {inviteBatch.isPending
                  ? "Sending..."
                  : `Invite Selected (${selected.size})`}
              </Button>
            )}

            <Select
              value={filter}
              onValueChange={(v) => {
                setFilter(v as FilterStatus);
                setSelected(new Set());
              }}
            >
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="invited">Invited</SelectItem>
                <SelectItem value="invite_failed">Failed</SelectItem>
                <SelectItem value="registered">Registered</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Table */}
        {waitlistQuery.isLoading || authLoading ? (
          <TableSkeleton rows={8} />
        ) : entries.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground">
            No waitlist entries{filter !== "all" ? ` with status "${STATUS_LABELS[filter as WaitlistStatus]}"` : ""}.
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      checked={allSelected}
                      onCheckedChange={toggleAll}
                      aria-label="Select all"
                    />
                  </TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Signed Up</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry) => {
                  const isSelectable =
                    entry.status === "pending" ||
                    entry.status === "invite_failed";
                  return (
                    <TableRow key={entry.id}>
                      <TableCell>
                        <Checkbox
                          checked={selected.has(entry.id)}
                          onCheckedChange={() => toggleOne(entry.id)}
                          disabled={!isSelectable}
                          aria-label={`Select ${entry.email}`}
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        {entry.email}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {entry.source ?? "—"}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={entry.status} />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                        {formatDate(entry.created_at)}
                      </TableCell>
                      <TableCell>
                        {entry.error_message ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="inline-flex cursor-help items-center gap-1 text-destructive text-sm">
                                <AlertCircle className="h-4 w-4 shrink-0" />
                                Error
                              </span>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-xs">
                              {entry.error_message}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <InviteButton
                          entry={entry}
                          isPending={
                            inviteSingle.isPending &&
                            inviteSingle.variables === entry.id
                          }
                          onInvite={handleInviteSingle}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
