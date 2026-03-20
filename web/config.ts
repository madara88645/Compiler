// Config for API Connection - Force Rebuild
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8080";

export function buildApiHeaders(headers: HeadersInit = {}): Record<string, string> {
  const mergedHeaders = new Headers(headers);
  const apiKey = process.env.NEXT_PUBLIC_API_KEY?.trim();

  if (apiKey) {
    mergedHeaders.set("x-api-key", apiKey);
  }

  return Object.fromEntries(mergedHeaders.entries());
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildApiHeaders(init.headers),
  });
}
