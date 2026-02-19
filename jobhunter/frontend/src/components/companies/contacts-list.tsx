"use client";

import { useState } from "react";
import type { ContactResponse } from "@/lib/types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as contactsApi from "@/lib/api/contacts";
import { useDraftMessage, useDraftLinkedIn } from "@/lib/hooks/use-outreach";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { toast } from "sonner";
import {
  Loader2,
  UserPlus,
  ShieldCheck,
  Mail,
  Linkedin,
  Users,
  Star,
} from "lucide-react";

interface ContactsListProps {
  companyId: string;
  contacts: ContactResponse[];
  isLoading: boolean;
}

export function ContactsList({ companyId, contacts, isLoading }: ContactsListProps) {
  const [findOpen, setFindOpen] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [language, setLanguage] = useState("en");
  const queryClient = useQueryClient();

  const findMutation = useMutation({
    mutationFn: () => contactsApi.findContact(companyId, firstName, lastName),
    onSuccess: () => {
      toast.success("Contact found");
      setFindOpen(false);
      setFirstName("");
      setLastName("");
      queryClient.invalidateQueries({ queryKey: ["contacts", companyId] });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Contact not found";
      toast.error(msg);
    },
  });

  const verifyMutation = useMutation({
    mutationFn: contactsApi.verifyContact,
    onSuccess: () => {
      toast.success("Email verified");
      queryClient.invalidateQueries({ queryKey: ["contacts", companyId] });
    },
    onError: () => toast.error("Verification failed"),
  });

  const draftEmailMutation = useDraftMessage();
  const draftLinkedInMutation = useDraftLinkedIn();

  if (isLoading) return <TableSkeleton />;

  if (contacts.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No contacts yet"
        description="Find contacts at this company to start outreach."
        action={{ label: "Find Contact", onClick: () => setFindOpen(true) }}
      />
    );
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Label className="text-sm text-muted-foreground">Outreach language:</Label>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="w-[130px] h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="en">English</SelectItem>
              <SelectItem value="he">{"\u05E2\u05D1\u05E8\u05D9\u05EA"}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" onClick={() => setFindOpen(true)}>
          <UserPlus className="mr-2 h-4 w-4" />
          Find Contact
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="hidden sm:table-cell">Title</TableHead>
              <TableHead>Email</TableHead>
              <TableHead className="hidden md:table-cell">Priority</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((contact) => (
              <TableRow key={contact.id}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{contact.full_name}</span>
                    {contact.is_decision_maker && (
                      <Star className="h-3.5 w-3.5 text-yellow-500" />
                    )}
                  </div>
                </TableCell>
                <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                  {contact.title || "—"}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm">{contact.email || "—"}</span>
                    {contact.email_verified && (
                      <ShieldCheck className="h-3.5 w-3.5 text-green-500" />
                    )}
                    {!contact.email_verified && contact.email_confidence !== null && (
                      <Badge variant="secondary" className="text-xs">
                        {Math.round((contact.email_confidence ?? 0) * 100)}%
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <Badge variant="secondary">{contact.outreach_priority}</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    {contact.email && !contact.email_verified && (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={() => verifyMutation.mutate(contact.id)}
                        disabled={verifyMutation.isPending}
                        title="Verify email"
                      >
                        <ShieldCheck className="h-4 w-4" />
                      </Button>
                    )}
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8"
                      onClick={() =>
                        draftEmailMutation.mutate(
                          { contactId: contact.id, language },
                          {
                            onSuccess: () => toast.success("Email draft created"),
                            onError: () => toast.error("Failed to create draft"),
                          }
                        )
                      }
                      disabled={draftEmailMutation.isPending}
                      title="Draft email"
                    >
                      {draftEmailMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Mail className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8"
                      onClick={() =>
                        draftLinkedInMutation.mutate(
                          { contactId: contact.id, language },
                          {
                            onSuccess: () => toast.success("LinkedIn message draft created"),
                            onError: () => toast.error("Failed to create draft"),
                          }
                        )
                      }
                      disabled={draftLinkedInMutation.isPending}
                      title="Draft LinkedIn message"
                    >
                      <Linkedin className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={findOpen} onOpenChange={setFindOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Find Contact</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              findMutation.mutate();
            }}
          >
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>First name</Label>
                <Input
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Last name</Label>
                <Input
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFindOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={findMutation.isPending}>
                {findMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Find
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
