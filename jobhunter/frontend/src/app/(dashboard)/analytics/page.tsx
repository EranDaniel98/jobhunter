"use client";

import { useFunnel, useOutreachStats, usePipelineStats } from "@/lib/hooks/use-analytics";
import { PageHeader } from "@/components/shared/page-header";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { FunnelChart } from "@/components/analytics/funnel-chart";
import { PipelineChart } from "@/components/analytics/pipeline-chart";
import { StatsCards } from "@/components/analytics/stats-cards";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";

export default function AnalyticsPage() {
  const funnelQuery = useFunnel();
  const statsQuery = useOutreachStats();
  const pipelineQuery = usePipelineStats();

  const isLoading = funnelQuery.isLoading || statsQuery.isLoading || pipelineQuery.isLoading;
  const hasData = statsQuery.data && statsQuery.data.total_sent > 0;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Analytics" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Track your job search pipeline and outreach performance" />

      {!hasData && pipelineQuery.data?.suggested === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="No data yet"
          description="Start sending outreach to see your analytics."
        />
      ) : (
        <>
          {statsQuery.data && <StatsCards stats={statsQuery.data} />}

          <div className="grid gap-6 md:grid-cols-2">
            {pipelineQuery.data && (
              <Card>
                <CardHeader>
                  <CardTitle>Pipeline</CardTitle>
                </CardHeader>
                <CardContent>
                  <PipelineChart data={pipelineQuery.data} />
                </CardContent>
              </Card>
            )}

            {funnelQuery.data && (
              <Card>
                <CardHeader>
                  <CardTitle>Outreach Funnel</CardTitle>
                </CardHeader>
                <CardContent>
                  <FunnelChart data={funnelQuery.data} />
                </CardContent>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}
