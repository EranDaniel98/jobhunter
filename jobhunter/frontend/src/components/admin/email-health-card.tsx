"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Clock, ChevronDown, ChevronUp, RefreshCw, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useEmailHealth, useRefreshEmailHealth } from "@/lib/hooks/use-admin";
import type { DnsCheckStatus, DnsCheckResult } from "@/lib/types";

/* ── Status helpers ── */

function statusColor(status: DnsCheckStatus): string {
  switch (status) {
    case "pass":
      return "text-emerald-500";
    case "warning":
      return "text-amber-500";
    case "fail":
      return "text-destructive";
    case "timeout":
      return "text-muted-foreground";
  }
}

function StatusIcon({ status }: { status: DnsCheckStatus }) {
  const cls = `h-4 w-4 ${statusColor(status)}`;
  switch (status) {
    case "pass":
      return <CheckCircle2 className={cls} />;
    case "warning":
      return <AlertTriangle className={cls} />;
    case "fail":
      return <XCircle className={cls} />;
    case "timeout":
      return <Clock className={cls} />;
  }
}

function OverallBadge({ status }: { status: DnsCheckStatus }) {
  const variants: Record<DnsCheckStatus, string> = {
    pass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    warning: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    fail: "bg-destructive/10 text-destructive border-destructive/20",
    timeout: "bg-muted text-muted-foreground border-border",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${variants[status]}`}
    >
      {status}
    </span>
  );
}

/* ── DNS row ── */

interface DnsRowProps {
  label: string;
  check: DnsCheckResult;
}

function DnsRow({ label, check }: DnsRowProps) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = !!(check.record || check.recommendation || check.selector);

  return (
    <div className="rounded-lg border border-border bg-muted/30 px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusIcon status={check.status} />
          <span className="text-sm font-medium text-foreground">{label}</span>
          {check.selector && (
            <span className="text-xs text-muted-foreground">({check.selector})</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold capitalize ${statusColor(check.status)}`}>
            {check.status}
          </span>
          {hasDetail && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label={expanded ? "Collapse details" : "Expand details"}
            >
              {expanded ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </div>
      </div>

      {expanded && hasDetail && (
        <div className="mt-2 space-y-1.5 pl-6">
          {check.record && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Raw Record
              </p>
              <code className="mt-0.5 block break-all rounded bg-muted px-2 py-1 text-[11px] font-mono text-foreground/80">
                {check.record}
              </code>
            </div>
          )}
          {check.recommendation && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Recommendation
              </p>
              <p className="mt-0.5 text-xs text-amber-600 dark:text-amber-400">
                {check.recommendation}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Main card ── */

export function EmailHealthCard() {
  const query = useEmailHealth();
  const refresh = useRefreshEmailHealth();

  const data = query.data;
  const isLoading = query.isLoading;
  const isRefreshing = refresh.isPending;

  function handleRefresh() {
    refresh.mutate();
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex items-center gap-3">
          <CardTitle className="text-base">Email Deliverability</CardTitle>
          {data && <OverallBadge status={data.overall} />}
        </div>
        <div className="flex items-center gap-2">
          {data?.domain && (
            <span className="text-xs text-muted-foreground hidden sm:inline">
              {data.domain}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing || isLoading}
            className="h-7 px-2.5"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`}
            />
            <span className="ml-1.5 text-xs">Refresh</span>
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-2">
        {isLoading ? (
          <div className="space-y-2">
            {["SPF", "DKIM", "DMARC"].map((label) => (
              <div
                key={label}
                className="h-11 animate-pulse rounded-lg bg-muted"
              />
            ))}
          </div>
        ) : data ? (
          <>
            <DnsRow label="SPF" check={data.spf} />
            <DnsRow label="DKIM" check={data.dkim} />
            <DnsRow label="DMARC" check={data.dmarc} />

            <div className="flex items-center justify-between pt-1">
              <p className="text-[11px] text-muted-foreground">
                Last checked:{" "}
                {new Date(data.checked_at).toLocaleString(undefined, {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </p>
              <a
                href="/docs/email-domain-setup.md"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
              >
                Setup guide
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </>
        ) : (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Failed to load DNS health data.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
