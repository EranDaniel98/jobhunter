"use client";

import { memo } from "react";
import type { AuditLogItem } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

const ACTION_BADGES: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  toggle_admin: { label: "Toggle Admin", variant: "default" },
  toggle_active: { label: "Toggle Active", variant: "secondary" },
  delete_user: { label: "Delete User", variant: "destructive" },
  broadcast_sent: { label: "Broadcast", variant: "outline" },
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

function formatDetails(details: Record<string, unknown> | null): string {
  if (!details) return "";
  return Object.entries(details)
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ");
}

interface AuditLogTableProps {
  items: AuditLogItem[];
}

function AuditLogTableInner({ items }: AuditLogTableProps) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        No audit log entries yet.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Admin</TableHead>
          <TableHead>Action</TableHead>
          <TableHead>Target User</TableHead>
          <TableHead>Details</TableHead>
          <TableHead>When</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => {
          const badge = ACTION_BADGES[item.action] || {
            label: item.action.replace(/_/g, " "),
            variant: "outline" as const,
          };

          return (
            <TableRow key={item.id}>
              <TableCell>
                <div className="font-medium">{item.admin_name || "System"}</div>
                <div className="text-xs text-muted-foreground">
                  {item.admin_email || ""}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={badge.variant}>{badge.label}</Badge>
              </TableCell>
              <TableCell>
                {item.target_name ? (
                  <>
                    <div className="font-medium">{item.target_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {item.target_email}
                    </div>
                  </>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                {formatDetails(item.details)}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                {formatRelativeTime(item.created_at)}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export const AuditLogTable = memo(AuditLogTableInner);
