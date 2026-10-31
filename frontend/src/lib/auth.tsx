"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api, clearSession, refreshSession, setSession } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (...permissions: string[]) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    refreshSession()
      .then((restored) => {
        if (active) setUser(restored);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo<AuthState>(() => ({
    user,
    loading,
    async login(email, password) {
      const data = await api<{ access_token: string; csrf_token: string; user: User }>(
        "/api/v1/auth/login",
        { method: "POST", body: JSON.stringify({ email, password }) },
        false,
      );
      setSession(data.access_token, data.csrf_token);
      setUser(data.user);
    },
    async logout() {
      try {
        await api("/api/v1/auth/logout", { method: "POST" }, false);
      } finally {
        clearSession();
        setUser(null);
      }
    },
    can(...permissions) {
      if (!user) return false;
      if (user.is_superuser) return true;
      return permissions.every((code) => user.permissions.includes(code));
    },
  }), [user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
