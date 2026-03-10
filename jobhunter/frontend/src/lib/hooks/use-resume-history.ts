"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as candidatesApi from "@/lib/api/candidates";

export function useResumes() {
  return useQuery({
    queryKey: ["resumes"],
    queryFn: candidatesApi.listResumes,
  });
}

export function useDeleteResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => candidatesApi.deleteResume(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resumes"] });
    },
  });
}
