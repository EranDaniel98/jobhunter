import api from "./client";
import type { OutreachMessageResponse } from "../types";

export async function draftMessage(contact_id: string, language = "en"): Promise<OutreachMessageResponse> {
  const { data } = await api.post<OutreachMessageResponse>("/outreach/draft", { contact_id, language });
  return data;
}

export async function draftFollowup(messageId: string): Promise<OutreachMessageResponse> {
  const { data } = await api.post<OutreachMessageResponse>(
    `/outreach/${messageId}/draft-followup`
  );
  return data;
}

export async function draftLinkedIn(contact_id: string, language = "en"): Promise<OutreachMessageResponse> {
  const { data } = await api.post<OutreachMessageResponse>("/outreach/draft-linkedin", {
    contact_id,
    language,
  });
  return data;
}

export async function listMessages(params?: {
  status?: string;
  channel?: string;
  skip?: number;
  limit?: number;
}): Promise<OutreachMessageResponse[]> {
  const { data } = await api.get<OutreachMessageResponse[]>("/outreach", { params });
  return data;
}

export async function getMessage(id: string): Promise<OutreachMessageResponse> {
  const { data } = await api.get<OutreachMessageResponse>(`/outreach/${id}`);
  return data;
}

export async function editMessage(
  id: string,
  updates: { subject?: string; body?: string }
): Promise<OutreachMessageResponse> {
  const { data } = await api.patch<OutreachMessageResponse>(`/outreach/${id}`, updates);
  return data;
}

export async function sendMessage(
  id: string,
  attachResume = true,
  autoApprove = true,
): Promise<OutreachMessageResponse> {
  const { data } = await api.post<OutreachMessageResponse>(
    `/outreach/${id}/send`, null, {
      params: { attach_resume: attachResume, auto_approve: autoApprove },
    }
  );
  return data;
}

export async function markReplied(id: string): Promise<OutreachMessageResponse> {
  const { data } = await api.patch<OutreachMessageResponse>(`/outreach/${id}/mark-replied`);
  return data;
}

export async function deleteMessage(id: string): Promise<void> {
  await api.delete(`/outreach/${id}`);
}
