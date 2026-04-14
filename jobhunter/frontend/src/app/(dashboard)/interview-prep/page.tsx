"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { useCompanies } from "@/lib/hooks/use-companies";
import {
  useInterviewSessions,
  useGeneratePrep,
  useStartMockInterview,
} from "@/lib/hooks/use-interview";
import type { InterviewPrepSessionResponse } from "@/lib/types";
import { GraduationCap, MessageSquare, Loader2, Sparkles, Clock, CheckCircle2, XCircle, Circle, Timer, X, Building2 } from "lucide-react";
import { PrepContentRenderer } from "@/components/interview/prep-content-renderer";
import { OperationProgress } from "@/components/shared/operation-progress";
import { MockInterviewChat } from "@/components/interview/mock-interview-chat";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import NextLink from "next/link";

const PREP_TYPES = [
  { value: "company_qa", label: "Company Q&A" },
  { value: "behavioral", label: "Behavioral" },
  { value: "technical", label: "Technical" },
  { value: "culture_fit", label: "Culture Fit" },
  { value: "salary_negotiation", label: "Salary Negotiation" },
  { value: "mock_interview", label: "Mock Interview" },
] as const;

const MOCK_INTERVIEW_TYPES = [
  { value: "behavioral", label: "Behavioral" },
  { value: "technical", label: "Technical" },
  { value: "mixed", label: "Mixed" },
];

function statusIcon(status: string) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-primary" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-destructive" />;
    case "in_progress":
      return <Loader2 className="h-4 w-4 animate-spin text-chart-3" />;
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />;
  }
}

function statusLabel(status: string) {
  switch (status) {
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "in_progress":
      return "In Progress";
    default:
      return status;
  }
}

// ---------- Session History ----------

function SessionHistory({
  sessions,
  onSelect,
}: {
  sessions: InterviewPrepSessionResponse[];
  onSelect: (session: InterviewPrepSessionResponse) => void;
}) {
  if (sessions.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Past Sessions</CardTitle>
        <CardDescription className="text-xs">Click to view details</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {sessions.map((session) => {
            const typeLabel = PREP_TYPES.find((t) => t.value === session.prep_type)?.label || session.prep_type;
            return (
              <div
                key={session.id}
                className="flex items-center gap-3 rounded-md border p-3 cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => onSelect(session)}
              >
                {statusIcon(session.status)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{typeLabel}</p>
                  <p className="text-xs text-muted-foreground">{statusLabel(session.status)}</p>
                </div>
                {session.error && (
                  <Badge variant="destructive" className="text-xs">Error</Badge>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------- Main Page ----------

export default function InterviewPrepPage() {
  const router = useRouter();
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<string>("company_qa");
  const [mockInterviewType, setMockInterviewType] = useState<string>("behavioral");
  const [activeMockSession, setActiveMockSession] = useState<InterviewPrepSessionResponse | null>(null);
  const [viewingSession, setViewingSession] = useState<InterviewPrepSessionResponse | null>(null);
  const [timerMinutes, setTimerMinutes] = useState<number>(0);
  const [timerActive, setTimerActive] = useState(false);
  const [timerRemaining, setTimerRemaining] = useState(0);

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const { data: companiesData, isLoading: companiesLoading } = useCompanies("approved");
  const { data: sessionsData, isLoading: sessionsLoading } = useInterviewSessions(
    selectedCompanyId || undefined,
  );
  const generatePrep = useGeneratePrep();
  const startMock = useStartMockInterview();

  const companies = companiesData?.companies || [];
  const sessions = sessionsData?.sessions || [];

  // Filter sessions by current tab prep_type
  const tabSessions = sessions.filter((s) => s.prep_type === activeTab);
  const latestTabSession = tabSessions.length > 0 ? tabSessions[0] : null;

  useEffect(() => {
    if (timerActive && timerRemaining > 0) {
      timerRef.current = setInterval(() => {
        setTimerRemaining(prev => {
          if (prev <= 1) {
            setTimerActive(false);
            toast.info("Time's up!");
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }
  }, [timerActive, timerRemaining]);

  function startTimer(mins: number) {
    setTimerMinutes(mins);
    setTimerRemaining(mins * 60);
    setTimerActive(true);
  }

  function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  function handleGenerate() {
    if (!selectedCompanyId) return;
    generatePrep.mutate({ companyId: selectedCompanyId, prepType: activeTab });
  }

  function handleStartMock() {
    if (!selectedCompanyId) return;
    startMock.mutate(
      { companyId: selectedCompanyId, interviewType: mockInterviewType },
      {
        onSuccess: (session) => {
          setActiveMockSession(session);
        },
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Interview Prep"
        description="AI-powered preparation for your upcoming interviews"
        dataTour="page-header"
      />

      {/* Company Selector */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <label className="text-sm font-medium whitespace-nowrap">Select Company</label>
            {companiesLoading ? (
              <Skeleton className="h-10 w-64" />
            ) : companies.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No approved companies yet. Approve a company first to start interview prep.
              </p>
            ) : (
              <Select value={selectedCompanyId} onValueChange={setSelectedCompanyId}>
                <SelectTrigger className="w-64">
                  <SelectValue placeholder="Choose a company..." />
                </SelectTrigger>
                <SelectContent>
                  {companies.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {selectedCompanyId && (
              <NextLink href={`/companies/${selectedCompanyId}`}>
                <Button variant="outline" size="sm">
                  <Building2 className="mr-1 h-3.5 w-3.5" />
                  View Dossier
                </Button>
              </NextLink>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Prep Summary */}
      {selectedCompanyId && !sessionsLoading && (
        <div className="flex items-center gap-4 rounded-lg border bg-muted/30 px-4 py-3">
          <GraduationCap className="h-5 w-5 text-primary shrink-0" />
          <div className="text-sm">
            <span className="font-medium">
              {sessions.length > 0
                ? `${sessions.length} sessions`
                : "No sessions yet"}
            </span>
            <span className="text-muted-foreground">
              {" "}across {new Set(sessions.map(s => s.prep_type)).size} prep types
            </span>
          </div>
        </div>
      )}

      {/* Readiness Tracker */}
      {selectedCompanyId && !sessionsLoading && (
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium">Prep Readiness</h3>
              <span className="text-xs text-muted-foreground">
                {PREP_TYPES.filter(pt => sessions.some(s => s.prep_type === pt.value && s.status === "completed")).length}/{PREP_TYPES.length} completed
              </span>
            </div>
            <div className="flex gap-2">
              {PREP_TYPES.map(pt => {
                const hasCompleted = sessions.some(s => s.prep_type === pt.value && s.status === "completed");
                const hasInProgress = sessions.some(s => s.prep_type === pt.value && s.status === "in_progress");
                return (
                  <button
                    key={pt.value}
                    onClick={() => setActiveTab(pt.value)}
                    className={cn(
                      "flex flex-col items-center gap-1 rounded-lg border p-2 flex-1 min-w-0 transition-colors",
                      activeTab === pt.value && "ring-2 ring-primary",
                      hasCompleted && "border-primary/30 bg-primary/5"
                    )}
                  >
                    <div className={cn(
                      "h-6 w-6 rounded-full flex items-center justify-center",
                      hasCompleted ? "bg-primary text-primary-foreground" :
                      hasInProgress ? "bg-chart-3/20 text-chart-3" :
                      "bg-muted text-muted-foreground"
                    )}>
                      {hasCompleted ? (
                        <CheckCircle2 className="h-3.5 w-3.5" />
                      ) : hasInProgress ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Circle className="h-3.5 w-3.5" />
                      )}
                    </div>
                    <span className="text-[10px] text-center leading-tight truncate w-full">
                      {pt.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {!selectedCompanyId && (
        <EmptyState
          icon={GraduationCap}
          title="Select a company to begin"
          description="Choose an approved company above to generate interview prep materials or start a mock interview."
          action={{
            label: "Browse Companies",
            onClick: () => router.push("/companies"),
          }}
        />
      )}

      {selectedCompanyId && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="flex-wrap h-auto gap-1">
            {PREP_TYPES.map((pt) => {
              const count = sessions.filter(s => s.prep_type === pt.value).length;
              return (
                <TabsTrigger key={pt.value} value={pt.value} className="text-xs sm:text-sm gap-1">
                  {pt.label}
                  {count > 0 && (
                    <Badge variant="secondary" className="ml-1 h-4 min-w-[16px] px-1 text-[10px]">
                      {count}
                    </Badge>
                  )}
                </TabsTrigger>
              );
            })}
          </TabsList>

          {/* Prep content tabs */}
          {PREP_TYPES.filter((pt) => pt.value !== "mock_interview").map((pt) => (
            <TabsContent key={pt.value} value={pt.value} className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold">{pt.label}</h3>
                  <p className="text-sm text-muted-foreground">
                    {tabSessions.length} session{tabSessions.length !== 1 ? "s" : ""} generated
                  </p>
                </div>
                <Button
                  onClick={handleGenerate}
                  disabled={generatePrep.isPending || (activeTab === pt.value && latestTabSession?.status === "in_progress")}
                >
                  {(generatePrep.isPending || (activeTab === pt.value && latestTabSession?.status === "in_progress")) ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4" />
                  )}
                  Generate {pt.label}
                </Button>
              </div>

              {generatePrep.isPending && activeTab === pt.value && (
                <OperationProgress
                  status="in_progress"
                  label={`Generating ${pt.label} content…`}
                />
              )}

              {sessionsLoading && (
                <div className="space-y-3">
                  <Skeleton className="h-32 w-full" />
                  <Skeleton className="h-32 w-full" />
                </div>
              )}

              {/* Show viewed session or latest session content */}
              {!sessionsLoading && viewingSession && viewingSession.prep_type === pt.value && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    {statusIcon(viewingSession.status)}
                    <span className="text-sm font-medium">
                      {statusLabel(viewingSession.status)}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setViewingSession(null)}
                      className="ml-auto text-xs"
                    >
                      Back to latest
                    </Button>
                  </div>
                  {viewingSession.error && (
                    <Card className="border-destructive">
                      <CardContent className="pt-4">
                        <p className="text-sm text-destructive">{viewingSession.error}</p>
                      </CardContent>
                    </Card>
                  )}
                  <PrepContentRenderer prepType={pt.value} content={viewingSession.content} />
                </div>
              )}

              {!sessionsLoading && !viewingSession && latestTabSession && activeTab === pt.value && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    {statusIcon(latestTabSession.status)}
                    <span className="text-sm font-medium">
                      Latest: {statusLabel(latestTabSession.status)}
                    </span>
                  </div>
                  {latestTabSession.error && (
                    <Card className="border-destructive">
                      <CardContent className="pt-4">
                        <p className="text-sm text-destructive">{latestTabSession.error}</p>
                      </CardContent>
                    </Card>
                  )}
                  <PrepContentRenderer prepType={pt.value} content={latestTabSession.content} />
                </div>
              )}

              {!sessionsLoading && !viewingSession && !latestTabSession && activeTab === pt.value && (
                <EmptyState
                  icon={GraduationCap}
                  title={`No ${pt.label} prep yet`}
                  description={`Click "Generate ${pt.label}" to create AI-powered interview preparation materials.`}
                />
              )}

              {/* Session history */}
              {!sessionsLoading && tabSessions.length > 1 && (
                <SessionHistory
                  sessions={tabSessions.slice(1)}
                  onSelect={(s) => setViewingSession(s)}
                />
              )}
            </TabsContent>
          ))}

          {/* Mock Interview Tab */}
          <TabsContent value="mock_interview" className="space-y-4">
            {!activeMockSession ? (
              <div className="space-y-4">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                  <div className="space-y-2">
                    <h3 className="text-lg font-semibold">Mock Interview</h3>
                    <p className="text-sm text-muted-foreground">
                      Practice with an AI interviewer. Choose your interview type and start when ready.
                    </p>
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-medium">Interview Type</label>
                      <Select value={mockInterviewType} onValueChange={setMockInterviewType}>
                        <SelectTrigger className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {MOCK_INTERVIEW_TYPES.map((t) => (
                            <SelectItem key={t.value} value={t.value}>
                              {t.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 items-end">
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-medium">Timer</label>
                      <div className="flex gap-1">
                        {[15, 30, 45].map(mins => (
                          <Button
                            key={mins}
                            size="sm"
                            variant={timerMinutes === mins ? "default" : "outline"}
                            className="h-7 text-xs"
                            onClick={() => startTimer(mins)}
                            type="button"
                          >
                            {mins}m
                          </Button>
                        ))}
                        {timerActive && (
                          <div className="flex items-center gap-2 ml-2">
                            <Timer className="h-4 w-4 text-primary" />
                            <span className={cn(
                              "text-sm font-mono font-bold tabular-nums",
                              timerRemaining < 60 && "text-destructive animate-pulse"
                            )}>
                              {formatTime(timerRemaining)}
                            </span>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 px-1"
                              onClick={() => { setTimerActive(false); setTimerRemaining(0); }}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                    <Button onClick={handleStartMock} disabled={startMock.isPending}>
                      {startMock.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <MessageSquare className="mr-2 h-4 w-4" />
                      )}
                      Start Mock Interview
                    </Button>
                  </div>
                </div>

                {/* Past mock sessions */}
                {sessionsLoading && (
                  <div className="space-y-3">
                    <Skeleton className="h-24 w-full" />
                    <Skeleton className="h-24 w-full" />
                  </div>
                )}

                {!sessionsLoading && tabSessions.length === 0 && (
                  <EmptyState
                    icon={MessageSquare}
                    title="No mock interviews yet"
                    description="Start your first mock interview to practice with an AI interviewer."
                  />
                )}

                {!sessionsLoading && tabSessions.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold">Past Mock Interviews</h4>
                    {tabSessions.map((session) => (
                      <Card
                        key={session.id}
                        className="cursor-pointer hover:bg-muted/50 transition-colors"
                        onClick={() => {
                          if (session.status === "in_progress") {
                            setActiveMockSession(session);
                          } else {
                            setViewingSession(session);
                          }
                        }}
                      >
                        <CardContent className="flex items-center gap-3 py-4">
                          {statusIcon(session.status)}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium">
                              Mock Interview
                              {session.status === "in_progress" && " (In Progress - Click to Resume)"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {session.messages?.length || 0} messages - {statusLabel(session.status)}
                            </p>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}

                {/* Viewing a past completed mock session */}
                {viewingSession && viewingSession.prep_type === "mock_interview" && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-semibold">Session Details</h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setViewingSession(null)}
                        className="ml-auto text-xs"
                      >
                        Close
                      </Button>
                    </div>
                    <MockInterviewChat
                      session={viewingSession}
                      onEnd={() => setViewingSession(null)}
                    />
                  </div>
                )}
              </div>
            ) : (
              <MockInterviewChat
                session={activeMockSession}
                onEnd={() => setActiveMockSession(null)}
              />
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
