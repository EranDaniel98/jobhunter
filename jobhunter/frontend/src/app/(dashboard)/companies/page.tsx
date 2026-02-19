"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { StatusBadge } from "@/components/shared/status-badge";
import { FitScore } from "@/components/shared/fit-score";
import { AddCompanyDialog } from "@/components/companies/add-company-dialog";
import {
  useCompanies,
  useDiscoverCompanies,
  useApproveCompany,
  useRejectCompany,
} from "@/lib/hooks/use-companies";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "sonner";
import { Building2, Loader2, Search, Plus, Check, X, SlidersHorizontal } from "lucide-react";

export default function CompaniesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [addOpen, setAddOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filterIndustries, setFilterIndustries] = useState("");
  const [filterLocations, setFilterLocations] = useState("");
  const [filterSize, setFilterSize] = useState("");
  const [filterKeywords, setFilterKeywords] = useState("");
  const router = useRouter();

  const queryStatus = statusFilter === "all" ? undefined : statusFilter;
  const { data, isLoading } = useCompanies(queryStatus);
  const discoverMutation = useDiscoverCompanies();
  const approveMutation = useApproveCompany();
  const rejectMutation = useRejectCompany();

  const companies = data?.companies || [];

  function handleDiscover() {
    const filters: Record<string, unknown> = {};
    if (filterIndustries.trim()) {
      filters.industries = filterIndustries.split(",").map((s) => s.trim()).filter(Boolean);
    }
    if (filterLocations.trim()) {
      filters.locations = filterLocations.split(",").map((s) => s.trim()).filter(Boolean);
    }
    if (filterSize && filterSize !== "any") {
      filters.company_size = filterSize;
    }
    if (filterKeywords.trim()) {
      filters.keywords = filterKeywords.trim();
    }

    discoverMutation.mutate(Object.keys(filters).length > 0 ? filters : undefined, {
      onSuccess: (result) => {
        toast.success(`Discovered ${result.total} companies`);
      },
      onError: (err: unknown) => {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Discovery failed";
        toast.error(msg);
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Companies" description="Manage your target company pipeline">
        <Button variant="outline" onClick={() => setAddOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Company
        </Button>
        <Button variant="outline" onClick={() => setFiltersOpen(!filtersOpen)}>
          <SlidersHorizontal className="mr-2 h-4 w-4" />
          Filters
        </Button>
        <Button onClick={handleDiscover} disabled={discoverMutation.isPending}>
          {discoverMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Search className="mr-2 h-4 w-4" />
          )}
          Discover
        </Button>
      </PageHeader>

      {filtersOpen && (
        <Card>
          <CardContent className="grid gap-4 sm:grid-cols-2 pt-6">
            <div className="space-y-2">
              <Label>Industries (comma-separated)</Label>
              <Input
                placeholder="e.g. fintech, saas, healthtech"
                value={filterIndustries}
                onChange={(e) => setFilterIndustries(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Locations (comma-separated)</Label>
              <Input
                placeholder="e.g. Tel Aviv, New York, Remote"
                value={filterLocations}
                onChange={(e) => setFilterLocations(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Company size</Label>
              <Select value={filterSize} onValueChange={setFilterSize}>
                <SelectTrigger>
                  <SelectValue placeholder="Any size" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Any size</SelectItem>
                  <SelectItem value="startup">Startup (1-50)</SelectItem>
                  <SelectItem value="mid-size">Mid-size (51-500)</SelectItem>
                  <SelectItem value="enterprise">Enterprise (500+)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Keywords</Label>
              <Textarea
                placeholder="Describe what you're looking for..."
                value={filterKeywords}
                onChange={(e) => setFilterKeywords(e.target.value)}
                rows={2}
              />
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs value={statusFilter} onValueChange={setStatusFilter}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="suggested">Suggested</TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="rejected">Rejected</TabsTrigger>
        </TabsList>
      </Tabs>

      {isLoading && <TableSkeleton />}

      {!isLoading && companies.length === 0 && (
        <EmptyState
          icon={Building2}
          title="No companies yet"
          description="Upload a resume and discover companies, or add one manually."
          action={{ label: "Discover Companies", onClick: handleDiscover }}
        />
      )}

      {!isLoading && companies.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead className="hidden sm:table-cell">Industry</TableHead>
                <TableHead>Fit Score</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Research</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {companies.map((company) => (
                <TableRow
                  key={company.id}
                  className="cursor-pointer"
                  onClick={() => router.push(`/companies/${company.id}`)}
                >
                  <TableCell>
                    <div>
                      <div className="font-medium">{company.name}</div>
                      <div className="text-xs text-muted-foreground">{company.domain}</div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {company.industry || "—"}
                  </TableCell>
                  <TableCell>
                    <FitScore score={company.fit_score} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge type="company" status={company.status} />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <StatusBadge type="research" status={company.research_status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                      {company.status === "suggested" && (
                        <>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-green-600"
                            onClick={() =>
                              approveMutation.mutate(company.id, {
                                onSuccess: () => toast.success("Company approved"),
                              })
                            }
                            disabled={approveMutation.isPending}
                          >
                            <Check className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-red-600"
                            onClick={() =>
                              rejectMutation.mutate(
                                { id: company.id, reason: "Not interested" },
                                { onSuccess: () => toast.success("Company rejected") }
                              )
                            }
                            disabled={rejectMutation.isPending}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <AddCompanyDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  );
}
