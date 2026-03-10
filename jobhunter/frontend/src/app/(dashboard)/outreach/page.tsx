"use client";

import { useState } from "react";
import Link from "next/link";
import {
  useMessages,
  useEditMessage,
  useSendMessage,
  useDraftFollowup,
  useMarkReplied,
  useDeleteMessage,
} from "@/lib/hooks/use-outreach";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { StatusBadge } from "@/components/shared/status-badge";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { QueryError } from "@/components/shared/query-error";
import type { OutreachMessageResponse } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { toastError } from "@/lib/api/error-utils";
import {
  Mail,
  Linkedin,
  Loader2,
  Send,
  Reply,
  Edit2,
  Trash2,
  Paperclip,
  ArrowLeft,
  Search,
  CheckCircle2,
  Circle,
  Building2,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function detectDir(text: string): "rtl" | "ltr" {
  const rtlChars = /[\u0590-\u05FF\u0600-\u06FF\uFE70-\uFEFF]/;
  return rtlChars.test(text) ? "rtl" : "ltr";
}

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function avatarColor(id: string): string {
  const colors = [
    "bg-red-500",
    "bg-blue-500",
    "bg-green-500",
    "bg-purple-500",
    "bg-amber-500",
    "bg-teal-500",
    "bg-pink-500",
    "bg-indigo-500",
  ];
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) | 0;
  return colors[Math.abs(hash) % colors.length];
}

function statusDotColor(status: string): string {
  switch (status) {
    case "replied":
      return "bg-green-500";
    case "delivered":
      return "bg-blue-500";
    case "opened":
      return "bg-amber-500";
    case "sent":
      return "bg-indigo-500";
    case "bounced":
      return "bg-red-500";
    default:
      return "bg-gray-400";
  }
}

function getInitials(msg: OutreachMessageResponse): string {
  const name = msg.contact_name;
  if (name) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    if (parts[0].length >= 2) return parts[0].slice(0, 2).toUpperCase();
    return parts[0][0].toUpperCase();
  }
  return msg.channel === "linkedin" ? "LI" : "ML";
}

function getContactName(msg: OutreachMessageResponse): string | null {
  return msg.contact_name || null;
}

function getCompanyName(msg: OutreachMessageResponse): string | null {
  return msg.company_name || null;
}

/* Timeline status steps in order */
const TIMELINE_STEPS = [
  { key: "draft", label: "Draft", dateField: null },
  { key: "sent", label: "Sent", dateField: "sent_at" as const },
  { key: "delivered", label: "Delivered", dateField: null },
  { key: "opened", label: "Opened", dateField: "opened_at" as const },
  { key: "replied", label: "Replied", dateField: "replied_at" as const },
] as const;

const STATUS_ORDER: Record<string, number> = {
  draft: 0,
  sent: 1,
  delivered: 2,
  opened: 3,
  replied: 4,
  bounced: -1,
};

/* ------------------------------------------------------------------ */
/*  Page Component                                                    */
/* ------------------------------------------------------------------ */

export default function OutreachPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedMessage, setSelectedMessage] =
    useState<OutreachMessageResponse | null>(null);
  const [editing, setEditing] = useState(false);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [sendConfirmId, setSendConfirmId] = useState<string | null>(null);
  const [attachResume, setAttachResume] = useState(true);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Bulk select — only drafts are selectable
  const [bulkMode, setBulkMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const params = {
    status: statusFilter === "all" ? undefined : statusFilter,
    channel: channelFilter === "all" ? undefined : channelFilter,
  };
  const { data: messages, isLoading, isError, refetch } = useMessages(params);
  const editMutation = useEditMessage();
  const sendMutation = useSendMessage();
  const followupMutation = useDraftFollowup();
  const markRepliedMutation = useMarkReplied();
  const deleteMutation = useDeleteMessage();

  // Client-side search filter
  const filteredMessages = (messages || []).filter(
    (msg) =>
      !searchQuery ||
      (msg.subject || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      msg.body.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  function openMessage(msg: OutreachMessageResponse) {
    if (bulkMode) {
      if (msg.status === "draft") toggleSelect(msg.id);
      return;
    }
    setSelectedMessage(msg);
    setEditSubject(msg.subject || "");
    setEditBody(msg.body);
    setEditing(false);
  }

  function handleSaveEdit() {
    if (!selectedMessage) return;
    editMutation.mutate(
      { id: selectedMessage.id, subject: editSubject, body: editBody },
      {
        onSuccess: (updated) => {
          setSelectedMessage(updated);
          setEditing(false);
          toast.success("Message updated");
        },
        onError: (err: unknown) => toastError(err, "Failed to save message"),
      },
    );
  }

  function handleDelete() {
    if (!deleteConfirmId) return;
    deleteMutation.mutate(deleteConfirmId, {
      onSuccess: () => {
        setSelectedMessage(null);
        setDeleteConfirmId(null);
        toast.success("Message deleted");
      },
      onError: (err: unknown) => {
        toastError(err, "Failed to delete message");
        setDeleteConfirmId(null);
      },
    });
  }

  function handleSend() {
    if (!sendConfirmId) return;
    sendMutation.mutate(
      { id: sendConfirmId, attachResume },
      {
        onSuccess: (updated) => {
          setSelectedMessage(updated);
          setSendConfirmId(null);
          setAttachResume(true);
          toast.success("Message sent!");
        },
        onError: (err: unknown) => {
          toastError(err, "Send failed");
          setSendConfirmId(null);
        },
      },
    );
  }

  // Bulk actions — only drafts
  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleBulkSendDrafts() {
    const drafts = (messages || []).filter(
      (m) => selectedIds.has(m.id) && m.status === "draft",
    );
    if (drafts.length === 0) {
      toast.info("No drafts selected");
      return;
    }
    let completed = 0;
    drafts.forEach((d) => {
      sendMutation.mutate(
        { id: d.id, attachResume: true },
        {
          onSuccess: () => {
            completed++;
            if (completed === drafts.length) {
              toast.success(`Sent ${completed} message(s)`);
              setSelectedIds(new Set());
              setBulkMode(false);
            }
          },
          onError: (err: unknown) => toastError(err, `Failed to send ${d.subject}`),
        },
      );
    });
  }

  function handleBulkDelete() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    let completed = 0;
    ids.forEach((id) => {
      deleteMutation.mutate(id, {
        onSuccess: () => {
          completed++;
          if (completed === ids.length) {
            toast.success(`Deleted ${completed} message(s)`);
            setSelectedIds(new Set());
            setBulkMode(false);
            setSelectedMessage(null);
          }
        },
        onError: (err: unknown) => toastError(err, "Failed to delete"),
      });
    });
  }

  /* ---------------------------------------------------------------- */
  /*  Render                                                          */
  /* ---------------------------------------------------------------- */

  const hasMessages = !isLoading && !isError && messages && messages.length > 0;
  const isEmpty = !isLoading && !isError && (!messages || messages.length === 0);

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 5rem)" }}>
      <PageHeader title="Outreach" description="Manage your outreach messages" />

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="sent">Sent</SelectItem>
            <SelectItem value="delivered">Delivered</SelectItem>
            <SelectItem value="opened">Opened</SelectItem>
            <SelectItem value="replied">Replied</SelectItem>
            <SelectItem value="bounced">Bounced</SelectItem>
          </SelectContent>
        </Select>
        <Select value={channelFilter} onValueChange={setChannelFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Channel" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All channels</SelectItem>
            <SelectItem value="email">Email</SelectItem>
            <SelectItem value="linkedin">LinkedIn</SelectItem>
          </SelectContent>
        </Select>

        <div className="ml-auto">
          <Button
            size="sm"
            variant={bulkMode ? "default" : "outline"}
            onClick={() => {
              setBulkMode(!bulkMode);
              setSelectedIds(new Set());
            }}
          >
            {bulkMode ? "Cancel Select" : "Select Drafts"}
          </Button>
        </div>
      </div>

      {/* Main split pane */}
      <div className="flex flex-1 min-h-0 min-w-0 gap-0 rounded-2xl border bg-card overflow-hidden shadow-sm">
        {/* ============ Left: Message list ============ */}
        <div
          className={cn(
            "border-r flex flex-col bg-muted/30",
            selectedMessage
              ? "hidden md:flex md:w-[340px] lg:w-[400px] shrink-0"
              : "w-full",
          )}
        >
          {/* Search box */}
          <div className="p-3 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search messages..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 h-9 bg-background"
              />
            </div>
          </div>

          {/* Message rows */}
          <div className="flex-1 overflow-y-auto">
            {isLoading && (
              <div className="p-4">
                <TableSkeleton />
              </div>
            )}

            {!isLoading && isError && (
              <div className="p-4">
                <QueryError
                  message="Could not load messages."
                  onRetry={() => refetch()}
                />
              </div>
            )}

            {isEmpty && (
              <div className="flex flex-col items-center justify-center h-full px-6 py-16 text-center">
                <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/10">
                  <Mail className="h-10 w-10 text-primary/60" />
                </div>
                <h3 className="mb-1 text-xl font-bold">
                  Your first outreach starts at Companies
                </h3>
                <p className="mb-4 max-w-sm text-sm text-muted-foreground">
                  Find a company, discover contacts, and draft your first
                  personalized email.
                </p>
                <Link href="/dashboard">
                  <Button>
                    <Building2 className="mr-2 h-4 w-4" />
                    Go to Companies
                  </Button>
                </Link>
              </div>
            )}

            {hasMessages &&
              filteredMessages.map((msg) => {
                const isSelected = selectedMessage?.id === msg.id;
                const initials = getInitials(msg);
                const ts = msg.sent_at || msg.opened_at || msg.replied_at || null;
                const isDraft = msg.status === "draft";

                return (
                  // Use div instead of button to avoid nested button (Checkbox is a button)
                  <div
                    key={msg.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => openMessage(msg)}
                    onKeyDown={(e) => e.key === "Enter" && openMessage(msg)}
                    className={cn(
                      "w-full text-left px-3 py-3 border-b transition-colors hover:bg-muted/60 flex items-start gap-3 group cursor-pointer",
                      isSelected &&
                        !bulkMode &&
                        "bg-primary/5 border-l-2 border-l-primary",
                      bulkMode && !isDraft && "opacity-50 cursor-not-allowed",
                    )}
                  >
                    {/* Bulk checkbox — only drafts */}
                    {bulkMode && isDraft && (
                      <div
                        className="pt-1 shrink-0"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Checkbox
                          checked={selectedIds.has(msg.id)}
                          onCheckedChange={() => toggleSelect(msg.id)}
                        />
                      </div>
                    )}

                    {/* Status dot */}
                    <div className="pt-2 shrink-0">
                      <div
                        className={cn(
                          "h-2.5 w-2.5 rounded-full",
                          statusDotColor(msg.status),
                        )}
                        title={msg.status}
                      />
                    </div>

                    {/* Avatar */}
                    <div
                      className={cn(
                        "h-9 w-9 rounded-full shrink-0 flex items-center justify-center text-white text-xs font-semibold",
                        avatarColor(msg.contact_id),
                      )}
                    >
                      {initials}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className="text-sm font-semibold truncate"
                          dir={detectDir(msg.subject || "")}
                        >
                          {msg.subject || "(No subject)"}
                        </span>
                        <span className="text-[11px] text-muted-foreground shrink-0 whitespace-nowrap">
                          {ts ? relativeTime(ts) : "Draft"}
                        </span>
                      </div>
                      <p
                        className="text-xs text-muted-foreground mt-0.5 truncate"
                        dir={detectDir(msg.body)}
                      >
                        {msg.body.slice(0, 80)}
                      </p>
                    </div>
                  </div>
                );
              })}

            {hasMessages && filteredMessages.length === 0 && searchQuery && (
              <div className="p-6 text-center text-sm text-muted-foreground">
                No messages match &ldquo;{searchQuery}&rdquo;
              </div>
            )}
          </div>

          {/* Bulk action bar */}
          {bulkMode && selectedIds.size > 0 && (
            <div className="border-t bg-background p-3 flex items-center justify-between gap-2">
              <span className="text-sm text-muted-foreground">
                {selectedIds.size} draft{selectedIds.size > 1 ? "s" : ""} selected
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleBulkSendDrafts}
                  disabled={sendMutation.isPending}
                >
                  <Send className="mr-1 h-3.5 w-3.5" />
                  Send All
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={handleBulkDelete}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="mr-1 h-3.5 w-3.5" />
                  Delete
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* ============ Right: Detail panel ============ */}
        <div
          className={cn(
            "flex-1 flex flex-col min-w-0 bg-background",
            !selectedMessage && "hidden md:flex",
          )}
        >
          {selectedMessage ? (
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Mobile back button */}
              <div className="md:hidden border-b px-4 py-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedMessage(null)}
                >
                  <ArrowLeft className="mr-1 h-4 w-4" /> Back
                </Button>
              </div>

              {/* Header bar */}
              <div className="border-b px-6 py-4 bg-muted/20">
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={cn(
                      "h-10 w-10 rounded-full shrink-0 flex items-center justify-center text-white text-sm font-semibold",
                      avatarColor(selectedMessage.contact_id),
                    )}
                  >
                    {getInitials(selectedMessage)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {getContactName(selectedMessage) && (
                        <span className="font-semibold text-sm">
                          {getContactName(selectedMessage)}
                        </span>
                      )}
                      {getCompanyName(selectedMessage) && (
                        <span className="text-sm text-muted-foreground">
                          at {getCompanyName(selectedMessage)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge
                        variant="outline"
                        className="text-[10px] px-1.5 py-0 gap-1"
                      >
                        {selectedMessage.channel === "linkedin" ? (
                          <Linkedin className="h-3 w-3" />
                        ) : (
                          <Mail className="h-3 w-3" />
                        )}
                        {selectedMessage.channel}
                      </Badge>
                      <StatusBadge
                        type="message"
                        status={selectedMessage.status}
                      />
                      <Badge
                        variant="secondary"
                        className="text-[10px] px-1.5 py-0"
                      >
                        {selectedMessage.message_type}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Subject line */}
                <h2
                  className="text-lg font-bold"
                  dir={detectDir(selectedMessage.subject || "")}
                >
                  {selectedMessage.subject || "(No subject)"}
                </h2>
              </div>

              {/* Scrollable body area */}
              <div className="flex-1 overflow-y-auto px-6 py-6">
                {editing ? (
                  <div className="space-y-4 max-w-2xl">
                    <div className="space-y-2">
                      <Label>Subject</Label>
                      <Input
                        value={editSubject}
                        onChange={(e) => setEditSubject(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Body</Label>
                      <Textarea
                        value={editBody}
                        onChange={(e) => setEditBody(e.target.value)}
                        rows={16}
                        className="font-mono text-sm"
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button
                        onClick={handleSaveEdit}
                        disabled={editMutation.isPending}
                      >
                        {editMutation.isPending && (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        Save
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setEditing(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-8">
                    {/* Message body card */}
                    <div className="rounded-xl border bg-white dark:bg-card p-8 shadow-sm max-w-2xl">
                      <div
                        className="whitespace-pre-wrap text-sm leading-relaxed"
                        dir={detectDir(selectedMessage.body)}
                      >
                        {selectedMessage.body}
                      </div>
                    </div>

                    {/* Visual timeline */}
                    <div className="max-w-sm">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
                        Timeline
                      </h4>
                      {selectedMessage.status === "bounced" ? (
                        <div className="flex items-center gap-3 text-sm text-red-500">
                          <div className="h-3 w-3 rounded-full bg-red-500" />
                          <span className="font-medium">Bounced</span>
                        </div>
                      ) : (
                        <div className="relative pl-4">
                          {TIMELINE_STEPS.map((step, idx) => {
                            const currentOrder =
                              STATUS_ORDER[selectedMessage.status] ?? 0;
                            const stepOrder = STATUS_ORDER[step.key] ?? 0;
                            const reached = stepOrder <= currentOrder;
                            const dateVal = step.dateField
                              ? (selectedMessage[
                                  step.dateField
                                ] as string | null)
                              : null;
                            const isLast = idx === TIMELINE_STEPS.length - 1;

                            return (
                              <div key={step.key} className="relative pb-6 last:pb-0">
                                {/* Vertical line */}
                                {!isLast && (
                                  <div
                                    className={cn(
                                      "absolute left-0 top-3 w-0.5 h-full -translate-x-1/2",
                                      reached
                                        ? "bg-primary/40"
                                        : "bg-muted-foreground/20",
                                    )}
                                  />
                                )}
                                {/* Dot */}
                                <div className="flex items-center gap-3">
                                  <div className="relative z-10 -ml-4">
                                    {reached ? (
                                      <CheckCircle2 className="h-4 w-4 text-primary" />
                                    ) : (
                                      <Circle className="h-4 w-4 text-muted-foreground/30" />
                                    )}
                                  </div>
                                  <span
                                    className={cn(
                                      "text-sm",
                                      reached
                                        ? "font-medium text-foreground"
                                        : "text-muted-foreground/50",
                                    )}
                                  >
                                    {step.label}
                                  </span>
                                  {dateVal && (
                                    <span className="text-xs text-muted-foreground ml-auto">
                                      {formatDateTime(dateVal)}
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Floating action bar at bottom */}
              {!editing && (
                <div className="border-t bg-muted/20 px-6 py-3 flex items-center gap-2">
                  {selectedMessage.status === "draft" && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditing(true)}
                      >
                        <Edit2 className="mr-1 h-3.5 w-3.5" /> Edit
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => setSendConfirmId(selectedMessage.id)}
                        disabled={sendMutation.isPending}
                      >
                        <Send className="mr-1 h-3.5 w-3.5" /> Send
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() =>
                          setDeleteConfirmId(selectedMessage.id)
                        }
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="mr-1 h-3.5 w-3.5" /> Delete
                      </Button>
                    </>
                  )}
                  {["sent", "delivered", "opened"].includes(
                    selectedMessage.status,
                  ) && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          followupMutation.mutate(selectedMessage.id, {
                            onSuccess: () => {
                              toast.success("Follow-up draft created");
                              setSelectedMessage(null);
                            },
                            onError: (err: unknown) =>
                              toastError(err, "Failed to create follow-up"),
                          })
                        }
                        disabled={followupMutation.isPending}
                      >
                        {followupMutation.isPending ? (
                          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Reply className="mr-1 h-3.5 w-3.5" />
                        )}
                        Draft Follow-up
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={markRepliedMutation.isPending}
                        onClick={() =>
                          markRepliedMutation.mutate(selectedMessage.id, {
                            onSuccess: (updated) => {
                              setSelectedMessage(updated);
                              toast.success("Marked as replied");
                            },
                          })
                        }
                      >
                        <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                        Mark Replied
                      </Button>
                    </>
                  )}
                </div>
              )}
            </div>
          ) : (
            /* Empty state when no message selected (desktop) */
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center px-6">
                <div className="mb-4 flex h-16 w-16 mx-auto items-center justify-center rounded-2xl bg-muted/50">
                  <Mail className="h-8 w-8 opacity-30" />
                </div>
                <p className="text-sm font-medium">
                  Select a message to view details
                </p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Choose from the list on the left
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Send confirmation */}
      <AlertDialog
        open={!!sendConfirmId}
        onOpenChange={(open) => {
          if (!open) {
            setSendConfirmId(null);
            setAttachResume(true);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Send message?</AlertDialogTitle>
            <AlertDialogDescription>
              This will send the email to the recipient. This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {selectedMessage?.channel === "email" && (
            <div className="flex items-center gap-2 px-1">
              <Checkbox
                id="attach-resume"
                checked={attachResume}
                onCheckedChange={(checked) => setAttachResume(checked === true)}
              />
              <label
                htmlFor="attach-resume"
                className="flex items-center gap-1.5 text-sm cursor-pointer select-none"
              >
                <Paperclip className="h-3.5 w-3.5" />
                Attach resume
              </label>
            </div>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleSend}
              disabled={sendMutation.isPending}
            >
              {sendMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Send
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete confirmation */}
      <AlertDialog
        open={!!deleteConfirmId}
        onOpenChange={(open) => !open && setDeleteConfirmId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete draft?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this draft message. This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
