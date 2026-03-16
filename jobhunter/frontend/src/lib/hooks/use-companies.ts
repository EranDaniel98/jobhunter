"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as companiesApi from "@/lib/api/companies";
import { toastError } from "@/lib/api/error-utils";

export function useCompanies(status?: string) {
  return useQuery({
    queryKey: ["companies", status],
    queryFn: () => companiesApi.listCompanies({ status: status || undefined }),
  });
}

export function useCompany(id: string) {
  return useQuery({
    queryKey: ["company", id],
    queryFn: () => companiesApi.getCompany(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.research_status;
      return status === "pending" || status === "in_progress" ? 3000 : false;
    },
  });
}

export function useDossier(companyId: string, enabled = true) {
  return useQuery({
    queryKey: ["dossier", companyId],
    queryFn: () => companiesApi.getDossier(companyId),
    enabled: !!companyId && enabled,
    retry: false,
  });
}

export function useCompanyContacts(companyId: string) {
  return useQuery({
    queryKey: ["contacts", companyId],
    queryFn: () => companiesApi.getCompanyContacts(companyId),
    enabled: !!companyId,
  });
}

export function useDiscoverCompanies() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (filters?: companiesApi.DiscoverFilters) => companiesApi.discoverCompanies(filters),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
  });
}

export function useAddCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (domain: string) => companiesApi.addCompany(domain),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
  });
}

export function useApproveCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => companiesApi.approveCompany(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      qc.invalidateQueries({ queryKey: ["company", id] });
    },
    onError: (err) => toastError(err, "Failed to approve company"),
  });
}

export function useCompanyNotes(companyId: string) {
  return useQuery({
    queryKey: ["company-notes", companyId],
    queryFn: () => companiesApi.getCompanyNotes(companyId),
    enabled: !!companyId,
  });
}

export function useUpsertCompanyNotes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ companyId, content }: { companyId: string; content: string }) =>
      companiesApi.upsertCompanyNotes(companyId, content),
    onSuccess: (_, { companyId }) => {
      qc.invalidateQueries({ queryKey: ["company-notes", companyId] });
    },
  });
}

export function useRejectCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      companiesApi.rejectCompany(id, reason),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      qc.invalidateQueries({ queryKey: ["company", id] });
    },
    onError: (err) => toastError(err, "Failed to reject company"),
  });
}
