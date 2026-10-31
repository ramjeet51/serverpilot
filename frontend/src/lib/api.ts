import { env } from "@/lib/env";
import type { User } from "@/lib/types";

const CSRF_KEY = "sp.csrf";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let accessToken: string | null = null;

export function getAccessToken() {
  return accessToken;
}

export function setSession(token: string, csrf: string) {
  accessToken = token;
  sessionStorage.setItem(CSRF_KEY, csrf);
}

export function clearSession() {
  accessToken = null;
  sessionStorage.removeItem(CSRF_KEY);
}

function csrf() {
  return typeof window === "undefined" ? null : sessionStorage.getItem(CSRF_KEY);
}

type Envelope<T> = { success: boolean; data: T; meta?: unknown; error?: { code: string; message: string; details?: unknown } };

async function parse<T>(response: Response): Promise<T> {
  const body = (await response.json().catch(() => null)) as Envelope<T> | null;
  if (!response.ok || !body?.success) {
    throw new ApiError(response.status, body?.error?.code ?? "error", body?.error?.message ?? "Request failed", body?.error?.details);
  }
  return body.data;
}

let refreshing: Promise<User | null> | null = null;

export function refreshSession(): Promise<User | null> {
  if (!csrf()) return Promise.resolve(null);
  if (!refreshing) {
    refreshing = (async () => {
      const response = await fetch(`${env.apiUrl}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf() ?? "" },
      });
      if (!response.ok) {
        clearSession();
        return null;
      }
      const data = await parse<{ access_token: string; csrf_token: string; user: User }>(response);
      setSession(data.access_token, data.csrf_token);
      return data.user;
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const token = csrf();
  if (token) headers.set("X-CSRF-Token", token);

  const response = await fetch(`${env.apiUrl}${path}`, { ...init, headers, credentials: "include" });
  if (response.status === 401 && retry && !path.startsWith("/api/v1/auth/")) {
    const user = await refreshSession();
    if (user) return api<T>(path, init, false);
  }
  return parse<T>(response);
}
