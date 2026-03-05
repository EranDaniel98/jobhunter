import type { CompanyDossierResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/shared/loading-skeleton";
import { Loader2, AlertTriangle, Briefcase, MessageSquare, DollarSign, Users, Newspaper, Lightbulb, TrendingUp } from "lucide-react";

interface DossierViewProps {
  dossier: CompanyDossierResponse | null;
  isLoading: boolean;
  researchStatus: string;
}

export function DossierView({ dossier, isLoading, researchStatus }: DossierViewProps) {
  if (researchStatus === "pending" || researchStatus === "in_progress") {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Loader2 className="mb-4 h-8 w-8 animate-spin text-primary" />
        <p className="text-sm font-medium">Researching company...</p>
        <p className="text-xs text-muted-foreground">This may take a moment</p>
      </div>
    );
  }

  if (researchStatus === "failed") {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <AlertTriangle className="mb-4 h-8 w-8 text-destructive" />
        <p className="text-sm font-medium">Research failed</p>
        <p className="text-xs text-muted-foreground">Please try approving the company again</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (!dossier) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Approve this company to generate a dossier.
      </p>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {dossier.culture_summary && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4" />
              Culture
              {dossier.culture_score !== null && (
                <Badge variant="secondary">{Math.round((dossier.culture_score ?? 0) * 100)}%</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">{dossier.culture_summary}</p>
            {dossier.red_flags && dossier.red_flags.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-destructive">Red Flags</p>
                {dossier.red_flags.map((flag, i) => (
                  <p key={i} className="text-xs text-destructive/80">
                    {flag}
                  </p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {dossier.why_hire_me && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Briefcase className="h-4 w-4" />
              Why Hire Me
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{dossier.why_hire_me}</p>
          </CardContent>
        </Card>
      )}

      {dossier.fit_score_tips && dossier.fit_score_tips.length > 0 && (
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4" />
              How to Raise Your Match Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {dossier.fit_score_tips.map((tip, i) => (
                <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                  <span className="shrink-0 text-primary">•</span>
                  {tip}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {dossier.resume_bullets && dossier.resume_bullets.length > 0 && (
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Lightbulb className="h-4 w-4" />
              Resume Tips for This Company
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {dossier.resume_bullets.map((bullet, i) => (
                <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                  <span className="shrink-0 text-primary">•</span>
                  {bullet}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {(dossier.interview_format || (dossier.interview_questions && dossier.interview_questions.length > 0)) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquare className="h-4 w-4" />
              Interview Prep
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {dossier.interview_format && (
              <p className="text-sm text-muted-foreground">{dossier.interview_format}</p>
            )}
            {dossier.interview_questions && dossier.interview_questions.length > 0 && (
              <ul className="space-y-1.5">
                {dossier.interview_questions.map((q, i) => (
                  <li key={i} className="text-sm text-muted-foreground">
                    {i + 1}. {q}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {dossier.compensation_data && Object.keys(dossier.compensation_data).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <DollarSign className="h-4 w-4" />
              Compensation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              {Object.entries(dossier.compensation_data).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <dt className="capitalize text-muted-foreground">{key.replace(/_/g, " ")}</dt>
                  <dd className="font-medium">{String(value)}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      )}

      {dossier.key_people && dossier.key_people.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4" />
              Key People
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {dossier.key_people.map((person, i) => (
                <div key={i} className="text-sm">
                  <span className="font-medium">{String(person.name ?? "")}</span>
                  {person.title ? (
                    <span className="text-muted-foreground"> — {String(person.title)}</span>
                  ) : null}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {dossier.recent_news && dossier.recent_news.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Newspaper className="h-4 w-4" />
              Recent News
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {dossier.recent_news.map((news, i) => (
                <div key={i} className="text-sm">
                  <p className="font-medium">{String(news.title ?? news.headline ?? "")}</p>
                  {news.summary ? (
                    <p className="text-xs text-muted-foreground">{String(news.summary)}</p>
                  ) : null}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
