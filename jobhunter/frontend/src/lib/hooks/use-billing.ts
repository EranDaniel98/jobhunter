"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { createCheckout, createPortal, getSubscription } from "../api/billing";
import { toastError } from "../api/error-utils";
import { toast } from "sonner";

export function useSubscription() {
  return useQuery({
    queryKey: ["subscription"],
    queryFn: getSubscription,
    retry: (failureCount, error: unknown) => {
      const status = (error as { response?: { status?: number } })?.response?.status;
      // Don't retry if the endpoint doesn't exist yet (404) or no subscription (404)
      if (status === 404) return false;
      return failureCount < 3;
    },
  });
}

export function useCheckout() {
  return useMutation({
    mutationFn: (tier: string) => createCheckout(tier),
    onSuccess: (data) => {
      if (data.status === "coming_soon") {
        toast.info("Paid plans are coming soon! Enjoy the free tier for now.");
        return;
      }
      if (data.url) window.location.href = data.url;
    },
    onError: (err) => toastError(err, "Failed to start checkout"),
  });
}

export function usePortal() {
  return useMutation({
    mutationFn: () => createPortal(),
    onSuccess: (data) => {
      window.location.href = data.url;
    },
    onError: (err) => toastError(err, "Failed to open billing portal"),
  });
}
