import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const client = axios.create({
  baseURL: API_URL,
});

const TOKEN_KEY = "acewin_crm_token";
const LANGUAGE_KEY = "acewin-language";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // The analytics and Copilot APIs localize their human-readable fields.
  // Add the active UI language to every request so callers stay simple.
  const lang = localStorage.getItem(LANGUAGE_KEY) === "fa" ? "fa" : "en";
  if (config.params instanceof URLSearchParams) {
    config.params.set("lang", lang);
  } else {
    config.params = { ...(config.params ?? {}), lang };
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
    // Entitlement errors (402) carry a structured object instead of a
    // plain string -- see backend app/billing/entitlements.py and
    // types.ts:EntitlementErrorDetail. Still just a string for a plain
    // toast; callers that want the upgrade_to plan for a richer prompt
    // should read error.response.data.detail directly instead of going
    // through this helper.
    if (detail && typeof detail === "object" && typeof detail.message === "string") {
      return detail.message;
    }
  }
  return "Something went wrong. Please try again.";
}

/** Pulls the structured entitlement-error payload out of an axios error,
 * or null if this wasn't one (a normal validation/not-found error, a
 * network error, etc.) -- lets a component show an "Upgrade to Pro"
 * button instead of (or alongside) a plain toast. */
export function entitlementError(error: unknown): { code: string; message: string; details: Record<string, unknown> } | null {
  if (!axios.isAxiosError(error) || error.response?.status !== 402) return null;
  const detail = error.response?.data?.detail;
  if (detail && typeof detail === "object" && typeof detail.code === "string") {
    return detail;
  }
  return null;
}
