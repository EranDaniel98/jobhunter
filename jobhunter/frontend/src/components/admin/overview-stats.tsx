"use client";

import type { SystemOverview } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Users, Building2, Mail, UserCheck, AlertTriangle } from "lucide-react";
import { useIncidentStats } from "@/lib/hooks/use-incidents";
import { GITHUB_ISSUES_URL } from "@/lib/constants";

interface OverviewStatsProps {
  data: SystemOverview;
}

export function OverviewStats({ data }: OverviewStatsProps) {
  const { data: incidentStats } = useIncidentStats();

  const cards = [
    {
      title: "Total Users",
      value: data.total_users,
      subtitle: `${data.active_users_7d} active this week`,
      icon: Users,
    },
    {
      title: "Total Companies",
      value: data.total_companies,
      icon: Building2,
    },
    {
      title: "Messages Sent",
      value: data.total_messages_sent,
      icon: Mail,
    },
    {
      title: "Active (30d)",
      value: data.active_users_30d,
      subtitle: `${data.total_invites_used} invites used`,
      icon: UserCheck,
    },
    {
      title: "Incidents",
      value: incidentStats?.total ?? 0,
      subtitle: incidentStats?.failed ? `${incidentStats.failed} failed sync` : undefined,
      icon: AlertTriangle,
      href: GITHUB_ISSUES_URL,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => {
        const Icon = card.icon;
        const CardWrapper = card.href
          ? ({ children }: { children: React.ReactNode }) => (
              <a
                href={card.href}
                target="_blank"
                rel="noopener noreferrer"
                className="block hover:opacity-80 transition-opacity"
              >
                {children}
              </a>
            )
          : ({ children }: { children: React.ReactNode }) => <>{children}</>;

        return (
          <CardWrapper key={card.title}>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {card.title}
                </CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{card.value}</div>
                {card.subtitle && (
                  <p className="text-xs text-muted-foreground">{card.subtitle}</p>
                )}
              </CardContent>
            </Card>
          </CardWrapper>
        );
      })}
    </div>
  );
}
