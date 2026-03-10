"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusBadge } from "@/components/shared/status-badge";
import { Check, X } from "lucide-react";
import type { CompanyResponse } from "@/lib/types";

/* ---------- Fit Score Ring ---------- */

function FitScoreRing({ score }: { score: number | null }) {
  const value = score ?? 0;
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  return (
    <div className="relative h-16 w-16 shrink-0">
      <svg className="h-full w-full -rotate-90" viewBox="0 0 64 64">
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="4"
          className="stroke-muted"
        />
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="4"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="stroke-primary transition-all duration-500"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">
        {value > 0 ? Math.round(value) : "\u2014"}
      </span>
    </div>
  );
}

/* ---------- Company Card ---------- */

interface CompanyCardProps {
  company: CompanyResponse;
  selected: boolean;
  onSelect: (id: string, checked: boolean) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  approving: boolean;
  rejecting: boolean;
}

export function CompanyCard({
  company,
  selected,
  onSelect,
  onApprove,
  onReject,
  approving,
  rejecting,
}: CompanyCardProps) {
  const router = useRouter();
  const techStack = company.tech_stack ?? [];
  const visibleTech = techStack.slice(0, 3);
  const extraCount = techStack.length - 3;

  return (
    <Card
      className="group relative flex min-h-[280px] cursor-pointer flex-col transition-shadow hover:shadow-lg"
      onClick={() => router.push(`/companies/${company.id}`)}
    >
      {/* Checkbox */}
      <div
        className="absolute left-3 top-3 z-10"
        onClick={(e) => e.stopPropagation()}
      >
        <Checkbox
          checked={selected}
          onCheckedChange={(v) => onSelect(company.id, !!v)}
          aria-label={`Select ${company.name}`}
        />
      </div>

      <CardContent className="flex flex-1 flex-col gap-3 pt-10 pb-4">
        {/* Header row: name + fit ring */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-base font-bold leading-tight">
              {company.name}
            </h3>
            {company.location_hq && (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {company.location_hq}
              </p>
            )}
          </div>
          <FitScoreRing score={company.fit_score} />
        </div>

        {/* Description snippet */}
        {company.description && (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {company.description.length > 80
              ? company.description.slice(0, 80) + "\u2026"
              : company.description}
          </p>
        )}

        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge type="company" status={company.status} />
          {company.funding_stage && (
            <Badge variant="secondary" className="text-[10px]">
              {company.funding_stage}
            </Badge>
          )}
        </div>

        {/* Tech stack tags */}
        {visibleTech.length > 0 && (
          <div className="mt-auto flex flex-wrap gap-1">
            {visibleTech.map((t) => (
              <Badge
                key={t}
                variant="outline"
                className="text-[10px] font-normal"
              >
                {t}
              </Badge>
            ))}
            {extraCount > 0 && (
              <Badge variant="outline" className="text-[10px] font-normal">
                +{extraCount}
              </Badge>
            )}
          </div>
        )}

        {/* Approve / Reject for suggested */}
        {company.status === "suggested" && (
          <div
            className="flex gap-1 pt-1"
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              size="sm"
              variant="ghost"
              className="h-7 flex-1 text-primary hover:bg-primary/10 hover:text-primary"
              onClick={() => onApprove(company.id)}
              disabled={approving}
            >
              <Check className="mr-1 h-3.5 w-3.5" />
              Approve
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 flex-1 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={() => onReject(company.id)}
              disabled={rejecting}
            >
              <X className="mr-1 h-3.5 w-3.5" />
              Reject
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
