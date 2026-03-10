"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as candidatesApi from "@/lib/api/candidates";
import * as applyApi from "@/lib/api/apply";
import { PageHeader } from "@/components/shared/page-header";
import { UploadZone } from "@/components/resume/upload-zone";
import { DnaProfile } from "@/components/resume/dna-profile";
import { SkillsGrid } from "@/components/resume/skills-grid";
import { EmptyState } from "@/components/shared/empty-state";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Circle, FileText, Loader2 } from "lucide-react";
import type { CandidateDNAResponse, SkillResponse } from "@/lib/types";

function calculateCompleteness(dna: CandidateDNAResponse, skills: SkillResponse[]): { score: number; checks: { label: string; done: boolean }[] } {
  const checks = [
    { label: "Experience summary", done: !!dna.experience_summary },
    { label: "Strengths identified", done: !!(dna.strengths && dna.strengths.length > 0) },
    { label: "Gaps analyzed", done: !!(dna.gaps && dna.gaps.length > 0) },
    { label: "Career stage set", done: !!dna.career_stage },
    { label: "Skills extracted", done: skills.length > 0 },
    { label: "Transferable skills mapped", done: !!(dna.transferable_skills && Object.keys(dna.transferable_skills).length > 0) },
  ];
  const done = checks.filter(c => c.done).length;
  return { score: Math.round((done / checks.length) * 100), checks };
}

function CompletenessCard({ dna, skills }: { dna: CandidateDNAResponse; skills: SkillResponse[] }) {
  const { score, checks } = calculateCompleteness(dna, skills);
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <Card>
      <CardContent className="flex flex-col items-center py-6">
        <div className="relative h-32 w-32">
          <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r={radius} fill="none" strokeWidth="8" className="stroke-muted" />
            <circle
              cx="60" cy="60" r={radius}
              fill="none" strokeWidth="8"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              className="stroke-primary transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold">{score}%</span>
            <span className="text-xs text-muted-foreground">Complete</span>
          </div>
        </div>
        <div className="mt-4 w-full space-y-2">
          {checks.map((check) => (
            <div key={check.label} className="flex items-center gap-2 text-sm">
              {check.done ? (
                <CheckCircle2 className="h-4 w-4 text-primary shrink-0" />
              ) : (
                <Circle className="h-4 w-4 text-muted-foreground shrink-0" />
              )}
              <span className={check.done ? "" : "text-muted-foreground"}>{check.label}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ResumePage() {
  const [uploadedRecently, setUploadedRecently] = useState(false);

  const dnaQuery = useQuery({
    queryKey: ["dna"],
    queryFn: candidatesApi.getDNA,
    retry: 1,
    refetchInterval: (query) =>
      !query.state.data && uploadedRecently ? 3000 : false,
  });

  const skillsQuery = useQuery({
    queryKey: ["skills"],
    queryFn: candidatesApi.getSkills,
    retry: 1,
    refetchInterval: (query) =>
      !query.state.data?.length && uploadedRecently ? 3000 : false,
  });

  const postingsQuery = useQuery({
    queryKey: ["postings"],
    queryFn: () => applyApi.listPostings(),
  });

  const hasDna = !!dnaQuery.data;
  const isLoading = dnaQuery.isLoading;

  // Calculate skills gap
  const userSkillNames = new Set((skillsQuery.data || []).map(s => s.name.toLowerCase()));
  const allRequiredSkills: Record<string, number> = {};
  (postingsQuery.data?.postings || []).forEach(p => {
    if (p.parsed_requirements) {
      const reqs = p.parsed_requirements as Record<string, unknown>;
      const skills = (reqs.required_skills || reqs.skills || []) as string[];
      skills.forEach((s: string) => {
        const lower = s.toLowerCase();
        if (!userSkillNames.has(lower)) {
          allRequiredSkills[s] = (allRequiredSkills[s] || 0) + 1;
        }
      });
    }
  });
  const gapSkills = Object.entries(allRequiredSkills)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Resume & DNA"
        description="Upload your resume to generate your candidate DNA profile"
      />

      <UploadZone onUploadSuccess={() => setUploadedRecently(true)} />

      {isLoading && (
        <div className="grid gap-4 md:grid-cols-2">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      )}

      {!isLoading && uploadedRecently && !hasDna && (
        <Card>
          <CardContent className="flex items-center gap-3 py-6">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">
              Processing your resume and generating DNA profile...
            </p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !uploadedRecently && !hasDna && (
        <EmptyState
          icon={FileText}
          title="No DNA profile yet"
          description="Upload your resume to get started. We'll analyze it and generate your candidate DNA profile."
        />
      )}

      {hasDna && dnaQuery.data && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <CompletenessCard dna={dnaQuery.data} skills={skillsQuery.data || []} />
            <div className="md:col-span-2">
              <DnaProfile dna={dnaQuery.data} />
            </div>
          </div>
          <SkillsGrid skills={skillsQuery.data?.length ? skillsQuery.data : dnaQuery.data.skills} />
          {gapSkills.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Skills Gap Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Skills frequently required in job postings that are not in your profile:
                </p>
                <div className="flex flex-wrap gap-2">
                  {gapSkills.map(([skill, count]) => (
                    <Badge key={skill} variant="outline" className="text-sm">
                      {skill}
                      <span className="ml-1 text-xs text-muted-foreground">({count})</span>
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
