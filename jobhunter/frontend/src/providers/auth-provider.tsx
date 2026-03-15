"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import * as authApi from "@/lib/api/auth";
import type { CandidateResponse, CandidateUpdate } from "@/lib/types";

interface AuthContextType {
  user: CandidateResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, inviteCode: string, preferences?: Record<string, unknown>) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (updates: CandidateUpdate) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CandidateResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = localStorage.getItem("access_token");
      if (token) {
        try {
          const me = await authApi.getMe();
          if (!cancelled) setUser(me);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        }
      }
      if (!cancelled) setIsLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authApi.login(email, password);
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      const me = await authApi.getMe();
      setUser(me);
      router.push("/dashboard");
    },
    [router]
  );

  const register = useCallback(
    async (email: string, password: string, fullName: string, inviteCode: string, preferences?: Record<string, unknown>) => {
      await authApi.register(email, password, fullName, inviteCode, preferences);
      // Auto-login after register
      await login(email, password);
    },
    [login]
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore logout errors
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
    router.push("/login");
  }, [router]);

  const updateProfile = useCallback(async (updates: CandidateUpdate) => {
    const updated = await authApi.updateMe(updates);
    setUser(updated);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await authApi.getMe();
      setUser(me);
    } catch {
      // Ignore - user may not be authenticated
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        updateProfile,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
