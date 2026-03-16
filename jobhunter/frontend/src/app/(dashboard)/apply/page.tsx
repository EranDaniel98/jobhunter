"use client";

import { useState } from "react";
import NextLink from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { useJobPostings, useApplyAnalysis, useAnalyzeJob, useScrapeUrl, useUpdatePostingStage, useDeletePosting } from "@/lib/hooks/use-apply";
import type { JobPostingResponse, ResumeTipItem } from "@/lib/types";
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
import { FileCheck, Copy, Loader2, CheckCircle2, XCircle, Clock, Plus, ArrowLeft, Link, Trash2 } from "lucide-react";
import { toast } from "sonner";

function statusColor(status: string) {
  switch (status) {
    case "analyzed":
      return "default";
    case "pending":
    case "analyzing":
      return "secondary";
    case "failed":
      return "destructive";
    default:
      return "outline";
  }
}

function statusIcon(status: string) {
  switch (status) {
    case "analyzed":
      return <CheckCircle2 className="h-3.5 w-3.5" />;
    case "pending":
    case "analyzing":
      return <Clock className="h-3.5 w-3.5" />;
    case "failed":
      return <XCircle className="h-3.5 w-3.5" />;
    default:
      return null;
  }
}

function priorityVariant(priority: string): "destructive" | "secondary" | "outline" {
  switch (priority) {
    case "high":
      return "destructive";
    case "medium":
      return "secondary";
    default:
      return "outline";
  }
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-primary";
  if (score >= 60) return "text-chart-3";
  return "text-destructive";
}

const APPLICATION_STAGES = [
  { value: "saved", label: "Saved", color: "bg-gray-100 text-gray-700" },
  { value: "applied", label: "Applied", color: "bg-blue-100 text-blue-700" },
  { value: "phone_screen", label: "Phone Screen", color: "bg-amber-100 text-amber-700" },
  { value: "interview", label: "Interview", color: "bg-purple-100 text-purple-700" },
  { value: "offer", label: "Offer", color: "bg-green-100 text-green-700" },
  { value: "rejected", label: "Rejected", color: "bg-red-100 text-red-700" },
];

export default function ApplyPage() {
  const [selectedPostingId, setSelectedPostingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [copied, setCopied] = useState(false);
  const [scrapeError, setScrapeError] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [url, setUrl] = useState("");
  const [rawText, setRawText] = useState("");

  const { data: postingsData, isLoading: loadingPostings } = useJobPostings();
  const postings = postingsData?.postings ?? [];
  const selectedPosting = postings.find((p) => p.id === selectedPostingId) ?? null;

  const { data: analysis, isLoading: loadingAnalysis, error: analysisError } = useApplyAnalysis(
    selectedPostingId,
    selectedPosting?.status === "pending" || selectedPosting?.status === "analyzing",
  );
  const analyzeMutation = useAnalyzeJob();
  const scrapeMutation = useScrapeUrl();
  const stageMutation = useUpdatePostingStage();
  const deleteMutation = useDeletePosting();
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !rawText.trim()) {
      toast.error("Title and job description are required");
      return;
    }
    analyzeMutation.mutate(
      {
        title: title.trim(),
        company_name: companyName.trim() || undefined,
        url: url.trim() || undefined,
        raw_text: rawText.trim(),
      },
      {
        onSuccess: (posting) => {
          setTitle("");
          setCompanyName("");
          setUrl("");
          setRawText("");
          setShowForm(false);
          setSelectedPostingId(posting.id);
        },
      }
    );
  }

  function handleFetch() {
    if (!url.trim()) {
      toast.error("Enter a URL first");
      return;
    }
    setScrapeError(null);
    scrapeMutation.mutate(url.trim(), {
      onSuccess: (data) => {
        setScrapeError(null);
        setRawText(data.raw_text);
        if (data.title) setTitle(data.title);
        if (data.company_name) setCompanyName(data.company_name);
        toast.success("Job posting fetched successfully");
      },
      onError: (err) => {
        const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          || "Could not fetch job posting from URL. Please paste the description manually.";
        setScrapeError(message);
      },
    });
  }

  async function handleCopyLetter() {
    if (!analysis?.cover_letter) return;
    try {
      await navigator.clipboard.writeText(analysis.cover_letter);
      setCopied(true);
      toast.success("Cover letter copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy");
    }
  }

  function handleSelectPosting(posting: JobPostingResponse) {
    setSelectedPostingId(posting.id);
    setShowForm(false);
  }

  // Group tips by priority
  const tipsByPriority = (analysis?.resume_tips ?? []).reduce<Record<string, ResumeTipItem[]>>(
    (acc, tip) => {
      const key = tip.priority || "low";
      if (!acc[key]) acc[key] = [];
      acc[key].push(tip);
      return acc;
    },
    {}
  );
  const priorityOrder = ["high", "medium", "low"];

  return (
    <div className="space-y-6">
      <PageHeader title="Apply" description="Analyze job postings and get tailored application materials" dataTour="page-header">
        <Button onClick={() => { setShowForm(true); setSelectedPostingId(null); }}>
          <Plus className="mr-2 h-4 w-4" />
          Analyze Job
        </Button>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[480px_1fr]">
        {/* Left column: form or postings list */}
        <div className="space-y-4">
          {showForm && (
            <Card>
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">New Job Analysis</CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowForm(false)}
                  >
                    <ArrowLeft className="mr-1 h-3.5 w-3.5" />
                    Back
                  </Button>
                </div>
                <CardDescription>Paste a job posting to get a fit analysis</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* URL fetch section */}
                  <div className="space-y-2">
                    <Label htmlFor="url">Job URL</Label>
                    <div className="flex gap-2">
                      <Input
                        id="url"
                        type="url"
                        placeholder="https://..."
                        value={url}
                        onChange={(e) => { setUrl(e.target.value); setScrapeError(null); }}
                        className="flex-1"
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={handleFetch}
                        disabled={scrapeMutation.isPending}
                      >
                        {scrapeMutation.isPending ? (
                          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Link className="mr-1.5 h-3.5 w-3.5" />
                        )}
                        Fetch
                      </Button>
                    </div>
                    {scrapeError && (
                      <p className="text-xs text-destructive">{scrapeError}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Paste a job posting URL to auto-extract the description
                    </p>
                  </div>

                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <span className="w-full border-t" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-card px-2 text-muted-foreground">or fill manually</span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="title">Job Title *</Label>
                    <Input
                      id="title"
                      placeholder="e.g. Senior Software Engineer"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="company">Company Name</Label>
                    <Input
                      id="company"
                      placeholder="e.g. Acme Corp"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="raw-text">Job Description *</Label>
                    <Textarea
                      id="raw-text"
                      placeholder="Paste the full job description here..."
                      value={rawText}
                      onChange={(e) => setRawText(e.target.value)}
                      rows={8}
                      required
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={analyzeMutation.isPending}
                  >
                    {analyzeMutation.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <FileCheck className="mr-2 h-4 w-4" />
                        Analyze Job Posting
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}

          {/* Postings list */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-muted-foreground px-1">
              Job Postings {postingsData?.total ? `(${postingsData.total})` : ""}
            </h3>

            {loadingPostings && (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <Card key={i}>
                    <CardContent className="py-3">
                      <Skeleton className="h-4 w-3/4 mb-2" />
                      <Skeleton className="h-3 w-1/2" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {!loadingPostings && postings.length === 0 && !showForm && (
              <EmptyState
                icon={FileCheck}
                title="No job postings yet"
                description="Click 'Analyze Job' to paste a job description and get a personalized fit analysis."
                action={{
                  label: "Analyze Job",
                  onClick: () => setShowForm(true),
                }}
              />
            )}

            {!loadingPostings && postings.map((posting) => (
              <Card
                key={posting.id}
                className={`cursor-pointer transition-colors hover:bg-muted/50 hover:shadow-md ${
                  selectedPostingId === posting.id ? "ring-2 ring-primary" : ""
                }`}
                onClick={() => handleSelectPosting(posting)}
              >
                <CardContent className="py-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm truncate">{posting.title}</p>
                      {posting.company_name && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {posting.company_id ? (
                            <NextLink
                              href={`/companies/${posting.company_id}`}
                              className="hover:underline hover:text-foreground"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {posting.company_name}
                            </NextLink>
                          ) : (
                            posting.company_name
                          )}
                        </p>
                      )}
                    </div>
                    <Badge variant={statusColor(posting.status)} className="shrink-0 gap-1 text-xs">
                      {statusIcon(posting.status)}
                      {posting.status}
                    </Badge>
                  </div>
                  {/* Application stage + delete */}
                  <div className="mt-2 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                    <Select
                      value={posting.application_stage || "saved"}
                      onValueChange={(stage) => stageMutation.mutate({ postingId: posting.id, stage })}
                    >
                      <SelectTrigger className="h-7 w-[140px] text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {APPLICATION_STAGES.map(s => (
                          <SelectItem key={s.value} value={s.value} className="text-xs">
                            {s.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive shrink-0"
                      onClick={() => setDeleteConfirmId(posting.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  {posting.ats_keywords && posting.ats_keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {posting.ats_keywords.slice(0, 4).map((kw) => (
                        <Badge key={kw} variant="outline" className="text-[10px] px-1.5 py-0">
                          {kw}
                        </Badge>
                      ))}
                      {posting.ats_keywords.length > 4 && (
                        <span className="text-[10px] text-muted-foreground">
                          +{posting.ats_keywords.length - 4} more
                        </span>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Right column: analysis view */}
        <div className="space-y-4">
          {!selectedPostingId && !showForm && (
            <Card className="flex items-center justify-center min-h-[400px]">
              <CardContent className="text-center py-16">
                <FileCheck className="mx-auto h-12 w-12 text-muted-foreground/40 mb-4" />
                <p className="text-muted-foreground">
                  Select a job posting to view its analysis
                </p>
              </CardContent>
            </Card>
          )}

          {selectedPostingId && loadingAnalysis && (
            <Card>
              <CardHeader>
                <Skeleton className="h-5 w-48 mb-2" />
                <Skeleton className="h-4 w-32" />
              </CardHeader>
              <CardContent className="space-y-6">
                <Skeleton className="h-8 w-full" />
                <div className="space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
                <Skeleton className="h-32 w-full" />
              </CardContent>
            </Card>
          )}

          {selectedPostingId && !loadingAnalysis && !analysis && !!analysisError && (
            <Card className="flex items-center justify-center min-h-[400px]">
              <CardContent className="text-center py-16">
                <XCircle className="mx-auto h-10 w-10 text-destructive/40 mb-4" />
                <p className="text-muted-foreground font-medium">Analysis failed</p>
                <p className="text-sm text-muted-foreground mt-1">
                  The analysis could not be retrieved. Try submitting the job posting again.
                </p>
              </CardContent>
            </Card>
          )}

          {selectedPostingId && !loadingAnalysis && !analysis && !analysisError && (
            <Card className="flex items-center justify-center min-h-[400px]">
              <CardContent className="text-center py-16 w-full max-w-xs">
                <Loader2 className="mx-auto h-10 w-10 text-muted-foreground/40 mb-4 animate-spin" />
                <p className="text-muted-foreground font-medium">Analysis in progress...</p>
                <p className="text-sm text-muted-foreground mt-1">
                  This usually takes 20-30 seconds
                </p>
                <div className="mt-4 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                  <div className="h-full w-1/3 rounded-full bg-primary animate-[indeterminate_1.5s_ease-in-out_infinite]" />
                </div>
              </CardContent>
            </Card>
          )}

          {analysis && (
            <div className="space-y-4">
              {/* Readiness Score */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Readiness Score</CardTitle>
                  <CardDescription>How well your profile matches this role</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-6">
                    <div className="relative h-28 w-28 shrink-0">
                      <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
                        <circle cx="60" cy="60" r="50" fill="none" strokeWidth="8" className="stroke-muted" />
                        <circle
                          cx="60" cy="60" r="50"
                          fill="none" strokeWidth="8"
                          strokeDasharray={2 * Math.PI * 50}
                          strokeDashoffset={2 * Math.PI * 50 - (analysis.readiness_score / 100) * 2 * Math.PI * 50}
                          strokeLinecap="round"
                          className={`transition-all duration-700 ${
                            analysis.readiness_score >= 80 ? "stroke-primary" :
                            analysis.readiness_score >= 60 ? "stroke-chart-3" :
                            "stroke-destructive"
                          }`}
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className={`text-3xl font-bold tabular-nums ${scoreColor(analysis.readiness_score)}`}>
                          {analysis.readiness_score}%
                        </span>
                      </div>
                    </div>
                    <div className="flex-1 space-y-1">
                      <p className="text-sm font-medium">
                        {analysis.readiness_score >= 80 ? "Strong match!" :
                         analysis.readiness_score >= 60 ? "Good potential" :
                         "Needs improvement"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {analysis.matching_skills.length} matching skills, {analysis.missing_skills.length} gaps
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Parsed Requirements */}
              {selectedPosting?.parsed_requirements && Object.keys(selectedPosting.parsed_requirements).length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Job Requirements</CardTitle>
                    <CardDescription>Parsed requirements from the posting</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {Object.entries(selectedPosting.parsed_requirements).map(([key, value]) => (
                        <div key={key}>
                          <h4 className="text-sm font-medium capitalize mb-1">{key.replace(/_/g, " ")}</h4>
                          {Array.isArray(value) ? (
                            <div className="flex flex-wrap gap-1.5">
                              {(value as string[]).map((item, i) => (
                                <Badge key={i} variant="outline" className="text-xs">{item}</Badge>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-muted-foreground">{String(value)}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Skills Comparison */}
              <div className="grid gap-4 sm:grid-cols-2">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-primary" />
                      Matching Skills
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {analysis.matching_skills.length === 0 ? (
                      <p className="text-sm text-muted-foreground">None identified</p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {analysis.matching_skills.map((skill) => (
                          <Badge key={skill} variant="secondary" className="text-xs">
                            {skill}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <XCircle className="h-4 w-4 text-destructive" />
                      Missing Skills
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {analysis.missing_skills.length === 0 ? (
                      <p className="text-sm text-muted-foreground">None - great match!</p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {analysis.missing_skills.map((skill) => (
                          <Badge key={skill} variant="destructive" className="text-xs">
                            {skill}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* ATS Keywords */}
              {analysis.ats_keywords.length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">ATS Keywords</CardTitle>
                    <CardDescription>Include these keywords in your application</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-1.5">
                      {analysis.ats_keywords.map((keyword) => (
                        <Badge key={keyword} variant="outline" className="text-xs">
                          {keyword}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Resume Tips */}
              {analysis.resume_tips.length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Resume Tips</CardTitle>
                    <CardDescription>Suggested improvements for this application</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {priorityOrder.map((priority) => {
                        const tips = tipsByPriority[priority];
                        if (!tips || tips.length === 0) return null;
                        return (
                          <div key={priority} className="space-y-2">
                            <div className="flex items-center gap-2">
                              <Badge variant={priorityVariant(priority)} className="text-xs capitalize">
                                {priority} priority
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                {tips.length} {tips.length === 1 ? "tip" : "tips"}
                              </span>
                            </div>
                            <ul className="space-y-1.5 ml-1">
                              {tips.map((tip, idx) => (
                                <li key={idx} className="text-sm flex gap-2">
                                  <span className="text-muted-foreground shrink-0 font-medium">
                                    [{tip.section}]
                                  </span>
                                  <span>{tip.tip}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Cover Letter */}
              {analysis.cover_letter && (
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-base">Cover Letter</CardTitle>
                        <CardDescription>AI-generated cover letter tailored to this role</CardDescription>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopyLetter}
                      >
                        {copied ? (
                          <CheckCircle2 className="mr-1.5 h-3.5 w-3.5 text-primary" />
                        ) : (
                          <Copy className="mr-1.5 h-3.5 w-3.5" />
                        )}
                        {copied ? "Copied!" : "Copy"}
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="whitespace-pre-wrap rounded-md bg-muted p-4 text-sm leading-relaxed">
                      {analysis.cover_letter}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Delete posting confirmation */}
      <AlertDialog
        open={!!deleteConfirmId}
        onOpenChange={(open) => { if (!open) setDeleteConfirmId(null); }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete job posting?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this job posting and its analysis. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleteConfirmId) {
                  deleteMutation.mutate(deleteConfirmId, {
                    onSuccess: () => {
                      if (selectedPostingId === deleteConfirmId) {
                        setSelectedPostingId(null);
                      }
                      toast.success("Job posting deleted");
                      setDeleteConfirmId(null);
                    },
                    onError: () => setDeleteConfirmId(null),
                  });
                }
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
