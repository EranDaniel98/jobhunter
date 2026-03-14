"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/providers/auth-provider";
import { useAnalyticsDashboard } from "@/lib/hooks/use-analytics-insights";
import { useCompanies } from "@/lib/hooks/use-companies";
import { useApprovalCount } from "@/lib/hooks/use-approvals";
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
import { Progress } from "@/components/ui/progress";
import { formatPercent } from "@/lib/utils";
import {
  Building2,
  Mail,
  Eye,
  MessageSquare,
  Search,
  ArrowRight,
  ClipboardCheck,
  FileText,
  Zap,
  TrendingUp,
} from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const dashboardQuery = useAnalyticsDashboard();
  const companiesQuery = useCompanies();
  const dnaQuery = useQuery({ queryKey: ["dna"], queryFn: candidatesApi.getDNA, retry: 1 });
  const approvalCountQuery = useApprovalCount();

  const isLoading = dashboardQuery.isLoading;
  const isError = dashboardQuery.isError;

  const stats = dashboardQuery.data?.outreach;
  const pipeline = dashboardQuery.data?.pipeline;
  const funnel = dashboardQuery.data?.funnel;
  const recentCompanies = companiesQuery.data?.companies?.slice(0, 5) || [];
  const pendingCount = approvalCountQuery.data?.count || 0;
  const totalCompanies = pipeline
    ? pipeline.suggested + pipeline.approved + pipeline.researched + pipeline.contacted
    : 0;

  // Compute next actions based on current state
  const nextActions: { label: string; description: string; href: string; icon: React.ElementType; priority: "high" | "medium" | "low" }[] = [];
  if (!dnaQuery.data) {
    nextActions.push({ label: "Upload your resume", description: "Get AI-powered job matching", href: "/resume", icon: FileText, priority: "high" });
  }
  if (pendingCount > 0) {
    nextActions.push({ label: `Review ${pendingCount} pending approval${pendingCount > 1 ? "s" : ""}`, description: "Messages waiting for your review", href: "/approvals", icon: ClipboardCheck, priority: "high" });
  }
  if (totalCompanies === 0 && dnaQuery.data) {
    nextActions.push({ label: "Discover companies", description: "Find companies that match your profile", href: "/companies", icon: Search, priority: "medium" });
  }
  if (pipeline && pipeline.approved > 0 && pipeline.contacted === 0) {
    nextActions.push({ label: "Start outreach", description: `${pipeline.approved} companies ready for contact`, href: "/outreach", icon: Mail, priority: "medium" });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, ${user?.full_name?.split(" ")[0] || "there"}`}
        description="Here's an overview of your job search"
      />

      {/* Email verification banner */}
      {user && !user.email_verified && <EmailVerificationBanner />}

      {/* Onboarding checklist */}
      <OnboardingChecklist
        hasResume={!!dnaQuery.data}
        hasCompanies={totalCompanies > 0}
        hasSentMessages={(stats?.total_sent || 0) > 0}
      />

      {/* Next Actions - contextual prompts */}
      {nextActions.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {nextActions.slice(0, 3).map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.href}
                onClick={() => router.push(action.href)}
                className="group flex items-center gap-3 rounded-2xl border bg-card p-4 text-left transition-all hover:shadow-md hover:border-primary/20"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{action.label}</p>
                  <p className="text-xs text-muted-foreground">{action.description}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
              </button>
            );
          })}
        </div>
      )}

      {/* Stats cards - square proportions */}
      {isError ? (
        <QueryError
          message="Could not load dashboard stats."
          onRetry={() => {
            dashboardQuery.refetch();
          }}
        />
      ) : isLoading ? (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Companies"
            value={totalCompanies}
            sub={`${pipeline?.approved || 0} approved`}
            icon={Building2}
            href="/companies"
          />
          <StatCard
            label="Emails Sent"
            value={stats?.total_sent || 0}
            sub={funnel ? `${funnel.drafted} drafts` : undefined}
            icon={Mail}
            href="/outreach"
          />
          <StatCard
            label="Open Rate"
            value={stats ? formatPercent(stats.open_rate) : "0%"}
            sub={stats ? `${stats.total_opened} opened` : undefined}
            icon={Eye}
            href="/analytics"
          />
          <StatCard
            label="Reply Rate"
            value={stats ? formatPercent(stats.reply_rate) : "0%"}
            sub={stats ? `${stats.total_replied} replies` : undefined}
            icon={MessageSquare}
            href="/analytics"
          />
        </div>
      )}

      {/* Pipeline + Usage - 2-column */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {pipeline && (
            <Card className="h-full">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-base">Pipeline Overview</CardTitle>
                <Link href="/analytics">
                  <Button variant="ghost" size="sm">
                    <TrendingUp className="mr-1 h-3.5 w-3.5" />
                    Analytics
                  </Button>
                </Link>
              </CardHeader>
              <CardContent>
                {(() => {
                  const stages = [
                    { label: "Suggested", value: pipeline.suggested, barColor: "bg-sky-400 dark:bg-sky-500", tip: "AI-recommended companies based on your DNA profile" },
                    { label: "Approved", value: pipeline.approved, barColor: "bg-primary", tip: "Companies you've approved for outreach" },
                    { label: "Researched", value: pipeline.researched, barColor: "bg-teal-500", tip: "Companies with completed research dossiers" },
                    { label: "Contacted", value: pipeline.contacted, barColor: "bg-violet-500", tip: "Companies where outreach has been sent" },
                  ];
                  const total = Math.max(stages.reduce((sum, s) => sum + s.value, 0), 1);
                  return (
                    <div className="space-y-4">
                      {stages.map((stage) => {
                        const pct = Math.round((stage.value / total) * 100);
                        return (
                          <Tooltip key={stage.label}>
                            <TooltipTrigger asChild>
                              <div className="space-y-1.5 cursor-help">
                                <div className="flex items-center justify-between text-sm">
                                  <span className="text-muted-foreground">{stage.label}</span>
                                  <span className="font-bold tabular-nums">{stage.value}</span>
                                </div>
                                <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                                  <div
                                    className={`h-full rounded-full transition-all ${stage.barColor}`}
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                              </div>
                            </TooltipTrigger>
                            <TooltipContent>{stage.tip}</TooltipContent>
                          </Tooltip>
                        );
                      })}

                      {/* Outreach funnel mini-summary */}
                      {funnel && (stats?.total_sent || 0) > 0 && (
                        <>
                          <div className="border-t pt-4 mt-2">
                            <p className="text-xs font-medium text-muted-foreground mb-3">Outreach Funnel</p>
                            <div className="flex items-center gap-2">
                              {[
                                { label: "Sent", value: funnel.sent },
                                { label: "Delivered", value: funnel.delivered },
                                { label: "Opened", value: funnel.opened },
                                { label: "Replied", value: funnel.replied },
                              ].map((step, i, arr) => (
                                <div key={step.label} className="flex items-center gap-2">
                                  <div className="text-center">
                                    <p className="text-lg font-bold tabular-nums">{step.value}</p>
                                    <p className="text-[10px] text-muted-foreground">{step.label}</p>
                                  </div>
                                  {i < arr.length - 1 && (
                                    <ArrowRight className="h-3 w-3 text-muted-foreground/40" />
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </>
                      )}
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
                <ArrowRight className="ml-1 h-3.5 w-3.5" />
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
                  <TableHead className="hidden sm:table-cell">Research</TableHead>
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
                    <TableCell className="hidden sm:table-cell">
                      <StatusBadge type="research" status={c.research_status} />
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

/* Square stat card - centered layout with icon, value, label */
function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  href,
}: {
  label: string;
  value: number | string;
  sub?: string;
  icon: React.ElementType;
  href: string;
}) {
  const router = useRouter();
  return (
    <Card
      className="cursor-pointer transition-all hover:shadow-md hover:border-primary/20"
      onClick={() => router.push(href)}
    >
      <CardContent className="flex flex-col items-center justify-center py-6 px-4 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 mb-3">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <p className="text-2xl font-bold tabular-nums" aria-live="polite">{value}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
        {sub && (
          <p className="text-[11px] text-muted-foreground/70 mt-1">{sub}</p>
        )}
      </CardContent>
    </Card>
  );
}
