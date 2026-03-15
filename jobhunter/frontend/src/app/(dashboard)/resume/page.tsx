"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as candidatesApi from "@/lib/api/candidates";
import * as applyApi from "@/lib/api/apply";
import { useResumes, useDeleteResume } from "@/lib/hooks/use-resume-history";
import { PageHeader } from "@/components/shared/page-header";
import { UploadZone } from "@/components/resume/upload-zone";
import { DnaProfile } from "@/components/resume/dna-profile";
import { SkillsGrid } from "@/components/resume/skills-grid";
import { EmptyState } from "@/components/shared/empty-state";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { CheckCircle2, Circle, FileText, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import type { CandidateDNAResponse, SkillResponse } from "@/lib/types";

function calculateCompleteness(dna: CandidateDNAResponse, skills: SkillResponse[]): { score: number; checks: { label: string; done: boolean }[] } {
  const checks = [
    { label: "Experience summary", done: !!dna.experience_summary },
    { label: "Strengths identified", done: !!(dna.strengths && dna.strengths.length > 0) },
    { label: "Gaps analyzed", done: !!(dna.gaps && dna.gaps.length > 0) },
    { label: "Career stage set", done: !!dna.career_stage },
    { label: "Skills extracted", done: skills.length > 0 },
    { label: "Transferable skills mapped", done: skills.some(s => s.category === "transferable") },
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
      <CardContent className="flex items-center gap-6 py-4">
        <div className="relative h-16 w-16 shrink-0">
          <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r={radius} fill="none" strokeWidth="10" className="stroke-muted" />
            <circle
              cx="60" cy="60" r={radius}
              fill="none" strokeWidth="10"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              className="stroke-primary transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-sm font-bold">{score}%</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 flex-1">
          {checks.map((check) => (
            <div key={check.label} className="flex items-center gap-1.5 text-xs">
              {check.done ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
              ) : (
                <Circle className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              )}
              <span className={check.done ? "" : "text-muted-foreground"}>{check.label}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ResumeHistoryCard() {
  const { data: resumes, isLoading } = useResumes();
  const deleteMutation = useDeleteResume();
  const [deleteId, setDeleteId] = useState<string | null>(null);

  if (isLoading || !resumes || resumes.length === 0) return null;

  function getFilename(path: string) {
    return path.split("/").pop() || path;
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Resume History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {resumes.map((r) => (
              <div
                key={r.id}
                className="flex items-center justify-between rounded-md border px-4 py-3"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="text-sm truncate">{getFilename(r.file_path)}</span>
                  {r.is_primary && (
                    <Badge variant="default" className="shrink-0 text-[10px]">Primary</Badge>
                  )}
                  <Badge
                    variant={r.parse_status === "completed" ? "secondary" : r.parse_status === "failed" ? "destructive" : "outline"}
                    className="shrink-0 text-[10px]"
                  >
                    {r.parse_status}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-2">
                  <span className="text-xs text-muted-foreground">
                    {r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}
                  </span>
                  {!r.is_primary && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={() => setDeleteId(r.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={!!deleteId} onOpenChange={(open) => { if (!open) setDeleteId(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete resume?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this resume. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleteId) {
                  deleteMutation.mutate(deleteId, {
                    onSuccess: () => {
                      toast.success("Resume deleted");
                      setDeleteId(null);
                    },
                    onError: () => toast.error("Failed to delete resume"),
                  });
                }
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
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
          <CardContent className="py-6 space-y-3">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">
                Processing your resume and generating DNA profile...
              </p>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div className="h-full w-1/3 rounded-full bg-primary animate-[indeterminate_1.5s_ease-in-out_infinite]" />
            </div>
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
          <ResumeHistoryCard />
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
