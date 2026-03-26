// Config for API Connection - Force Rebuild
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8080";

export function buildApiHeaders(headers: HeadersInit = {}): Record<string, string> {
  const mergedHeaders = new Headers(headers);
  return Object.fromEntries(mergedHeaders.entries());
}

export class ApiError extends Error {
  status: number;
  detail: string;
  payload: unknown;

  constructor(status: number, detail: string, payload: unknown) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.payload = payload;
  }
}

function extractDetail(payload: unknown): string | null {
  if (typeof payload === "string" && payload.trim()) {
    return payload.trim();
  }

  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
  }

  return null;
}

export function describeApiError(status: number, payload: unknown): string {
  const detail = extractDetail(payload);

  if (status === 403) {
    return detail || "This action requires a valid API key or additional backend access.";
  }

  if (status === 429) {
    return detail || "Rate limit exceeded. Please retry in a moment.";
  }

  if (status >= 500) {
    return detail || "The backend hit an internal error.";
  }

  return detail || `API Error: ${status}`;
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildApiHeaders(init.headers),
  });
}

async function readApiPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }

  return text;
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init);
  const payload = await readApiPayload(response);

  if (!response.ok) {
    throw new ApiError(response.status, describeApiError(response.status, payload), payload);
  }

  return payload as T;
}
