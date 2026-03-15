import type { CandidateDNAResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface DnaProfileProps {
  dna: CandidateDNAResponse;
}

export function DnaProfile({ dna }: DnaProfileProps) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle>Experience Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {dna.experience_summary || "No summary available"}
          </p>
          {dna.career_stage && (
            <div className="mt-3">
              <Badge variant="outline">{dna.career_stage}</Badge>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-l-4 border-l-green-500">
        <CardHeader>
          <CardTitle className="text-green-600 dark:text-green-400">Strengths</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-2">
            {dna.strengths?.map((s, i) => (
              <Badge key={i} className="bg-green-500/15 text-green-700 dark:text-green-300 whitespace-normal text-left h-auto py-1 text-sm">
                {s}
              </Badge>
            )) || <span className="text-sm text-muted-foreground">None identified</span>}
          </div>
        </CardContent>
      </Card>

      <Card className="border-l-4 border-l-red-500">
        <CardHeader>
          <CardTitle className="text-red-600 dark:text-red-400">Gaps</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-2">
            {dna.gaps?.map((g, i) => (
              <Badge key={i} className="bg-red-500/15 text-red-700 dark:text-red-300 whitespace-normal text-left h-auto py-1 text-sm">
                {g}
              </Badge>
            )) || <span className="text-sm text-muted-foreground">None identified</span>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
