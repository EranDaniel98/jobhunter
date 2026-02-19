import api from "./client";
import type { CandidateDNAResponse, ResumeUploadResponse, SkillResponse } from "../types";

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<ResumeUploadResponse>("/candidates/resume", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getDNA(): Promise<CandidateDNAResponse> {
  const { data } = await api.get<CandidateDNAResponse>("/candidates/me/dna");
  return data;
}

export async function getSkills(): Promise<SkillResponse[]> {
  const { data } = await api.get<SkillResponse[]>("/candidates/me/skills");
  return data;
}
