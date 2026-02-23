import api from "./client";
import type { PendingAction, PendingActionListResponse, PendingCountResponse } from "../types";

export async function listApprovals(params?: {
  status?: string;
  action_type?: string;
  skip?: number;
  limit?: number;
}): Promise<PendingActionListResponse> {
  const { data } = await api.get<PendingActionListResponse>("/approvals", { params });
  return data;
}

export async function getApprovalCount(): Promise<PendingCountResponse> {
  const { data } = await api.get<PendingCountResponse>("/approvals/count");
  return data;
}

export async function approveAction(id: string): Promise<PendingAction> {
  const { data } = await api.post<PendingAction>(`/approvals/${id}/approve`);
  return data;
}

export async function rejectAction(id: string): Promise<PendingAction> {
  const { data } = await api.post<PendingAction>(`/approvals/${id}/reject`);
  return data;
}
