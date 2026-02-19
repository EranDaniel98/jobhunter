import api from "./client";
import type { FunnelResponse, OutreachStatsResponse, PipelineStatsResponse } from "../types";

export async function getFunnel(): Promise<FunnelResponse> {
  const { data } = await api.get<FunnelResponse>("/analytics/funnel");
  return data;
}

export async function getOutreachStats(): Promise<OutreachStatsResponse> {
  const { data } = await api.get<OutreachStatsResponse>("/analytics/outreach");
  return data;
}

export async function getPipelineStats(): Promise<PipelineStatsResponse> {
  const { data } = await api.get<PipelineStatsResponse>("/analytics/pipeline");
  return data;
}
