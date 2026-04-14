"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { QueryError } from "@/components/shared/query-error";
import { StatusBadge } from "@/components/shared/status-badge";
import { FitScore } from "@/components/shared/fit-score";
import { AddCompanyDialog } from "@/components/companies/add-company-dialog";
import { OperationProgress } from "@/components/shared/operation-progress";
import {
  useCompanies,
  useDiscoverCompanies,
  useApproveCompany,
  useRejectCompany,
} from "@/lib/hooks/use-companies";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { toastError } from "@/lib/api/error-utils";
import {
  Building2,
  Loader2,
  Search,
  Plus,
  Check,
  X,
  ArrowUpDown,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

type SortField = "name" | "fit_score" | "date_added" | "status" | "";

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "suggested", label: "Suggested" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
] as const;

export default function CompaniesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortField>("fit_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [addOpen, setAddOpen] = useState(false);
  const [discoverOpen, setDiscoverOpen] = useState(false);
  const [filterIndustries, setFilterIndustries] = useState("");
  const [filterLocations, setFilterLocations] = useState("");
  const [filterSize, setFilterSize] = useState("");
  const [filterKeywords, setFilterKeywords] = useState("");
  const router = useRouter();

  const queryStatus = statusFilter === "all" ? undefined : statusFilter;
  const { data, isLoading, isError, refetch } = useCompanies(queryStatus);
  const discoverMutation = useDiscoverCompanies();
  const approveMutation = useApproveCompany();
  const rejectMutation = useRejectCompany();

  const companies = data?.companies || [];

  // Derived stats (computed from full unfiltered list)
  const totalCompanies = companies.length;
  const approvedCount = companies.filter((c) => c.status === "approved").length;
  const researchedCount = companies.filter(
    (c) => c.research_status === "completed"
  ).length;
  const avgFitScore =
    companies.length > 0
      ? Math.round(
          companies.reduce((sum, c) => sum + (c.fit_score ?? 0), 0) /
            companies.length
        )
      : 0;

  const filteredCompanies = companies
    .filter(
      (c) =>
        searchQuery === "" ||
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.domain &&
          c.domain.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (c.industry &&
          c.industry.toLowerCase().includes(searchQuery.toLowerCase()))
    )
    .sort((a, b) => {
      if (!sortBy) return 0;
      if (sortBy === "name") {
        return sortDir === "asc"
          ? a.name.localeCompare(b.name)
          : b.name.localeCompare(a.name);
      }
      if (sortBy === "fit_score") {
        return sortDir === "asc"
          ? (a.fit_score || 0) - (b.fit_score || 0)
          : (b.fit_score || 0) - (a.fit_score || 0);
      }
      if (sortBy === "date_added") {
        const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
        const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
        return sortDir === "asc" ? ta - tb : tb - ta;
      }
      if (sortBy === "status") {
        return sortDir === "asc"
          ? a.status.localeCompare(b.status)
          : b.status.localeCompare(a.status);
      }
      return 0;
    });

  function toggleSort(col: SortField) {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir(col === "name" || col === "status" ? "asc" : "desc");
    }
  }

  function handleSortDropdown(value: string) {
    // Split on the last underscore to handle field names like "fit_score"
    const lastIdx = value.lastIndexOf("_");
    const field = value.slice(0, lastIdx) as SortField;
    const dir = value.slice(lastIdx + 1) as "asc" | "desc";
    setSortBy(field);
    setSortDir(dir);
  }

  function handleDiscover() {
    const filters: Record<string, unknown> = {};
    if (filterIndustries.trim()) {
      filters.industries = filterIndustries
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    if (filterLocations.trim()) {
      filters.locations = filterLocations
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    if (filterSize && filterSize !== "any") {
      filters.company_size = filterSize;
    }
    if (filterKeywords.trim()) {
      filters.keywords = filterKeywords.trim();
    }

    discoverMutation.mutate(
      Object.keys(filters).length > 0 ? filters : undefined,
      {
        onSuccess: (result) => {
          toast.success(`Discovered ${result.total} companies`);
          setDiscoverOpen(false);
        },
        onError: (err: unknown) => {
          toastError(err, "Discovery failed");
        },
      }
    );
  }

  return (
    <div className="space-y-5">
      {/* Page Header - title + description only */}
      <PageHeader
        title="Companies"
        description="Track and manage your target company pipeline"
        dataTour="page-header"
      />

      {/* Stats row */}
      {!isLoading && !isError && (
        <div className="flex flex-wrap gap-2">
          <div className="flex items-center gap-1.5 rounded-full border bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
            <Building2 className="h-3 w-3" />
            <span className="font-medium text-foreground">{totalCompanies}</span>
            total
          </div>
          <div className="flex items-center gap-1.5 rounded-full border bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
            <Check className="h-3 w-3 text-primary" />
            <span className="font-medium text-foreground">{approvedCount}</span>
            approved
          </div>
          <div className="flex items-center gap-1.5 rounded-full border bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
            <Search className="h-3 w-3" />
            <span className="font-medium text-foreground">{researchedCount}</span>
            researched
          </div>
          {totalCompanies > 0 && (
            <div className="flex items-center gap-1.5 rounded-full border bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
              <Sparkles className="h-3 w-3 text-chart-3" />
              avg fit
              <span className="font-medium text-foreground">{avgFitScore}%</span>
            </div>
          )}
        </div>
      )}

      {/* Action row */}
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-muted-foreground">
          {!isLoading && !isError && (
            <span>
              {filteredCompanies.length}{" "}
              {filteredCompanies.length === 1 ? "company" : "companies"}
              {statusFilter !== "all" && ` · ${statusFilter}`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setDiscoverOpen((o) => !o)}
            aria-expanded={discoverOpen}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            Discover
            {discoverOpen ? (
              <ChevronUp className="ml-1 h-3 w-3" />
            ) : (
              <ChevronDown className="ml-1 h-3 w-3" />
            )}
          </Button>
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Company
          </Button>
        </div>
      </div>

      {/* Discover panel - collapsible */}
      {discoverOpen && (
        <Card className="border-dashed">
          <CardContent className="pt-5 pb-4">
            <p className="mb-4 text-sm font-medium">
              Discover companies matching your profile
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs">Industries (comma-separated)</Label>
                <Input
                  placeholder="e.g. fintech, saas, healthtech"
                  value={filterIndustries}
                  onChange={(e) => setFilterIndustries(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Locations (comma-separated)</Label>
                <Input
                  placeholder="e.g. Tel Aviv, New York, Remote"
                  value={filterLocations}
                  onChange={(e) => setFilterLocations(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Company size</Label>
                <Select value={filterSize} onValueChange={setFilterSize}>
                  <SelectTrigger>
                    <SelectValue placeholder="Any size" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any size</SelectItem>
                    <SelectItem value="startup">Startup (1–50)</SelectItem>
                    <SelectItem value="mid-size">Mid-size (51–500)</SelectItem>
                    <SelectItem value="enterprise">Enterprise (500+)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Keywords</Label>
                <Textarea
                  placeholder="Describe what you're looking for..."
                  value={filterKeywords}
                  onChange={(e) => setFilterKeywords(e.target.value)}
                  rows={2}
                />
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {discoverMutation.isPending && (
                <OperationProgress status="in_progress" label="Discovering companies that match your profile…" />
              )}
              <div className="flex justify-end">
                <Button
                  onClick={handleDiscover}
                  disabled={discoverMutation.isPending}
                >
                  {discoverMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4" />
                  )}
                  {discoverMutation.isPending ? "Discovering…" : "Run Discovery"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filter / sort bar - always visible */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search companies…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
          />
        </div>

        {/* Sort */}
        <Select
          value={`${sortBy}_${sortDir}`}
          onValueChange={handleSortDropdown}
        >
          <SelectTrigger className="w-[220px] shrink-0">
            <ArrowUpDown className="mr-2 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="Sort by…" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="fit_score_desc">Fit Score (high first)</SelectItem>
            <SelectItem value="fit_score_asc">Fit Score (low first)</SelectItem>
            <SelectItem value="name_asc">Name (A–Z)</SelectItem>
            <SelectItem value="name_desc">Name (Z–A)</SelectItem>
            <SelectItem value="date_added_desc">Date Added (newest)</SelectItem>
            <SelectItem value="date_added_asc">Date Added (oldest)</SelectItem>
            <SelectItem value="status_asc">Status (A–Z)</SelectItem>
          </SelectContent>
        </Select>

        {/* Status filter chips */}
        <div className="flex items-center gap-1 shrink-0">
          {STATUS_FILTERS.map((f) => (
            <Button
              key={f.value}
              size="sm"
              variant={statusFilter === f.value ? "default" : "outline"}
              className="h-8 rounded-full px-3 text-xs"
              onClick={() => setStatusFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Loading / error / empty states */}
      {isLoading && <TableSkeleton />}

      {!isLoading && isError && (
        <QueryError
          message="Could not load companies."
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !isError && filteredCompanies.length === 0 && (
        <EmptyState
          icon={Building2}
          title="No companies yet"
          description="Upload a resume and discover companies, or add one manually."
          action={{ label: "Discover Companies", onClick: () => setDiscoverOpen(true) }}
        />
      )}

      {/* Companies table */}
      {!isLoading && !isError && filteredCompanies.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead
                  className="cursor-pointer select-none"
                  onClick={() => toggleSort("name")}
                >
                  <span className="flex items-center gap-1">
                    Company
                    <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                  </span>
                </TableHead>
                <TableHead className="hidden sm:table-cell">Industry</TableHead>
                <TableHead className="hidden md:table-cell">Location</TableHead>
                <TableHead
                  className="cursor-pointer select-none"
                  onClick={() => toggleSort("fit_score")}
                >
                  <span className="flex items-center gap-1">
                    Fit Score
                    <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                  </span>
                </TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Research</TableHead>
                <TableHead className="hidden lg:table-cell">Tech Stack</TableHead>
                <TableHead className="hidden lg:table-cell">Funding</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredCompanies.map((company) => {
                const techStack = company.tech_stack ?? [];
                const visibleTech = techStack.slice(0, 3);
                const extraCount = techStack.length - 3;

                return (
                  <TableRow
                    key={company.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/companies/${company.id}`)}
                  >
                    <TableCell>
                      <div>
                        <div className="font-medium">{company.name}</div>
                        {company.domain && (
                          <div className="text-xs text-muted-foreground">
                            {company.domain}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                      {company.industry || "\u2014"}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                      {company.location_hq || "\u2014"}
                    </TableCell>
                    <TableCell>
                      <FitScore score={company.fit_score} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge type="company" status={company.status} />
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <StatusBadge
                        type="research"
                        status={company.research_status}
                      />
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <div className="flex flex-wrap gap-1">
                        {visibleTech.map((t) => (
                          <Badge
                            key={t}
                            variant="outline"
                            className="text-[10px] font-normal"
                          >
                            {t}
                          </Badge>
                        ))}
                        {extraCount > 0 && (
                          <Badge
                            variant="outline"
                            className="text-[10px] font-normal"
                          >
                            +{extraCount}
                          </Badge>
                        )}
                        {techStack.length === 0 && (
                          <span className="text-muted-foreground">{"\u2014"}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      {company.funding_stage ? (
                        <Badge variant="secondary" className="text-[10px]">
                          {company.funding_stage}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">{"\u2014"}</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div
                        className="flex justify-end gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {company.status === "suggested" && (
                          <>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-primary hover:bg-primary/10 hover:text-primary"
                              aria-label={`Approve ${company.name}`}
                              onClick={() =>
                                approveMutation.mutate(company.id, {
                                  onSuccess: () => toast.success("Company approved"),
                                  onError: (err: unknown) => toastError(err, "Failed to approve company"),
                                })
                              }
                              disabled={approveMutation.isPending}
                            >
                              <Check className="h-4 w-4" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                              aria-label={`Reject ${company.name}`}
                              onClick={() =>
                                rejectMutation.mutate(
                                  { id: company.id, reason: "Not interested" },
                                  {
                                    onSuccess: () => toast.success("Company rejected"),
                                    onError: (err: unknown) => toastError(err, "Failed to reject company"),
                                  }
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
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <AddCompanyDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  );
}
