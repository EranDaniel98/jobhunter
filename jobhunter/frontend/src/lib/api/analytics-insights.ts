import api from "./client";
import type { AnalyticsInsightListResponse, AnalyticsDashboardResponse } from "@/lib/types";

export async function getDashboard() {
  const { data } = await api.get<AnalyticsDashboardResponse>("/analytics/dashboard");
  return data;
}

export async function getInsights(unreadOnly = false) {
  const { data } = await api.get<AnalyticsInsightListResponse>("/analytics/insights", {
    params: { unread_only: unreadOnly },
  });
  return data;
}

export async function refreshInsights() {
  const { data } = await api.post("/analytics/insights/refresh");
  return data;
}

export async function markInsightRead(id: string) {
  const { data } = await api.patch(`/analytics/insights/${id}/read`);
  return data;
}
