"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  useReplyMockInterview,
  useEndMockInterview,
  useInterviewSession,
} from "@/lib/hooks/use-interview";
import type { InterviewPrepSessionResponse } from "@/lib/types";
import { MessageSquare, Send, Loader2, Sparkles, User, Bot } from "lucide-react";
import { GenericContent } from "./generic-content";

export function MockInterviewChat({
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
            <GenericContent data={liveSession.content} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
