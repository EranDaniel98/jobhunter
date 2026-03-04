import api from "./client";
import type { JobPostingResponse, JobPostingListResponse, ApplyAnalysisResponse, ScrapeUrlResponse } from "@/lib/types";

export async function analyzeJobPosting(data: {
  title: string;
  company_name?: string;
  company_id?: string;
  url?: string;
  raw_text: string;
}) {
  const { data: resp } = await api.post<JobPostingResponse>("/apply/analyze", data);
  return resp;
}

export async function listPostings(skip = 0, limit = 20) {
  const { data } = await api.get<JobPostingListResponse>("/apply/postings", { params: { skip, limit } });
  return data;
}

export async function getAnalysis(postingId: string) {
  const { data } = await api.get<ApplyAnalysisResponse>(`/apply/postings/${postingId}/analysis`);
  return data;
}

export async function scrapeUrl(url: string) {
  const { data } = await api.post<ScrapeUrlResponse>("/apply/scrape-url", { url });
  return data;
}
