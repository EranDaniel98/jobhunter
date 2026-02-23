"use client";

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
  signup: { icon: UserPlus, color: "bg-green-100 text-green-800", label: "Signed up" },
  email_sent: { icon: Mail, color: "bg-blue-100 text-blue-800", label: "Email sent" },
  company_added: { icon: Building2, color: "bg-purple-100 text-purple-800", label: "Company added" },
  company_discovered: { icon: Search, color: "bg-orange-100 text-orange-800", label: "Company discovered" },
  company_researched: { icon: Search, color: "bg-yellow-100 text-yellow-800", label: "Research completed" },
  contact_discovered: { icon: UserPlus, color: "bg-teal-100 text-teal-800", label: "Contact discovered" },
  message_drafted: { icon: Mail, color: "bg-indigo-100 text-indigo-800", label: "Message drafted" },
  resume_uploaded: { icon: Zap, color: "bg-pink-100 text-pink-800", label: "Resume uploaded" },
  resume_parsed: { icon: Zap, color: "bg-pink-100 text-pink-800", label: "Resume parsed" },
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

export function ActivityFeed({ items }: ActivityFeedProps) {
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
          color: "bg-gray-100 text-gray-800",
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
