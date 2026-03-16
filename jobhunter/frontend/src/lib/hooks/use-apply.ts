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

export function useApplyAnalysis(postingId: string | null, isInProgress?: boolean) {
  return useQuery({
    queryKey: ["apply-analysis", postingId],
    queryFn: async () => {
      const result = await applyApi.getAnalysis(postingId!);
      // Backend returns {status: "pending", detail: "..."} with 202 for in-progress analyses.
      // Axios treats 202 as success, so we check the shape and return null to signal "still pending".
      if (result && "detail" in result && (result as Record<string, unknown>).status === "pending") {
        return null;
      }
      return result;
    },
    enabled: !!postingId,
    retry: (failureCount, error: unknown) => {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 404) return false;
      return failureCount < 3;
    },
    refetchInterval: (query) => {
      // Poll while analysis is still pending (null data means 202 in-progress),
      // or while the posting status indicates analysis is in progress
      if ((query.state.data === null && !query.state.error) || isInProgress) {
        return 3000;
      }
      return false;
    },
  });
}

export function useScrapeUrl() {
  return useMutation({
    mutationFn: (url: string) => applyApi.scrapeUrl(url),
    onError: (err) => toastError(err, "Failed to fetch job posting"),
  });
}

export function useUpdatePostingStage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ postingId, stage }: { postingId: string; stage: string }) =>
      applyApi.updatePostingStage(postingId, stage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job-postings"] });
    },
    onError: (err) => toastError(err, "Failed to update stage"),
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

export function useDeletePosting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (postingId: string) => applyApi.deletePosting(postingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job-postings"] });
    },
    onError: (err) => toastError(err, "Failed to delete posting"),
  });
}
