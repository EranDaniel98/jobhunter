"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as candidatesApi from "@/lib/api/candidates";
import { UploadZone } from "@/components/resume/upload-zone";
import { Card, CardContent } from "@/components/ui/card";
import { Info, Loader2, CheckCircle2 } from "lucide-react";

export function StepResume() {
  const [uploadDone, setUploadDone] = useState(false);

  const dnaQuery = useQuery({
    queryKey: ["dna"],
    queryFn: candidatesApi.getDNA,
    enabled: uploadDone,
    refetchInterval: (query) => (query.state.data ? false : 3000),
    retry: 1,
  });

  const hasDna = !!dnaQuery.data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Upload your resume</h2>
        <p className="mt-1 text-muted-foreground">
          This is optional — you can always do it later from the Resume &amp; DNA page.
        </p>
      </div>

      {/* Why this matters */}
      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="flex items-start gap-3 py-4">
          <Info className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div className="space-y-1">
            <p className="text-sm font-medium">Why upload your resume?</p>
            <p className="text-sm text-muted-foreground">
              Your resume powers our AI engine. We analyze it to build your <strong>Candidate DNA</strong> — a
              profile of your strengths, skills, transferable abilities, and gaps. This profile drives
              personalized company matching, outreach message generation, and skills gap analysis.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Upload zone */}
      {!hasDna && (
        <UploadZone onUploadSuccess={() => setUploadDone(true)} />
      )}

      {/* Processing state */}
      {uploadDone && !hasDna && (
        <Card>
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <div>
              <p className="text-sm font-medium">Building your Candidate DNA...</p>
              <p className="text-xs text-muted-foreground">
                This usually takes 30-60 seconds. You can continue to the next step while we process.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Success state */}
      {hasDna && (
        <Card className="border-green-500/30 bg-green-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <div>
              <p className="text-sm font-medium text-green-700 dark:text-green-400">
                Candidate DNA profile created!
              </p>
              <p className="text-xs text-muted-foreground">
                Your strengths, skills, and growth areas have been identified. View them on the Resume &amp; DNA page.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
