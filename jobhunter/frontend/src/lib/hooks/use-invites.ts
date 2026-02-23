"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as invitesApi from "@/lib/api/invites";

export function useInvites() {
  return useQuery({
    queryKey: ["invites"],
    queryFn: invitesApi.listInvites,
  });
}

export function useCreateInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: invitesApi.createInvite,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invites"] });
    },
  });
}

export function useValidateInvite(code: string | null) {
  return useQuery({
    queryKey: ["invite-validate", code],
    queryFn: () => invitesApi.validateInvite(code!),
    enabled: !!code,
    retry: false,
  });
}
