"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/providers/auth-provider";
import { usePipelineStats, useFunnel, useOutreachStats } from "@/lib/hooks/use-analytics";
import { useCompanies } from "@/lib/hooks/use-companies";
import * as candidatesApi from "@/lib/api/candidates";
import { OnboardingChecklist } from "@/components/dashboard/onboarding-checklist";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { FitScore } from "@/components/shared/fit-score";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
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
        <Button variant="outline" onClick={() => router.push("/resume")}>
          <Upload className="mr-2 h-4 w-4" />
          Upload Resume
        </Button>
        <Button variant="outline" onClick={() => router.push("/companies")}>
          <Search className="mr-2 h-4 w-4" />
          Discover Companies
        </Button>
        <Button variant="outline" onClick={() => router.push("/companies")}>
          <Plus className="mr-2 h-4 w-4" />
          Add Company
        </Button>
      </div>

      {/* Onboarding checklist */}
      <OnboardingChecklist
        hasResume={!!dnaQuery.data}
        hasCompanies={(pipeline ? pipeline.suggested + pipeline.approved + pipeline.researched + pipeline.contacted : 0) > 0}
        hasSentMessages={(stats?.total_sent || 0) > 0}
      />

      {/* Stats cards */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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
              <Building2 className="h-4 w-4 text-muted-foreground" />
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
              <Mail className="h-4 w-4 text-muted-foreground" />
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
              <Eye className="h-4 w-4 text-muted-foreground" />
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
              <MessageSquare className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats ? formatPercent(stats.reply_rate) : "0%"}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Pipeline mini */}
      {pipeline && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pipeline Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-6 text-center">
              {[
                { label: "Suggested", value: pipeline.suggested, color: "text-blue-600", tip: "AI-recommended companies based on your DNA profile" },
                { label: "Approved", value: pipeline.approved, color: "text-green-600", tip: "Companies you've approved for outreach" },
                { label: "Researched", value: pipeline.researched, color: "text-purple-600", tip: "Companies with completed research dossiers" },
                { label: "Contacted", value: pipeline.contacted, color: "text-yellow-600", tip: "Companies where outreach has been sent" },
              ].map((item) => (
                <Tooltip key={item.label}>
                  <TooltipTrigger asChild>
                    <div className="cursor-help">
                      <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
                      <div className="text-xs text-muted-foreground">{item.label}</div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>{item.tip}</TooltipContent>
                </Tooltip>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

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
    </div>
  );
}
