import api from "./client";
import type { IncidentResponse, IncidentStats } from "../types";

export async function submitIncident(formData: FormData): Promise<IncidentResponse> {
  const { data } = await api.post<IncidentResponse>("/incidents", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getIncidentStats(): Promise<IncidentStats> {
  const { data } = await api.get<IncidentStats>("/incidents/stats");
  return data;
}
