"use client";

import { memo } from "react";
import type { ActivityFeedItem } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  Building2,
  Mail,
  Search,
  UserPlus,
  Zap,
} from "lucide-react";

const EVENT_CONFIG: Record<string, { icon: typeof Mail; color: string; label: string }> = {
  signup: { icon: UserPlus, color: "bg-primary/15 text-primary", label: "Signed up" },
  email_sent: { icon: Mail, color: "bg-secondary text-secondary-foreground", label: "Email sent" },
  company_added: { icon: Building2, color: "bg-chart-4/15 text-chart-4", label: "Company added" },
  company_discovered: { icon: Search, color: "bg-chart-5/15 text-chart-5", label: "Company discovered" },
  company_researched: { icon: Search, color: "bg-accent text-accent-foreground", label: "Research completed" },
  contact_discovered: { icon: UserPlus, color: "bg-chart-2/15 text-chart-2", label: "Contact discovered" },
  message_drafted: { icon: Mail, color: "bg-chart-1/15 text-chart-1", label: "Message drafted" },
  resume_uploaded: { icon: Zap, color: "bg-chart-3/15 text-chart-3", label: "Resume uploaded" },
  resume_parsed: { icon: Zap, color: "bg-chart-3/15 text-chart-3", label: "Resume parsed" },
};

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

interface ActivityFeedProps {
  items: ActivityFeedItem[];
}

function ActivityFeedInner({ items }: ActivityFeedProps) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        No activity yet.
      </p>
    );
  }

  return (
    <div className="space-y-1 max-h-[500px] overflow-y-auto">
      {items.map((item) => {
        const config = EVENT_CONFIG[item.event_type] || {
          icon: Zap,
          color: "bg-muted text-muted-foreground",
          label: item.event_type.replace(/_/g, " "),
        };
        const Icon = config.icon;

        return (
          <div
            key={item.id}
            className="flex items-start gap-3 rounded-md px-3 py-2 hover:bg-muted/50"
          >
            <div className={`mt-0.5 rounded-full p-1.5 ${config.color}`}>
              <Icon className="h-3 w-3" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm">
                <span className="font-medium">{item.user_name}</span>{" "}
                <span className="text-muted-foreground">{config.label}</span>
              </p>
              {item.entity_type && (
                <Badge variant="outline" className="mt-0.5 text-xs">
                  {item.entity_type}
                </Badge>
              )}
            </div>
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {formatRelativeTime(item.occurred_at)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export const ActivityFeed = memo(ActivityFeedInner);
