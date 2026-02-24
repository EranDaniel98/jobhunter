"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as candidatesApi from "@/lib/api/candidates";
import { PageHeader } from "@/components/shared/page-header";
import { UploadZone } from "@/components/resume/upload-zone";
import { DnaProfile } from "@/components/resume/dna-profile";
import { SkillsGrid } from "@/components/resume/skills-grid";
import { EmptyState } from "@/components/shared/empty-state";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { FileText, Loader2 } from "lucide-react";

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
      !query.state.data && uploadedRecently ? 3000 : false,
  });

  const hasDna = !!dnaQuery.data;
  const isLoading = dnaQuery.isLoading;

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
          <DnaProfile dna={dnaQuery.data} />
          <SkillsGrid skills={skillsQuery.data || dnaQuery.data.skills} />
        </>
      )}
    </div>
  );
}
