import type { CandidateDNAResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface DnaProfileProps {
  dna: CandidateDNAResponse;
}

export function DnaProfile({ dna }: DnaProfileProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
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

      <Card>
        <CardHeader>
          <CardTitle className="text-green-600">Strengths</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {dna.strengths?.map((s, i) => (
              <Badge key={i} className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
                {s}
              </Badge>
            )) || <span className="text-sm text-muted-foreground">None identified</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-yellow-600">Gaps</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {dna.gaps?.map((g, i) => (
              <Badge key={i} className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                {g}
              </Badge>
            )) || <span className="text-sm text-muted-foreground">None identified</span>}
          </div>
        </CardContent>
      </Card>

      {dna.transferable_skills && Object.keys(dna.transferable_skills).length > 0 && (
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Transferable Skills</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(dna.transferable_skills).map(([key, value]) => (
                <Badge key={key} variant="secondary">
                  {key}: {String(value)}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
