"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as interviewApi from "@/lib/api/interview";
import { toastError } from "@/lib/api/error-utils";
import { toast } from "sonner";

export function useInterviewSessions(companyId?: string) {
  return useQuery({
    queryKey: ["interview-sessions", companyId],
    queryFn: () => interviewApi.listSessions(companyId),
    refetchInterval: (query) => {
      const sessions = query.state.data?.sessions;
      if (!sessions) return false;
      const hasPending = sessions.some(
        (s) => s.status === "pending" || s.status === "generating"
      );
      return hasPending ? 3000 : false;
    },
  });
}

export function useInterviewSession(sessionId: string | null) {
  return useQuery({
    queryKey: ["interview-session", sessionId],
    queryFn: () => interviewApi.getSession(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "in_progress" ? 3000 : false;
    },
  });
}

export function useGeneratePrep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ companyId, prepType }: { companyId: string; prepType: string }) =>
      interviewApi.generatePrep(companyId, prepType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interview-sessions"] });
      toast.success("Generating interview prep...");
    },
    onError: (err) => toastError(err, "Failed to generate prep"),
  });
}

export function useStartMockInterview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ companyId, interviewType }: { companyId: string; interviewType: string }) =>
      interviewApi.startMockInterview(companyId, interviewType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interview-sessions"] });
    },
    onError: (err) => toastError(err, "Failed to start mock interview"),
  });
}

export function useReplyMockInterview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, answer }: { sessionId: string; answer: string }) =>
      interviewApi.replyMockInterview(sessionId, answer),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["interview-session", vars.sessionId] });
    },
    onError: (err) => toastError(err, "Failed to send reply"),
  });
}

export function useEndMockInterview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => interviewApi.endMockInterview(sessionId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["interview-sessions"] });
      qc.invalidateQueries({ queryKey: ["interview-session", data.id] });
      toast.success("Mock interview completed!");
    },
    onError: (err) => toastError(err, "Failed to end interview"),
  });
}
