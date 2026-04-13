import api from "./client";
import type {
  CompanyDossierResponse,
  CompanyListResponse,
  CompanyResponse,
  ContactResponse,
} from "../types";

export interface DiscoverFilters {
  industries?: string[];
  locations?: string[];
  company_size?: string;
  keywords?: string;
}

export async function discoverCompanies(filters?: DiscoverFilters): Promise<CompanyListResponse> {
  const { data } = await api.post<CompanyListResponse>("/companies/discover", filters || {});
  return data;
}

export async function addCompany(domain: string): Promise<CompanyResponse> {
  const { data } = await api.post<CompanyResponse>("/companies/add", { domain });
  return data;
}

export async function listCompanies(params?: {
  status?: string;
  skip?: number;
  limit?: number;
}): Promise<CompanyListResponse> {
  const { data } = await api.get<CompanyListResponse>("/companies", { params });
  return data;
}

export async function getCompany(id: string): Promise<CompanyResponse> {
  const { data } = await api.get<CompanyResponse>(`/companies/${id}`);
  return data;
}

export async function approveCompany(id: string): Promise<CompanyResponse> {
  const { data } = await api.post<CompanyResponse>(`/companies/${id}/approve`);
  return data;
}

export async function rejectCompany(id: string, reason: string): Promise<CompanyResponse> {
  const { data } = await api.post<CompanyResponse>(`/companies/${id}/reject`, { reason });
  return data;
}

export async function getDossier(companyId: string): Promise<CompanyDossierResponse> {
  const { data } = await api.get<CompanyDossierResponse>(`/companies/${companyId}/dossier`);
  return data;
}

export async function getCompanyContacts(companyId: string): Promise<ContactResponse[]> {
  const { data } = await api.get<ContactResponse[]>(`/companies/${companyId}/contacts`);
  return data;
}

export interface CompanyNoteResponse {
  id: string;
  company_id: string;
  content: string;
}

export async function getCompanyNotes(companyId: string): Promise<CompanyNoteResponse | null> {
  const { data } = await api.get<CompanyNoteResponse | null>(`/companies/${companyId}/notes`);
  return data;
}

export async function upsertCompanyNotes(companyId: string, content: string): Promise<CompanyNoteResponse> {
  const { data } = await api.put<CompanyNoteResponse>(`/companies/${companyId}/notes`, { content });
  return data;
}
