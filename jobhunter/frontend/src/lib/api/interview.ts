import api from "./client";
import type { InterviewPrepSessionResponse, InterviewPrepListResponse } from "@/lib/types";

export async function generatePrep(companyId: string, prepType: string) {
  const { data } = await api.post<InterviewPrepSessionResponse>("/interview-prep/generate", {
    company_id: companyId,
    prep_type: prepType,
  });
  return data;
}

export async function listSessions(companyId?: string) {
  const params = companyId ? { company_id: companyId } : {};
  const { data } = await api.get<InterviewPrepListResponse>("/interview-prep/sessions", { params });
  return data;
}

export async function getSession(sessionId: string) {
  const { data } = await api.get<InterviewPrepSessionResponse>(`/interview-prep/sessions/${sessionId}`);
  return data;
}

export async function startMockInterview(companyId: string, interviewType: string) {
  const { data } = await api.post<InterviewPrepSessionResponse>("/interview-prep/mock/start", {
    company_id: companyId,
    interview_type: interviewType,
  });
  return data;
}

export async function replyMockInterview(sessionId: string, answer: string) {
  const { data } = await api.post<{ id: string; role: string; content: string; turn_number: number; feedback: unknown }>("/interview-prep/mock/reply", {
    session_id: sessionId,
    answer,
  });
  return data;
}

export async function endMockInterview(sessionId: string) {
  const { data } = await api.post<InterviewPrepSessionResponse>("/interview-prep/mock/end", {
    session_id: sessionId,
  });
  return data;
}
