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
  isOnboarded: boolean;
  isTourCompleted: boolean;
  completeOnboarding: () => Promise<void>;
  completeTour: () => Promise<void>;
  resetTour: () => void;
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
      try {
        localStorage.setItem("access_token", tokens.access_token);
        localStorage.setItem("refresh_token", tokens.refresh_token);
      } catch {
        console.warn("localStorage unavailable — session will not persist across tabs");
      }
      const me = await authApi.getMe();
      setUser(me);
      router.push(me.onboarding_completed ? "/dashboard" : "/onboarding");
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
    } catch (err) {
      if (localStorage.getItem("access_token")) {
        console.warn("Failed to refresh user profile", err);
      }
    }
  }, []);

  const completeOnboarding = useCallback(async () => {
    const updated = await authApi.completeOnboarding();
    setUser(updated);
  }, []);

  const completeTour = useCallback(async () => {
    const updated = await authApi.completeTour();
    setUser(updated);
  }, []);

  const resetTour = useCallback(() => {
    if (user) {
      setUser({ ...user, tour_completed: false, tour_completed_at: null });
    }
  }, [user]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isOnboarded: !!(user?.onboarding_completed),
        isTourCompleted: !!(user?.tour_completed),
        login,
        register,
        logout,
        updateProfile,
        refreshUser,
        completeOnboarding,
        completeTour,
        resetTour,
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
