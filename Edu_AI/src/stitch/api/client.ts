export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8001").replace(/\/$/, "");
const AUTH_STORAGE_KEY = "edu-ai-auth";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function apiErrorDetail(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    const messages = value.map((item) => apiErrorDetail(item)).filter(Boolean);
    return messages.join("；") || "请求失败";
  }
  if (value && typeof value === "object") {
    const detail = value as { msg?: unknown; message?: unknown; detail?: unknown };
    if (detail.msg) return apiErrorDetail(detail.msg);
    if (detail.message) return apiErrorDetail(detail.message);
    if (detail.detail) return apiErrorDetail(detail.detail);
  }
  return "请求失败";
}

function getAuthToken() {
  if (typeof window === "undefined") return null;

  try {
    const stored = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as { token?: string };
    return parsed.token || null;
  } catch {
    return null;
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}) {
  const token = getAuthToken();
  const headers = new Headers(init.headers || {});

  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? apiErrorDetail((payload as { detail?: unknown }).detail)
        : "请求失败";
    throw new ApiError(detail, response.status);
  }

  return payload as T;
}

export async function apiBlob(path: string): Promise<Blob> {
  const token = getAuthToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (!response.ok) {
    let detail = "下载失败";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (payload.detail) detail = String(payload.detail);
    } catch {
      // Keep the stable fallback for non-JSON proxy errors.
    }
    throw new ApiError(detail, response.status);
  }
  return response.blob();
}
