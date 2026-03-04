"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { useCompanies } from "@/lib/hooks/use-companies";
import {
  useInterviewSessions,
  useGeneratePrep,
  useStartMockInterview,
  useReplyMockInterview,
  useEndMockInterview,
  useInterviewSession,
} from "@/lib/hooks/use-interview";
import type { InterviewPrepSessionResponse } from "@/lib/types";
import { GraduationCap, MessageSquare, Send, Loader2, Sparkles, Clock, CheckCircle2, XCircle, User, Bot } from "lucide-react";

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
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-destructive" />;
    case "in_progress":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
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

// ---------- Content Renderers ----------

function CompanyQAContent({ content }: { content: Record<string, unknown> }) {
  const questions = (content.questions as Array<{ question: string; answer: string; tips?: string }>) || [];
  if (questions.length === 0) {
    return <p className="text-sm text-muted-foreground">No Q&A content generated yet.</p>;
  }
  return (
    <div className="space-y-4">
      {questions.map((qa, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Q: {qa.question}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm">{qa.answer}</p>
            {qa.tips && (
              <p className="text-xs text-muted-foreground italic">Tip: {qa.tips}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function BehavioralContent({ content }: { content: Record<string, unknown> }) {
  const stories = (content.stories as Array<{ situation: string; task: string; action: string; result: string; question?: string }>) || [];
  if (stories.length === 0) {
    return <p className="text-sm text-muted-foreground">No behavioral stories generated yet.</p>;
  }
  return (
    <div className="space-y-4">
      {stories.map((story, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            {story.question && (
              <CardDescription className="text-sm font-medium text-foreground">{story.question}</CardDescription>
            )}
            <CardTitle className="text-xs text-muted-foreground">STAR Story #{i + 1}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>
              <span className="font-semibold text-blue-600 dark:text-blue-400">Situation: </span>
              {story.situation}
            </div>
            <div>
              <span className="font-semibold text-green-600 dark:text-green-400">Task: </span>
              {story.task}
            </div>
            <div>
              <span className="font-semibold text-amber-600 dark:text-amber-400">Action: </span>
              {story.action}
            </div>
            <div>
              <span className="font-semibold text-purple-600 dark:text-purple-400">Result: </span>
              {story.result}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TechnicalContent({ content }: { content: Record<string, unknown> }) {
  const topics = (content.topics as Array<{ topic: string; questions: Array<{ question: string; answer: string; difficulty?: string }> }>) || [];
  if (topics.length === 0) {
    return <p className="text-sm text-muted-foreground">No technical content generated yet.</p>;
  }
  return (
    <div className="space-y-6">
      {topics.map((topic, i) => (
        <div key={i} className="space-y-3">
          <h4 className="font-semibold text-sm">{topic.topic}</h4>
          {topic.questions.map((q, j) => (
            <Card key={j}>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-sm">{q.question}</CardTitle>
                  {q.difficulty && (
                    <Badge variant={q.difficulty === "hard" ? "destructive" : q.difficulty === "medium" ? "default" : "secondary"} className="text-xs">
                      {q.difficulty}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{q.answer}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ))}
    </div>
  );
}

function CultureFitContent({ content }: { content: Record<string, unknown> }) {
  const values = (content.values as Array<{ value: string; description: string; how_to_demonstrate: string }>) || [];
  const tips = (content.tips as string[]) || [];
  return (
    <div className="space-y-4">
      {values.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-semibold text-sm">Company Values & How to Align</h4>
          {values.map((v, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{v.value}</CardTitle>
                <CardDescription className="text-xs">{v.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{v.how_to_demonstrate}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {tips.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">General Tips</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-4 space-y-1 text-sm">
              {tips.map((tip, i) => (
                <li key={i}>{tip}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      {values.length === 0 && tips.length === 0 && (
        <p className="text-sm text-muted-foreground">No culture fit content generated yet.</p>
      )}
    </div>
  );
}

function SalaryNegotiationContent({ content }: { content: Record<string, unknown> }) {
  const range = content.salary_range as { low: number; mid: number; high: number } | undefined;
  const strategies = (content.strategies as string[]) || [];
  const talking_points = (content.talking_points as string[]) || [];
  return (
    <div className="space-y-4">
      {range && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Estimated Salary Range</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-6 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Low</p>
                <p className="font-semibold">${range.low?.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Mid</p>
                <p className="font-semibold text-green-600 dark:text-green-400">${range.mid?.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">High</p>
                <p className="font-semibold">${range.high?.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      {strategies.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Negotiation Strategies</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-4 space-y-1 text-sm">
              {strategies.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      {talking_points.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Talking Points</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-4 space-y-1 text-sm">
              {talking_points.map((tp, i) => (
                <li key={i}>{tp}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      {!range && strategies.length === 0 && talking_points.length === 0 && (
        <p className="text-sm text-muted-foreground">No salary negotiation content generated yet.</p>
      )}
    </div>
  );
}

function GenericContent({ content }: { content: Record<string, unknown> }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <pre className="whitespace-pre-wrap text-sm">{JSON.stringify(content, null, 2)}</pre>
      </CardContent>
    </Card>
  );
}

function PrepContentRenderer({ prepType, content }: { prepType: string; content: Record<string, unknown> | null }) {
  if (!content) return <p className="text-sm text-muted-foreground">No content available.</p>;

  switch (prepType) {
    case "company_qa":
      return <CompanyQAContent content={content} />;
    case "behavioral":
      return <BehavioralContent content={content} />;
    case "technical":
      return <TechnicalContent content={content} />;
    case "culture_fit":
      return <CultureFitContent content={content} />;
    case "salary_negotiation":
      return <SalaryNegotiationContent content={content} />;
    default:
      return <GenericContent content={content} />;
  }
}

// ---------- Mock Interview Chat ----------

function MockInterviewChat({
  session,
  onEnd,
}: {
  session: InterviewPrepSessionResponse;
  onEnd: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const replyMutation = useReplyMockInterview();
  const endMutation = useEndMockInterview();
  const { data: liveSession } = useInterviewSession(session.id);

  const messages = liveSession?.messages || session.messages || [];
  const isActive = (liveSession?.status || session.status) === "in_progress";

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  function handleReply() {
    if (!answer.trim()) return;
    replyMutation.mutate(
      { sessionId: session.id, answer: answer.trim() },
      {
        onSuccess: () => setAnswer(""),
      },
    );
  }

  function handleEnd() {
    endMutation.mutate(session.id, {
      onSuccess: () => onEnd(),
    });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleReply();
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          <span className="text-sm font-medium">Mock Interview</span>
          {isActive ? (
            <Badge variant="default" className="text-xs">Active</Badge>
          ) : (
            <Badge variant="secondary" className="text-xs">Ended</Badge>
          )}
        </div>
        {isActive && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleEnd}
            disabled={endMutation.isPending}
          >
            {endMutation.isPending && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
            End & Get Feedback
          </Button>
        )}
      </div>

      {/* Chat messages */}
      <div className="max-h-[500px] overflow-y-auto space-y-3 rounded-lg border p-4 bg-muted/30">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            The interviewer will ask the first question...
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "candidate" ? "justify-end" : "justify-start"}`}
          >
            {msg.role !== "candidate" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <Bot className="h-4 w-4 text-primary" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm ${
                msg.role === "candidate"
                  ? "bg-primary text-primary-foreground"
                  : "bg-card border"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.feedback && (
                <div className="mt-2 pt-2 border-t border-border/50 text-xs opacity-80">
                  <p className="font-medium mb-1">Feedback:</p>
                  <p className="whitespace-pre-wrap">{typeof msg.feedback === "string" ? msg.feedback : JSON.stringify(msg.feedback, null, 2)}</p>
                </div>
              )}
            </div>
            {msg.role === "candidate" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
                <User className="h-4 w-4" />
              </div>
            )}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Reply input */}
      {isActive && (
        <div className="flex gap-2">
          <Textarea
            placeholder="Type your answer..."
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            className="flex-1 resize-none"
            disabled={replyMutation.isPending}
          />
          <Button
            size="icon"
            onClick={handleReply}
            disabled={!answer.trim() || replyMutation.isPending}
            className="shrink-0 self-end"
            aria-label="Send reply"
          >
            {replyMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      )}

      {/* Feedback summary after end */}
      {!isActive && liveSession?.content && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              Interview Feedback Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <GenericContent content={liveSession.content} />
          </CardContent>
        </Card>
      )}
    </div>
  );
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
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<string>("company_qa");
  const [mockInterviewType, setMockInterviewType] = useState<string>("behavioral");
  const [activeMockSession, setActiveMockSession] = useState<InterviewPrepSessionResponse | null>(null);
  const [viewingSession, setViewingSession] = useState<InterviewPrepSessionResponse | null>(null);

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
          </div>
        </CardContent>
      </Card>

      {!selectedCompanyId && (
        <EmptyState
          icon={GraduationCap}
          title="Select a company to begin"
          description="Choose an approved company above to generate interview prep materials or start a mock interview."
        />
      )}

      {selectedCompanyId && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="flex-wrap h-auto gap-1">
            {PREP_TYPES.map((pt) => (
              <TabsTrigger key={pt.value} value={pt.value} className="text-xs sm:text-sm">
                {pt.label}
              </TabsTrigger>
            ))}
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
                  disabled={generatePrep.isPending}
                >
                  {generatePrep.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4" />
                  )}
                  Generate {pt.label}
                </Button>
              </div>

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
                  <Button onClick={handleStartMock} disabled={startMock.isPending}>
                    {startMock.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <MessageSquare className="mr-2 h-4 w-4" />
                    )}
                    Start Mock Interview
                  </Button>
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
