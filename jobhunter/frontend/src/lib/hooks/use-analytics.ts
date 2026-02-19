"use client";

import { useQuery } from "@tanstack/react-query";
import * as analyticsApi from "@/lib/api/analytics";

export function useFunnel() {
  return useQuery({
    queryKey: ["funnel"],
    queryFn: analyticsApi.getFunnel,
  });
}

export function useOutreachStats() {
  return useQuery({
    queryKey: ["outreach-stats"],
    queryFn: analyticsApi.getOutreachStats,
  });
}

export function usePipelineStats() {
  return useQuery({
    queryKey: ["pipeline-stats"],
    queryFn: analyticsApi.getPipelineStats,
  });
}
