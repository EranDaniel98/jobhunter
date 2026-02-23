"use client";

import { useState } from "react";
import { useMessages, useEditMessage, useSendMessage, useDraftFollowup, useMarkReplied, useDeleteMessage } from "@/lib/hooks/use-outreach";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { StatusBadge } from "@/components/shared/status-badge";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import type { OutreachMessageResponse } from "@/lib/types";
import { formatDateTime, truncate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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
import { Mail, Linkedin, Loader2, Send, Reply, Edit2, MessageSquare, Trash2, Paperclip } from "lucide-react";

function detectDir(text: string): "rtl" | "ltr" {
  const rtlChars = /[\u0590-\u05FF\u0600-\u06FF\uFE70-\uFEFF]/;
  return rtlChars.test(text) ? "rtl" : "ltr";
}

export default function OutreachPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [selectedMessage, setSelectedMessage] = useState<OutreachMessageResponse | null>(null);
  const [editing, setEditing] = useState(false);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [sendConfirmId, setSendConfirmId] = useState<string | null>(null);
  const [attachResume, setAttachResume] = useState(true);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const params = {
    status: statusFilter === "all" ? undefined : statusFilter,
    channel: channelFilter === "all" ? undefined : channelFilter,
  };
  const { data: messages, isLoading } = useMessages(params);
  const editMutation = useEditMessage();
  const sendMutation = useSendMessage();
  const followupMutation = useDraftFollowup();
  const markRepliedMutation = useMarkReplied();
  const deleteMutation = useDeleteMessage();

  function openMessage(msg: OutreachMessageResponse) {
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
      }
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
    sendMutation.mutate({ id: sendConfirmId, attachResume }, {
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
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Outreach" description="Manage your outreach messages" />

      <div className="flex flex-wrap gap-3">
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
      </div>

      {isLoading && <TableSkeleton />}

      {!isLoading && (!messages || messages.length === 0) && (
        <EmptyState
          icon={MessageSquare}
          title="No outreach messages yet"
          description="Go to a company to draft your first email."
        />
      )}

      {!isLoading && messages && messages.length > 0 && (
        <div className="grid gap-3">
          {messages.map((msg) => (
            <Card
              key={msg.id}
              className="cursor-pointer transition-colors hover:bg-muted/50"
              onClick={() => openMessage(msg)}
            >
              <CardContent className="flex items-center gap-4 py-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted">
                  {msg.channel === "linkedin" ? (
                    <Linkedin className="h-4 w-4" />
                  ) : (
                    <Mail className="h-4 w-4" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">
                      {msg.subject || "(No subject)"}
                    </span>
                    <StatusBadge type="message" status={msg.status} />
                    <Badge variant="secondary" className="text-xs">
                      {msg.message_type}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1" dir={detectDir(msg.body)}>
                    {truncate(msg.body, 100)}
                  </p>
                </div>
                <div className="shrink-0 text-xs text-muted-foreground">
                  {msg.sent_at ? formatDateTime(msg.sent_at) : "Draft"}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Message detail sheet */}
      <Sheet open={!!selectedMessage} onOpenChange={(open) => !open && setSelectedMessage(null)}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          {selectedMessage && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  {selectedMessage.channel === "linkedin" ? (
                    <Linkedin className="h-4 w-4" />
                  ) : (
                    <Mail className="h-4 w-4" />
                  )}
                  {editing ? "Edit Message" : "Message Details"}
                </SheetTitle>
              </SheetHeader>
              <div className="mt-6 space-y-4">
                <div className="flex items-center gap-2">
                  <StatusBadge type="message" status={selectedMessage.status} />
                  <Badge variant="secondary">{selectedMessage.message_type}</Badge>
                  <Badge variant="outline">{selectedMessage.channel}</Badge>
                </div>

                {editing ? (
                  <div className="space-y-3">
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
                        rows={12}
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button onClick={handleSaveEdit} disabled={editMutation.isPending}>
                        {editMutation.isPending && (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        Save
                      </Button>
                      <Button variant="outline" onClick={() => setEditing(false)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    {selectedMessage.subject && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground">Subject</p>
                        <p className="text-sm" dir={detectDir(selectedMessage.subject || "")}>{selectedMessage.subject}</p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Body</p>
                      <div
                        className="whitespace-pre-wrap rounded-md bg-muted p-3 text-sm"
                        dir={detectDir(selectedMessage.body)}
                      >
                        {selectedMessage.body}
                      </div>
                    </div>

                    {/* Timeline */}
                    <div className="space-y-1 text-xs text-muted-foreground">
                      {selectedMessage.sent_at && (
                        <p>Sent: {formatDateTime(selectedMessage.sent_at)}</p>
                      )}
                      {selectedMessage.opened_at && (
                        <p>Opened: {formatDateTime(selectedMessage.opened_at)}</p>
                      )}
                      {selectedMessage.replied_at && (
                        <p>Replied: {formatDateTime(selectedMessage.replied_at)}</p>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-2 pt-2">
                      {selectedMessage.status === "draft" && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setEditing(true)}
                          >
                            <Edit2 className="mr-1 h-3.5 w-3.5" />
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => setSendConfirmId(selectedMessage.id)}
                          >
                            <Send className="mr-1 h-3.5 w-3.5" />
                            Send
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => setDeleteConfirmId(selectedMessage.id)}
                          >
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            Delete
                          </Button>
                        </>
                      )}
                      {["sent", "delivered", "opened"].includes(selectedMessage.status) && (
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
                                onError: (err: unknown) => toastError(err, "Failed to create follow-up"),
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
                            onClick={() =>
                              markRepliedMutation.mutate(selectedMessage.id, {
                                onSuccess: (updated) => {
                                  setSelectedMessage(updated);
                                  toast.success("Marked as replied");
                                },
                              })
                            }
                          >
                            Mark as Replied
                          </Button>
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      {/* Send confirmation */}
      <AlertDialog open={!!sendConfirmId} onOpenChange={(open) => { if (!open) { setSendConfirmId(null); setAttachResume(true); } }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Send message?</AlertDialogTitle>
            <AlertDialogDescription>
              This will send the email to the recipient. This action cannot be undone.
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
            <AlertDialogAction onClick={handleSend} disabled={sendMutation.isPending}>
              {sendMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Send
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteConfirmId} onOpenChange={(open) => !open && setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete draft?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this draft message. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
