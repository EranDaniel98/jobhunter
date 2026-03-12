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
  invite_code: string,
  preferences?: Record<string, unknown>
): Promise<CandidateResponse> {
  const { data } = await api.post<CandidateResponse>("/auth/register", {
    email,
    password,
    full_name,
    invite_code,
    preferences,
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

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.post("/auth/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function verifyEmail(token: string): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>("/auth/verify", null, {
    params: { token },
  });
  return data;
}

export async function resendVerification(): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>("/auth/resend-verification");
  return data;
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>("/auth/forgot-password", { email });
  return data;
}

export async function resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>("/auth/reset-password", {
    token,
    new_password: newPassword,
  });
  return data;
}
