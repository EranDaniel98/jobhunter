"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import * as incidentsApi from "@/lib/api/incidents";
import { toastError } from "@/lib/api/error-utils";
import { toast } from "sonner";

export function useSubmitIncident() {
  return useMutation({
    mutationFn: incidentsApi.submitIncident,
    onSuccess: (data) => {
      if (data.github_issue_url) {
        toast.success("Incident submitted", {
          description: "A GitHub issue has been created.",
          action: {
            label: "View",
            onClick: () => window.open(data.github_issue_url!, "_blank"),
          },
        });
      } else {
        toast.success("Incident submitted", {
          description: "We'll look into it shortly.",
        });
      }
    },
    onError: (err: unknown) => {
      toastError(err, "Failed to submit incident");
    },
  });
}

export function useIncidentStats() {
  return useQuery({
    queryKey: ["incident-stats"],
    queryFn: incidentsApi.getIncidentStats,
  });
}
