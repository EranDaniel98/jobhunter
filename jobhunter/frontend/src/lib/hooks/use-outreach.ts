"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as outreachApi from "@/lib/api/outreach";

export function useMessages(params?: { status?: string; channel?: string }) {
  return useQuery({
    queryKey: ["messages", params],
    queryFn: () => outreachApi.listMessages(params),
  });
}

export function useMessage(id: string) {
  return useQuery({
    queryKey: ["message", id],
    queryFn: () => outreachApi.getMessage(id),
    enabled: !!id,
  });
}

export function useDraftMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, language }: { contactId: string; language?: string }) =>
      outreachApi.draftMessage(contactId, language),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages"] });
    },
  });
}

export function useDraftFollowup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) => outreachApi.draftFollowup(messageId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages"] });
    },
  });
}

export function useDraftLinkedIn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, language }: { contactId: string; language?: string }) =>
      outreachApi.draftLinkedIn(contactId, language),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages"] });
    },
  });
}

export function useEditMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...updates }: { id: string; subject?: string; body?: string }) =>
      outreachApi.editMessage(id, updates),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["messages"] });
      qc.invalidateQueries({ queryKey: ["message", id] });
    },
  });
}

export function useSendMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, attachResume }: { id: string; attachResume?: boolean }) =>
      outreachApi.sendMessage(id, attachResume),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["messages"] });
      qc.invalidateQueries({ queryKey: ["message", id] });
    },
  });
}

export function useMarkReplied() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => outreachApi.markReplied(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["messages"] });
      qc.invalidateQueries({ queryKey: ["message", id] });
    },
  });
}

export function useDraftVariants() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, language }: { contactId: string; language?: string }) =>
      outreachApi.draftVariants(contactId, language),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages"] });
    },
  });
}

export function useDeleteMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => outreachApi.deleteMessage(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages"] });
    },
  });
}
