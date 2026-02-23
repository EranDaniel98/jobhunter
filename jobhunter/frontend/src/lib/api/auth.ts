import api from "./client";
import type { CandidateResponse, CandidateUpdate, TokenPair } from "../types";

export async function login(email: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>("/auth/login", { email, password });
  return data;
}

export async function register(
  email: string,
  password: string,
  full_name: string,
  invite_code: string
): Promise<CandidateResponse> {
  const { data } = await api.post<CandidateResponse>("/auth/register", {
    email,
    password,
    full_name,
    invite_code,
  });
  return data;
}

export async function refresh(refresh_token: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>("/auth/refresh", { refresh_token });
  return data;
}

export async function logout(): Promise<void> {
  await api.post("/auth/logout");
}

export async function getMe(): Promise<CandidateResponse> {
  const { data } = await api.get<CandidateResponse>("/auth/me");
  return data;
}

export async function updateMe(updates: CandidateUpdate): Promise<CandidateResponse> {
  const { data } = await api.patch<CandidateResponse>("/auth/me", updates);
  return data;
}
