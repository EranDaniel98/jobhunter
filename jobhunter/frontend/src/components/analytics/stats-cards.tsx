import type { OutreachStatsResponse } from "@/lib/types";
import { formatPercent } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mail, Eye, MessageSquare, AlertTriangle } from "lucide-react";

interface StatsCardsProps {
  stats: OutreachStatsResponse;
}

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: "Total Sent",
      value: stats.total_sent,
      icon: Mail,
    },
    {
      title: "Open Rate",
      value: formatPercent(stats.open_rate),
      subtitle: `${stats.total_opened} opened`,
      icon: Eye,
    },
    {
      title: "Reply Rate",
      value: formatPercent(stats.reply_rate),
      subtitle: `${stats.total_replied} replied`,
      icon: MessageSquare,
    },
    {
      title: "Bounced",
      value: stats.total_sent - stats.total_opened,
      icon: AlertTriangle,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <Card key={card.title}>
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
        );
      })}
    </div>
  );
}
