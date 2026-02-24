"use client";

import { use } from "react";
import Link from "next/link";
import {
  useCompany,
  useDossier,
  useCompanyContacts,
  useApproveCompany,
  useRejectCompany,
} from "@/lib/hooks/use-companies";

import { StatusBadge } from "@/components/shared/status-badge";
import { FitScore } from "@/components/shared/fit-score";
import { DossierView } from "@/components/companies/dossier-view";
import { ContactsList } from "@/components/companies/contacts-list";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { ArrowLeft, Check, X, Globe, MapPin, Users, Banknote } from "lucide-react";

export default function CompanyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: company, isLoading } = useCompany(id);
  const dossierQuery = useDossier(id, company?.research_status === "completed");
  const contactsQuery = useCompanyContacts(id);
  const approveMutation = useApproveCompany();
  const rejectMutation = useRejectCompany();

  if (isLoading) return <PageSkeleton />;
  if (!company) return <p>Company not found</p>;

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
                className="text-green-600"
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
                className="text-red-600"
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
      </Tabs>
    </div>
  );
}
