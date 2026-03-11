import api from "./client";

export interface CheckoutResponse {
  status: string;
  url: string | null;
  message: string | null;
}

export interface SubscriptionResponse {
  tier: string;
  status: string;
  current_period_end: string | null;
  stripe_subscription_id: string | null;
}

export interface PortalResponse {
  url: string;
}

export async function createCheckout(tier: string): Promise<CheckoutResponse> {
  const { data } = await api.post<CheckoutResponse>(
    "/billing/create-checkout-session",
    { tier },
  );
  return data;
}

export async function createPortal(): Promise<PortalResponse> {
  const { data } = await api.get<PortalResponse>("/billing/portal");
  return data;
}

export async function getSubscription(): Promise<SubscriptionResponse> {
  const { data } = await api.get<SubscriptionResponse>(
    "/billing/subscription",
  );
  return data;
}
