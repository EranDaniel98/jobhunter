"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as approvalsApi from "@/lib/api/approvals";

export function useApprovals(params?: { status?: string; action_type?: string }) {
  return useQuery({
    queryKey: ["approvals", params],
    queryFn: () => approvalsApi.listApprovals(params),
  });
}

export function useApprovalCount() {
  return useQuery({
    queryKey: ["approvals", "count"],
    queryFn: () => approvalsApi.getApprovalCount(),
    refetchInterval: 60_000, // Poll every 60s as fallback
  });
}

export function useApproveAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => approvalsApi.approveAction(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
      qc.invalidateQueries({ queryKey: ["messages"] });
    },
  });
}

export function useRejectAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => approvalsApi.rejectAction(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
  });
}
