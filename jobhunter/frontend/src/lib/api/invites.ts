import api from "./client";

interface InviteCreateResponse {
  code: string;
  invite_url: string;
  expires_at: string;
}

interface InviteValidateResponse {
  valid: boolean;
  invited_by_name: string | null;
}

export interface InviteListItem {
  id: string;
  code: string;
  is_used: boolean;
  used_by_email: string | null;
  expires_at: string;
  created_at: string;
}

export async function createInvite(): Promise<InviteCreateResponse> {
  const { data } = await api.post<InviteCreateResponse>("/invites");
  return data;
}

export async function validateInvite(code: string): Promise<InviteValidateResponse> {
  const { data } = await api.get<InviteValidateResponse>(`/invites/${code}/validate`);
  return data;
}

export async function listInvites(): Promise<InviteListItem[]> {
  const { data } = await api.get<InviteListItem[]>("/invites");
  return data;
}
