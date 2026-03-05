"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/providers/auth-provider";
import { usePipelineStats, useFunnel, useOutreachStats } from "@/lib/hooks/use-analytics";
import { useCompanies } from "@/lib/hooks/use-companies";
import * as candidatesApi from "@/lib/api/candidates";
import { UsageCard } from "@/components/dashboard/usage-card";
import { OnboardingChecklist } from "@/components/dashboard/onboarding-checklist";
import { EmailVerificationBanner } from "@/components/dashboard/email-verification-banner";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { FitScore } from "@/components/shared/fit-score";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import { QueryError } from "@/components/shared/query-error";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { formatPercent } from "@/lib/utils";
import {
  Building2,
  Mail,
  Eye,
  MessageSquare,
  Upload,
  Search,
  Plus,
} from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const pipelineQuery = usePipelineStats();
  const funnelQuery = useFunnel();
  const statsQuery = useOutreachStats();
  const companiesQuery = useCompanies();
  const dnaQuery = useQuery({ queryKey: ["dna"], queryFn: candidatesApi.getDNA, retry: 1 });

  const isLoading =
    pipelineQuery.isLoading || funnelQuery.isLoading || statsQuery.isLoading;
  const isError =
    pipelineQuery.isError || funnelQuery.isError || statsQuery.isError;

  const stats = statsQuery.data;
  const pipeline = pipelineQuery.data;
  const recentCompanies = companiesQuery.data?.companies?.slice(0, 5) || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, ${user?.full_name?.split(" ")[0] || "there"}`}
        description="Here's an overview of your job search"
      />

      {/* Quick actions */}
      <div className="flex flex-wrap gap-3">
        <Button variant="default" onClick={() => router.push("/resume")}>
          <Upload className="mr-2 h-4 w-4" />
          Upload Resume
        </Button>
        <Button variant="outline" onClick={() => router.push("/companies")}>
          <Search className="mr-2 h-4 w-4" />
          Discover Companies
        </Button>
        <Button variant="ghost" onClick={() => router.push("/companies")}>
          <Plus className="mr-2 h-4 w-4" />
          Add Company
        </Button>
      </div>

      {/* Email verification banner */}
      {user && !user.email_verified && <EmailVerificationBanner />}

      {/* Onboarding checklist */}
      <OnboardingChecklist
        hasResume={!!dnaQuery.data}
        hasCompanies={(pipeline ? pipeline.suggested + pipeline.approved + pipeline.researched + pipeline.contacted : 0) > 0}
        hasSentMessages={(stats?.total_sent || 0) > 0}
      />

      {/* Stats cards */}
      {isError ? (
        <QueryError
          message="Could not load dashboard stats."
          onRetry={() => {
            pipelineQuery.refetch();
            funnelQuery.refetch();
            statsQuery.refetch();
          }}
        />
      ) : isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <CardTitle className="text-sm font-medium text-muted-foreground cursor-help">
                    Companies
                  </CardTitle>
                </TooltipTrigger>
                <TooltipContent>Total companies in your pipeline</TooltipContent>
              </Tooltip>
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
                <Building2 className="h-4 w-4 text-primary" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {pipeline
                  ? pipeline.suggested + pipeline.approved + pipeline.researched + pipeline.contacted
                  : 0}
              </div>
              <p className="text-xs text-muted-foreground">
                {pipeline?.approved || 0} approved
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <CardTitle className="text-sm font-medium text-muted-foreground cursor-help">
                    Emails Sent
                  </CardTitle>
                </TooltipTrigger>
                <TooltipContent>Total outreach emails you&apos;ve sent</TooltipContent>
              </Tooltip>
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
                <Mail className="h-4 w-4 text-primary" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.total_sent || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <CardTitle className="text-sm font-medium text-muted-foreground cursor-help">
                    Open Rate
                  </CardTitle>
                </TooltipTrigger>
                <TooltipContent>Percentage of sent emails that were opened</TooltipContent>
              </Tooltip>
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
                <Eye className="h-4 w-4 text-primary" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats ? formatPercent(stats.open_rate) : "0%"}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <CardTitle className="text-sm font-medium text-muted-foreground cursor-help">
                    Reply Rate
                  </CardTitle>
                </TooltipTrigger>
                <TooltipContent>Percentage of sent emails that got a reply</TooltipContent>
              </Tooltip>
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
                <MessageSquare className="h-4 w-4 text-primary" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats ? formatPercent(stats.reply_rate) : "0%"}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Pipeline mini + Usage */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {pipeline && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Pipeline Overview</CardTitle>
              </CardHeader>
              <CardContent>
                {(() => {
                  const stages = [
                    { label: "Suggested", value: pipeline.suggested, barColor: "bg-chart-1", tip: "AI-recommended companies based on your DNA profile" },
                    { label: "Approved", value: pipeline.approved, barColor: "bg-chart-2", tip: "Companies you've approved for outreach" },
                    { label: "Researched", value: pipeline.researched, barColor: "bg-chart-3", tip: "Companies with completed research dossiers" },
                    { label: "Contacted", value: pipeline.contacted, barColor: "bg-chart-4", tip: "Companies where outreach has been sent" },
                  ];
                  const total = Math.max(stages.reduce((sum, s) => sum + s.value, 0), 1);
                  return (
                    <div className="space-y-3">
                      {stages.map((stage) => (
                        <Tooltip key={stage.label}>
                          <TooltipTrigger asChild>
                            <div className="flex items-center gap-3 cursor-help">
                              <span className="w-24 text-xs text-muted-foreground text-right">{stage.label}</span>
                              <div className="flex-1 h-2.5 rounded-full bg-muted overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${stage.barColor}`}
                                  style={{ width: `${(stage.value / total) * 100}%` }}
                                />
                              </div>
                              <span className="w-8 text-sm font-bold text-right">{stage.value}</span>
                            </div>
                          </TooltipTrigger>
                          <TooltipContent>{stage.tip}</TooltipContent>
                        </Tooltip>
                      ))}
                    </div>
                  );
                })()}
              </CardContent>
            </Card>
          )}
        </div>
        <UsageCard />
      </div>

      {/* Recent companies */}
      {recentCompanies.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Recent Companies</CardTitle>
            <Link href="/companies">
              <Button variant="ghost" size="sm">
                View all
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead>
                  <TableHead>Fit Score</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentCompanies.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/companies/${c.id}`)}
                  >
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell>
                      <FitScore score={c.fit_score} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge type="company" status={c.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      {recentCompanies.length === 0 && !companiesQuery.isLoading && (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-sm text-muted-foreground">No companies in your pipeline yet.</p>
            <Button variant="outline" className="mt-3" onClick={() => router.push("/companies")}>
              <Search className="mr-2 h-4 w-4" />
              Discover Companies
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
