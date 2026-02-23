import api from "./client";
import type {
  SystemOverview,
  AdminUserList,
  AdminUserDetail,
  RegistrationTrend,
  InviteChainItem,
  TopUserItem,
} from "../types";

export async function getOverview(): Promise<SystemOverview> {
  const { data } = await api.get<SystemOverview>("/admin/overview");
  return data;
}

export async function listUsers(params?: {
  skip?: number;
  limit?: number;
  search?: string;
}): Promise<AdminUserList> {
  const { data } = await api.get<AdminUserList>("/admin/users", { params });
  return data;
}

export async function getUser(id: string): Promise<AdminUserDetail> {
  const { data } = await api.get<AdminUserDetail>(`/admin/users/${id}`);
  return data;
}

export async function toggleAdmin(
  id: string,
  isAdmin: boolean
): Promise<AdminUserDetail> {
  const { data } = await api.patch<AdminUserDetail>(`/admin/users/${id}`, {
    is_admin: isAdmin,
  });
  return data;
}

export async function deleteUser(id: string): Promise<void> {
  await api.delete(`/admin/users/${id}`);
}

export async function getRegistrationTrend(
  days: number = 30
): Promise<RegistrationTrend[]> {
  const { data } = await api.get<RegistrationTrend[]>(
    "/admin/analytics/registrations",
    { params: { days } }
  );
  return data;
}

export async function getInviteChain(): Promise<InviteChainItem[]> {
  const { data } = await api.get<InviteChainItem[]>("/admin/analytics/invites");
  return data;
}

export async function getTopUsers(
  metric: string = "messages_sent",
  limit: number = 10
): Promise<TopUserItem[]> {
  const { data } = await api.get<TopUserItem[]>("/admin/analytics/top-users", {
    params: { metric, limit },
  });
  return data;
}
