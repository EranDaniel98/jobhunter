"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAnalyticsDashboard, useRefreshInsights, useMarkInsightRead } from "@/lib/hooks/use-analytics-insights";
import { BarChart3, RefreshCw, Loader2, TrendingUp, Mail, Building2, Lightbulb, Zap, AlertTriangle, Download, CheckCheck, Linkedin } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryError } from "@/components/shared/query-error";
import { formatPercent } from "@/lib/utils";
import type { AnalyticsInsightResponse } from "@/lib/types";

const FUNNEL_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "hsl(0, 84%, 60%)",
];

const PIE_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
];

const SEVERITY_STYLES: Record<string, { border: string; bg: string; badge: string; badgeText: string }> = {
  info: {
    border: "border-l-secondary",
    bg: "hover:bg-secondary/50",
    badge: "bg-secondary text-secondary-foreground",
    badgeText: "Info",
  },
  success: {
    border: "border-l-primary",
    bg: "hover:bg-primary/5",
    badge: "bg-primary/15 text-primary",
    badgeText: "Success",
  },
  warning: {
    border: "border-l-chart-3",
    bg: "hover:bg-chart-3/10",
    badge: "bg-chart-3/15 text-chart-3",
    badgeText: "Warning",
  },
  action_needed: {
    border: "border-l-destructive",
    bg: "hover:bg-destructive/5",
    badge: "bg-destructive/15 text-destructive",
    badgeText: "Action Needed",
  },
};

function getSeverityStyle(severity: string) {
  return SEVERITY_STYLES[severity] || SEVERITY_STYLES.info;
}

function formatRelativeTime(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/* ------------------------------------------------------------------ */
/*  Loading skeleton                                                   */
/* ------------------------------------------------------------------ */
function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" />
      {/* Stat cards skeleton */}
      <div className="grid gap-4 grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="flex flex-col items-center justify-center py-6 space-y-3">
              <Skeleton className="h-10 w-10 rounded-full" />
              <Skeleton className="h-8 w-12" />
              <Skeleton className="h-3 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
      {/* Charts skeleton */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-[250px] w-full" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-[250px] w-full" />
          </CardContent>
        </Card>
      </div>
      {/* Insights skeleton */}
      <Card>
        <CardContent className="space-y-3 pt-6">
          <Skeleton className="h-5 w-40" />
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Insight card                                                       */
/* ------------------------------------------------------------------ */
function InsightCard({
  insight,
  onMarkRead,
}: {
  insight: AnalyticsInsightResponse;
  onMarkRead: (id: string) => void;
}) {
  const style = getSeverityStyle(insight.severity);

  return (
    <button
      onClick={() => {
        if (!insight.is_read) onMarkRead(insight.id);
      }}
      className={`w-full text-left rounded-lg border border-l-4 ${style.border} p-4 transition-colors ${style.bg} ${
        !insight.is_read ? "bg-muted/40" : "opacity-75"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style.badge}`}>
              {style.badgeText}
            </span>
            {!insight.is_read && (
              <span className="inline-flex h-2 w-2 rounded-full bg-primary" />
            )}
            <span className="text-xs text-muted-foreground ml-auto flex-shrink-0">
              {formatRelativeTime(insight.created_at)}
            </span>
          </div>
          <h4 className="text-sm font-semibold leading-tight">{insight.title}</h4>
          <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{insight.body}</p>
        </div>
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */
export default function AnalyticsPage() {
  const router = useRouter();
  const dashboardQuery = useAnalyticsDashboard();
  const refreshMutation = useRefreshInsights();
  const markReadMutation = useMarkInsightRead();
  const [insightFilter, setInsightFilter] = useState<string>("all");

  if (dashboardQuery.isLoading) {
    return <DashboardSkeleton />;
  }

  if (dashboardQuery.isError) {
    return (
      <div className="space-y-6">
        <PageHeader title="Analytics" />
        <QueryError
          message="Could not load analytics data."
          onRetry={() => dashboardQuery.refetch()}
        />
      </div>
    );
  }

  const dashboard = dashboardQuery.data;
  const hasOutreachData = dashboard && dashboard.outreach.total_sent > 0;
  const hasPipelineData =
    dashboard &&
    (dashboard.pipeline.suggested > 0 ||
      dashboard.pipeline.approved > 0 ||
      dashboard.pipeline.researched > 0 ||
      dashboard.pipeline.contacted > 0);
  const hasAnyData = hasOutreachData || hasPipelineData;

  const unreadCount = dashboard?.insights.filter((i) => !i.is_read).length ?? 0;

  // Funnel chart data (includes Bounced)
  const funnelData = dashboard
    ? [
        { name: "Drafted", value: dashboard.funnel.drafted },
        { name: "Sent", value: dashboard.funnel.sent },
        { name: "Delivered", value: dashboard.funnel.delivered },
        { name: "Opened", value: dashboard.funnel.opened },
        { name: "Replied", value: dashboard.funnel.replied },
        { name: "Bounced", value: dashboard.funnel.bounced },
      ]
    : [];

  // Pipeline pie chart data
  const pipelineData = dashboard
    ? [
        { name: "Suggested", value: dashboard.pipeline.suggested },
        { name: "Approved", value: dashboard.pipeline.approved },
        { name: "Researched", value: dashboard.pipeline.researched },
        { name: "Contacted", value: dashboard.pipeline.contacted },
      ].filter((d) => d.value > 0)
    : [];

  // Derived stats
  const efficiency = dashboard
    ? dashboard.outreach.total_replied > 0
      ? (dashboard.outreach.total_sent / dashboard.outreach.total_replied).toFixed(1)
      : "\u2014"
    : "\u2014";
  const bounceRate = dashboard
    ? dashboard.funnel.sent > 0
      ? `${((dashboard.funnel.bounced / dashboard.funnel.sent) * 100).toFixed(1)}%`
      : "0%"
    : "0%";
  const totalCompanies = dashboard
    ? dashboard.pipeline.suggested +
      dashboard.pipeline.approved +
      dashboard.pipeline.researched +
      dashboard.pipeline.contacted
    : 0;

  // CSV export
  function exportCsv() {
    if (!dashboard) return;
    const rows = [
      ["Metric", "Value"],
      ["Total Sent", String(dashboard.outreach.total_sent)],
      ["Total Opened", String(dashboard.outreach.total_opened)],
      ["Total Replied", String(dashboard.outreach.total_replied)],
      ["Open Rate", formatPercent(dashboard.outreach.open_rate)],
      ["Reply Rate", formatPercent(dashboard.outreach.reply_rate)],
      ["Drafted", String(dashboard.funnel.drafted)],
      ["Sent", String(dashboard.funnel.sent)],
      ["Delivered", String(dashboard.funnel.delivered)],
      ["Opened", String(dashboard.funnel.opened)],
      ["Replied", String(dashboard.funnel.replied)],
      ["Bounced", String(dashboard.funnel.bounced)],
      ["Companies Suggested", String(dashboard.pipeline.suggested)],
      ["Companies Approved", String(dashboard.pipeline.approved)],
      ["Companies Researched", String(dashboard.pipeline.researched)],
      ["Companies Contacted", String(dashboard.pipeline.contacted)],
    ];
    const csv = rows.map(r => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "analytics-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  // Mark all insights read
  function markAllRead() {
    if (!dashboard) return;
    dashboard.insights
      .filter((i) => !i.is_read)
      .forEach((i) => markReadMutation.mutate(i.id));
  }

  // Channel breakdown data
  const byChannel = dashboard?.outreach.by_channel as
    | Record<string, { sent?: number; opened?: number; replied?: number }>
    | undefined;

  // Insight type filter
  const insightTypes = dashboard
    ? Array.from(new Set(dashboard.insights.map((i) => i.insight_type).filter(Boolean)))
    : [];
  const filteredInsights = dashboard
    ? dashboard.insights.filter(
        (i) => insightFilter === "all" || i.insight_type === insightFilter,
      )
    : [];

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Track your job search pipeline and outreach performance" dataTour="page-header">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={exportCsv} disabled={!dashboard}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
          >
            {refreshMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Refresh Insights
          </Button>
        </div>
      </PageHeader>

      {!hasAnyData ? (
        <EmptyState
          icon={BarChart3}
          title="No data yet"
          description="Start discovering companies and sending outreach to see your analytics dashboard come to life."
          action={{
            label: "Discover Companies",
            onClick: () => router.push("/companies"),
          }}
        />
      ) : (
        <>
          {/* ---- Stat cards (square, centered) ---- */}
          <div className="grid gap-4 grid-cols-3 lg:grid-cols-6">
            {/* Total Sent */}
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-6">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-chart-2/15 mb-3">
                  <Mail className="h-5 w-5 text-chart-2" />
                </div>
                <div className="text-2xl font-bold">{dashboard?.outreach.total_sent ?? 0}</div>
                <p className="text-xs font-medium text-muted-foreground mt-1">Total Sent</p>
                <p className="text-[10px] text-muted-foreground">outreach messages</p>
              </CardContent>
            </Card>

            {/* Open Rate */}
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-6">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-chart-3/15 mb-3">
                  <TrendingUp className="h-5 w-5 text-chart-3" />
                </div>
                <div className="text-2xl font-bold">
                  {dashboard ? formatPercent(dashboard.outreach.open_rate) : "0%"}
                </div>
                <p className="text-xs font-medium text-muted-foreground mt-1">Open Rate</p>
                <p className="text-[10px] text-muted-foreground">{dashboard?.outreach.total_opened ?? 0} opened</p>
              </CardContent>
            </Card>

            {/* Reply Rate */}
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-6">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-chart-5/15 mb-3">
                  <TrendingUp className="h-5 w-5 text-chart-5" />
                </div>
                <div className="text-2xl font-bold">
                  {dashboard ? formatPercent(dashboard.outreach.reply_rate) : "0%"}
                </div>
                <p className="text-xs font-medium text-muted-foreground mt-1">Reply Rate</p>
                <p className="text-[10px] text-muted-foreground">{dashboard?.outreach.total_replied ?? 0} replied</p>
              </CardContent>
            </Card>

            {/* Companies */}
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-6">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 mb-3">
                  <Building2 className="h-5 w-5 text-primary" />
                </div>
                <div className="text-2xl font-bold">{totalCompanies}</div>
                <p className="text-xs font-medium text-muted-foreground mt-1">Companies</p>
                <p className="text-[10px] text-muted-foreground">in pipeline</p>
              </CardContent>
            </Card>

            {/* Efficiency */}
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-6">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-chart-4/15 mb-3">
                  <Zap className="h-5 w-5 text-chart-4" />
                </div>
                <div className="text-2xl font-bold">{efficiency}</div>
                <p className="text-xs font-medium text-muted-foreground mt-1">Efficiency</p>
                <p className="text-[10px] text-muted-foreground">msgs per reply</p>
              </CardContent>
            </Card>

            {/* Bounce Rate */}
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-6">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-destructive/15 mb-3">
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                </div>
                <div className="text-2xl font-bold">{bounceRate}</div>
                <p className="text-xs font-medium text-muted-foreground mt-1">Bounce Rate</p>
                <p className="text-[10px] text-muted-foreground">{dashboard?.funnel.bounced ?? 0} bounced</p>
              </CardContent>
            </Card>
          </div>

          {/* ---- Charts ---- */}
          <div className="grid gap-6 md:grid-cols-2">
            {/* Outreach Funnel */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Outreach Funnel
                </CardTitle>
                <CardDescription>Message progression from draft to reply</CardDescription>
              </CardHeader>
              <CardContent>
                {hasOutreachData ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={funnelData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {funnelData.map((_, index) => (
                          <Cell key={index} fill={FUNNEL_COLORS[index]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-[250px] items-center justify-center text-sm text-muted-foreground">
                    No outreach data yet. Send some messages to see the funnel.
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Pipeline Distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5" />
                  Pipeline Distribution
                </CardTitle>
                <CardDescription>Company stages across your pipeline</CardDescription>
              </CardHeader>
              <CardContent>
                {pipelineData.length > 0 ? (
                  <div className="flex flex-col items-center">
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie
                          data={pipelineData}
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={80}
                          paddingAngle={3}
                          dataKey="value"
                        >
                          {pipelineData.map((_, index) => (
                            <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="mt-2 flex flex-wrap justify-center gap-3">
                      {pipelineData.map((entry, index) => (
                        <div key={entry.name} className="flex items-center gap-1.5 text-xs">
                          <span
                            className="inline-block h-3 w-3 rounded-full"
                            style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }}
                          />
                          <span className="text-muted-foreground">
                            {entry.name}: <span className="font-medium text-foreground">{entry.value}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex h-[250px] items-center justify-center text-sm text-muted-foreground">
                    No companies in pipeline yet. Discover companies to get started.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* ---- Channel Breakdown ---- */}
          {byChannel && Object.keys(byChannel).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Mail className="h-5 w-5" />
                  Channel Breakdown
                </CardTitle>
                <CardDescription>Performance comparison across outreach channels</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-5">
                  {Object.entries(byChannel).map(([channel, stats]) => {
                    const sent = stats?.sent ?? 0;
                    const opened = stats?.opened ?? 0;
                    const replied = stats?.replied ?? 0;
                    const maxVal = Math.max(sent, 1);
                    return (
                      <div key={channel} className="space-y-2">
                        <div className="flex items-center gap-2">
                          {channel === "linkedin" ? (
                            <Linkedin className="h-4 w-4 text-chart-1" />
                          ) : (
                            <Mail className="h-4 w-4 text-chart-2" />
                          )}
                          <span className="text-sm font-medium capitalize">{channel}</span>
                        </div>
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2">
                            <span className="w-16 text-xs text-muted-foreground">Sent</span>
                            <div className="flex-1 h-4 rounded-full bg-muted overflow-hidden">
                              <div
                                className="h-full rounded-full bg-chart-2 transition-all"
                                style={{ width: `${(sent / maxVal) * 100}%` }}
                              />
                            </div>
                            <span className="w-8 text-xs font-medium text-right">{sent}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-16 text-xs text-muted-foreground">Opened</span>
                            <div className="flex-1 h-4 rounded-full bg-muted overflow-hidden">
                              <div
                                className="h-full rounded-full bg-chart-3 transition-all"
                                style={{ width: `${(opened / maxVal) * 100}%` }}
                              />
                            </div>
                            <span className="w-8 text-xs font-medium text-right">{opened}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-16 text-xs text-muted-foreground">Replied</span>
                            <div className="flex-1 h-4 rounded-full bg-muted overflow-hidden">
                              <div
                                className="h-full rounded-full bg-chart-5 transition-all"
                                style={{ width: `${(replied / maxVal) * 100}%` }}
                              />
                            </div>
                            <span className="w-8 text-xs font-medium text-right">{replied}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* ---- AI Insights Feed ---- */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Lightbulb className="h-5 w-5" />
                    AI Insights
                    {unreadCount > 0 && (
                      <Badge variant="secondary" className="ml-1">
                        {unreadCount} new
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription className="mt-1">
                    Personalized analysis and recommendations for your job search
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  {unreadCount > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={markAllRead}
                      disabled={markReadMutation.isPending}
                    >
                      <CheckCheck className="mr-2 h-4 w-4" />
                      Mark all read
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => refreshMutation.mutate()}
                    disabled={refreshMutation.isPending}
                  >
                    {refreshMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-2 h-4 w-4" />
                    )}
                    Analyze
                  </Button>
                </div>
              </div>

              {/* Insight type filter pills */}
              {insightTypes.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  <Button
                    variant={insightFilter === "all" ? "default" : "outline"}
                    size="sm"
                    className="h-7 text-xs px-3 rounded-full"
                    onClick={() => setInsightFilter("all")}
                  >
                    All
                  </Button>
                  {insightTypes.map((t) => (
                    <Button
                      key={t}
                      variant={insightFilter === t ? "default" : "outline"}
                      size="sm"
                      className="h-7 text-xs px-3 rounded-full capitalize"
                      onClick={() => setInsightFilter(t)}
                    >
                      {t.replace(/_/g, " ")}
                    </Button>
                  ))}
                </div>
              )}
            </CardHeader>
            <CardContent>
              {filteredInsights.length > 0 ? (
                <div className="max-h-[480px] space-y-3 overflow-y-auto pr-1">
                  {filteredInsights.map((insight) => (
                    <InsightCard
                      key={insight.id}
                      insight={insight}
                      onMarkRead={(id) => markReadMutation.mutate(id)}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <div className="mb-3 rounded-full bg-muted p-3">
                    <Lightbulb className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <p className="text-sm font-medium">No insights yet</p>
                  <p className="mt-1 max-w-xs text-xs text-muted-foreground">
                    Click &quot;Analyze&quot; to generate AI-powered insights about your job search progress.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
