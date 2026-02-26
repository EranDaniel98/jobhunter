"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as insightsApi from "@/lib/api/analytics-insights";
import { toastError } from "@/lib/api/error-utils";
import { toast } from "sonner";

export function useAnalyticsDashboard() {
  return useQuery({
    queryKey: ["analytics-dashboard"],
    queryFn: insightsApi.getDashboard,
  });
}

export function useAnalyticsInsights(unreadOnly = false) {
  return useQuery({
    queryKey: ["analytics-insights", unreadOnly],
    queryFn: () => insightsApi.getInsights(unreadOnly),
  });
}

export function useRefreshInsights() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: insightsApi.refreshInsights,
    onSuccess: () => {
      toast.success("Generating fresh insights...");
      qc.invalidateQueries({ queryKey: ["analytics-insights"] });
      qc.invalidateQueries({ queryKey: ["analytics-dashboard"] });
    },
    onError: (err) => toastError(err, "Failed to refresh insights"),
  });
}

export function useMarkInsightRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: insightsApi.markInsightRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analytics-insights"] });
      qc.invalidateQueries({ queryKey: ["analytics-dashboard"] });
    },
  });
}
