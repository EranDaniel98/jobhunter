"use client";

import { use, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCompany,
  useCompanies,
  useDossier,
  useCompanyContacts,
  useCompanyNotes,
  useUpsertCompanyNotes,
  useApproveCompany,
  useRejectCompany,
} from "@/lib/hooks/use-companies";
import { useMessages } from "@/lib/hooks/use-outreach";

import { StatusBadge } from "@/components/shared/status-badge";
import { FitScore } from "@/components/shared/fit-score";
import { DossierView } from "@/components/companies/dossier-view";
import { ContactsList } from "@/components/companies/contacts-list";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { cn, formatDateTime } from "@/lib/utils";
import { ArrowLeft, Building2, Check, Loader2, X, Globe, MapPin, Users, Banknote, Mail, Linkedin } from "lucide-react";

function statusDotColor(status: string): string {
  switch (status) {
    case "replied": return "bg-green-500";
    case "delivered": return "bg-blue-500";
    case "opened": return "bg-amber-500";
    case "sent": return "bg-indigo-500";
    case "bounced": return "bg-red-500";
    default: return "bg-gray-400";
  }
}

export default function CompanyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { data: company, isLoading } = useCompany(id);
  const dossierQuery = useDossier(id, company?.research_status === "completed");
  const contactsQuery = useCompanyContacts(id);
  const approveMutation = useApproveCompany();
  const rejectMutation = useRejectCompany();
  const messagesQuery = useMessages();
  const notesQuery = useCompanyNotes(id);
  const upsertNotesMutation = useUpsertCompanyNotes();
  const allCompaniesQuery = useCompanies();
  const [noteContent, setNoteContent] = useState("");
  const [notesDirty, setNotesDirty] = useState(false);

  useEffect(() => {
    if (notesQuery.data?.content !== undefined) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sync server state to local draft
      setNoteContent(notesQuery.data.content);
    }
  }, [notesQuery.data?.content]);

  function handleSaveNotes() {
    if (!notesDirty) return;
    upsertNotesMutation.mutate(
      { companyId: id, content: noteContent },
      { onSuccess: () => { setNotesDirty(false); toast.success("Notes saved"); } }
    );
  }

  if (isLoading) return <PageSkeleton />;
  if (!company) {
    return (
      <EmptyState
        icon={Building2}
        title="Company not found"
        description="This company may have been removed or the link is incorrect."
        action={{ label: "Back to Companies", onClick: () => router.push("/companies") }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Link href="/companies" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Back to companies
      </Link>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{company.name}</h1>
            <StatusBadge type="company" status={company.status} />
            <StatusBadge type="research" status={company.research_status} />
            {company.research_status === "failed" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => approveMutation.mutate(company.id)}
                disabled={approveMutation.isPending}
              >
                {approveMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Retry Research
              </Button>
            )}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            {company.domain && (
              <span className="flex items-center gap-1">
                <Globe className="h-3.5 w-3.5" />
                {company.domain}
              </span>
            )}
            {company.location_hq && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {company.location_hq}
              </span>
            )}
            {company.size_range && (
              <span className="flex items-center gap-1">
                <Users className="h-3.5 w-3.5" />
                {company.size_range}
              </span>
            )}
            {company.funding_stage && (
              <span className="flex items-center gap-1">
                <Banknote className="h-3.5 w-3.5" />
                {company.funding_stage}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <FitScore score={company.fit_score} />
          {company.status === "suggested" && (
            <>
              <Button
                size="sm"
                variant="outline"
                className="text-primary hover:bg-primary/10 hover:text-primary"
                onClick={() =>
                  approveMutation.mutate(company.id, {
                    onSuccess: () => toast.success("Company approved"),
                  })
                }
              >
                <Check className="mr-1 h-4 w-4" />
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() =>
                  rejectMutation.mutate(
                    { id: company.id, reason: "Not interested" },
                    { onSuccess: () => toast.success("Company rejected") }
                  )
                }
              >
                <X className="mr-1 h-4 w-4" />
                Reject
              </Button>
            </>
          )}
        </div>
      </div>

      {company.description && (
        <Card>
          <CardContent className="py-4">
            <p className="text-sm text-muted-foreground">{company.description}</p>
            {company.tech_stack && company.tech_stack.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1">
                {company.tech_stack.map((tech, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {tech}
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="dossier">
        <TabsList>
          <TabsTrigger value="dossier">Dossier</TabsTrigger>
          <TabsTrigger value="contacts">
            Contacts {contactsQuery.data ? `(${contactsQuery.data.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="outreach">Outreach</TabsTrigger>
        </TabsList>
        <TabsContent value="dossier" className="mt-4">
          <DossierView
            dossier={dossierQuery.data || null}
            isLoading={dossierQuery.isLoading}
            researchStatus={company.research_status}
          />
        </TabsContent>
        <TabsContent value="contacts" className="mt-4">
          <ContactsList
            companyId={company.id}
            contacts={contactsQuery.data || []}
            isLoading={contactsQuery.isLoading}
          />
        </TabsContent>
        <TabsContent value="outreach" className="mt-4">
          {(() => {
            const contactIds = new Set((contactsQuery.data || []).map(c => c.id));
            const companyMessages = (messagesQuery.data || []).filter(m => contactIds.has(m.contact_id));
            if (messagesQuery.isLoading) return <PageSkeleton />;
            if (companyMessages.length === 0) {
              return (
                <EmptyState
                  icon={Mail}
                  title="No outreach yet"
                  description="No outreach messages sent to this company yet."
                />
              );
            }
            return (
              <div className="space-y-2">
                {companyMessages.map(msg => (
                  <div key={msg.id} className="flex items-center gap-3 rounded-lg border p-3">
                    <div className={cn("h-2.5 w-2.5 rounded-full shrink-0", statusDotColor(msg.status))} />
                    {msg.channel === "linkedin" ? <Linkedin className="h-4 w-4 text-muted-foreground" /> : <Mail className="h-4 w-4 text-muted-foreground" />}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{msg.subject || "(No subject)"}</p>
                      <p className="text-xs text-muted-foreground">{msg.sent_at ? formatDateTime(msg.sent_at) : "Draft"}</p>
                    </div>
                    <StatusBadge type="message" status={msg.status} />
                  </div>
                ))}
              </div>
            );
          })()}
        </TabsContent>
      </Tabs>

      {/* Notes */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            value={noteContent}
            onChange={(e) => { setNoteContent(e.target.value); setNotesDirty(true); }}
            onBlur={handleSaveNotes}
            placeholder="Add personal notes about this company..."
            rows={4}
            className="resize-y"
          />
          {upsertNotesMutation.isPending && (
            <p className="mt-1 text-xs text-muted-foreground">Saving...</p>
          )}
        </CardContent>
      </Card>

      {/* Similar Companies */}
      {(() => {
        const similarCompanies = (allCompaniesQuery.data?.companies || [])
          .filter(c => c.id !== id)
          .filter(c => {
            if (company.industry && c.industry === company.industry) return true;
            if (company.tech_stack?.length && c.tech_stack?.length) {
              return company.tech_stack.some(t => c.tech_stack!.includes(t));
            }
            return false;
          })
          .sort((a, b) => (b.fit_score || 0) - (a.fit_score || 0))
          .slice(0, 3);
        if (similarCompanies.length === 0) return null;
        return (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Similar Companies</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-3">
                {similarCompanies.map(c => (
                  <Link key={c.id} href={`/companies/${c.id}`} className="rounded-lg border p-3 hover:bg-muted/50 transition-colors">
                    <h4 className="font-medium text-sm">{c.name}</h4>
                    <p className="text-xs text-muted-foreground">{c.industry || c.domain}</p>
                    <div className="mt-2"><FitScore score={c.fit_score} /></div>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        );
      })()}
    </div>
  );
}
