"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as applyApi from "@/lib/api/apply";
import { toastError } from "@/lib/api/error-utils";
import { toast } from "sonner";

export function useJobPostings() {
  return useQuery({
    queryKey: ["job-postings"],
    queryFn: () => applyApi.listPostings(),
  });
}

export function useApplyAnalysis(postingId: string | null) {
  return useQuery({
    queryKey: ["apply-analysis", postingId],
    queryFn: () => applyApi.getAnalysis(postingId!),
    enabled: !!postingId,
    retry: (failureCount, error: any) => {
      // Don't retry 202 (still processing) or 404
      if (error?.response?.status === 202 || error?.response?.status === 404) return false;
      return failureCount < 3;
    },
    refetchInterval: (query) => {
      // Poll while analysis is pending
      if (query.state.error && (query.state.error as any)?.response?.status === 202) {
        return 3000;
      }
      return false;
    },
  });
}

export function useAnalyzeJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: applyApi.analyzeJobPosting,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job-postings"] });
      toast.success("Analyzing job posting...");
    },
    onError: (err) => toastError(err, "Failed to analyze job posting"),
  });
}
