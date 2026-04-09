"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as adminApi from "@/lib/api/admin";
import { toastError } from "@/lib/api/error-utils";
import type { WaitlistStatus, PlanTier } from "@/lib/types";

export function useSystemOverview() {
  return useQuery({
    queryKey: ["admin", "overview"],
    queryFn: adminApi.getOverview,
    refetchInterval: 60000,
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
    placeholderData: keepPreviousData,
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
      qc.invalidateQueries({ queryKey: ["admin", "audit-log"] });
    },
  });
}

export function useToggleActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      adminApi.toggleActive(id, isActive),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      qc.invalidateQueries({ queryKey: ["admin", "overview"] });
      qc.invalidateQueries({ queryKey: ["admin", "audit-log"] });
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
      qc.invalidateQueries({ queryKey: ["admin", "audit-log"] });
    },
  });
}

export function useUpdateUserPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, planTier }: { id: string; planTier: PlanTier }) =>
      adminApi.updateUserPlan(id, planTier),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      qc.invalidateQueries({ queryKey: ["admin", "user", vars.id] });
      qc.invalidateQueries({ queryKey: ["admin", "audit-log"] });
    },
  });
}

export function useRegistrationTrend(days: number = 30) {
  return useQuery({
    queryKey: ["admin", "registrations", days],
    queryFn: () => adminApi.getRegistrationTrend(days),
    refetchInterval: 120000,
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

export function useActivityFeed(limit: number = 50) {
  return useQuery({
    queryKey: ["admin", "activity", limit],
    queryFn: () => adminApi.getActivityFeed(limit),
    refetchInterval: 60000,
  });
}

export function useAuditLog(limit: number = 50) {
  return useQuery({
    queryKey: ["admin", "audit-log", limit],
    queryFn: () => adminApi.getAuditLog(limit),
  });
}

export function useBroadcast() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ subject, body }: { subject: string; body: string }) =>
      adminApi.sendBroadcast(subject, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "audit-log"] });
    },
  });
}

// Waitlist
export function useWaitlist(params?: {
  status?: WaitlistStatus | "all";
  skip?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["admin", "waitlist", params],
    queryFn: () => adminApi.getWaitlist(params),
    placeholderData: keepPreviousData,
    refetchInterval: 60000,
  });
}

export function useInviteWaitlistEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminApi.inviteWaitlistEntry(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "waitlist"] });
    },
    onError: (err) => toastError(err, "Failed to invite user"),
  });
}

export function useInviteWaitlistBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => adminApi.inviteWaitlistBatch(ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "waitlist"] });
    },
    onError: (err) => toastError(err, "Failed to invite users"),
  });
}

export function useEmailHealth() {
  return useQuery({
    queryKey: ["admin", "email-health"],
    queryFn: () => adminApi.getEmailHealth(false),
    staleTime: 5 * 60 * 1000, // 5 minutes – DNS records don't change often
  });
}

export function useRefreshEmailHealth() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => adminApi.getEmailHealth(true),
    onSuccess: (data) => {
      qc.setQueryData(["admin", "email-health"], data);
    },
  });
}
