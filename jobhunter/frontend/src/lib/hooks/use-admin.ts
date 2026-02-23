"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as adminApi from "@/lib/api/admin";

export function useSystemOverview() {
  return useQuery({
    queryKey: ["admin", "overview"],
    queryFn: adminApi.getOverview,
  });
}

export function useAdminUsers(params?: {
  skip?: number;
  limit?: number;
  search?: string;
}) {
  return useQuery({
    queryKey: ["admin", "users", params],
    queryFn: () => adminApi.listUsers(params),
  });
}

export function useAdminUser(id: string) {
  return useQuery({
    queryKey: ["admin", "user", id],
    queryFn: () => adminApi.getUser(id),
    enabled: !!id,
  });
}

export function useToggleAdmin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isAdmin }: { id: string; isAdmin: boolean }) =>
      adminApi.toggleAdmin(id, isAdmin),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      qc.invalidateQueries({ queryKey: ["admin", "overview"] });
    },
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminApi.deleteUser(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      qc.invalidateQueries({ queryKey: ["admin", "overview"] });
    },
  });
}

export function useRegistrationTrend(days: number = 30) {
  return useQuery({
    queryKey: ["admin", "registrations", days],
    queryFn: () => adminApi.getRegistrationTrend(days),
  });
}

export function useInviteChain() {
  return useQuery({
    queryKey: ["admin", "invites"],
    queryFn: adminApi.getInviteChain,
  });
}

export function useTopUsers(metric: string = "messages_sent", limit: number = 10) {
  return useQuery({
    queryKey: ["admin", "top-users", metric, limit],
    queryFn: () => adminApi.getTopUsers(metric, limit),
  });
}
