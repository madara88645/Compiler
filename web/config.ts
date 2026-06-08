const DEFAULT_LOCAL_API_BASE = "http://127.0.0.1:8080";
const BACKEND_WAKING_UP_MESSAGE =
  "The service is temporarily unavailable or still waking up. Please retry in a few seconds.";

type LocationLike = {
  hostname: string;
  origin: string;
};

export function buildApiHeaders(headers: HeadersInit = {}): Record<string, string> {
  const mergedHeaders = new Headers(headers);
  return Object.fromEntries(mergedHeaders.entries());
}

export function buildGeneratorApiHeaders(headers: HeadersInit = {}): Record<string, string> {
  return buildApiHeaders(headers);
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

/**
 * Raised by {@link withTimeout} when a wrapped promise does not settle within
 * the allotted time. Surfaced like an AbortError by {@link describeRequestError}.
 */
export class TimeoutError extends Error {
  constructor(message = "The request timed out.") {
    super(message);
    this.name = "TimeoutError";
  }
}

/**
 * Opt-in client-side timeout wrapper. Races `promise` against a timer; if the
 * timer wins it invokes `onTimeout` (e.g. to abort an in-flight request) and
 * rejects with a {@link TimeoutError}. Handlers are always attached to
 * `promise`, so a losing rejection can never surface as an unhandled rejection.
 *
 * This does not alter `apiFetch`/`apiJson` default behavior — callers opt in by
 * wrapping a request promise and passing their own timeout.
 */
export function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  onTimeout?: () => void,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      try {
        onTimeout?.();
      } finally {
        reject(new TimeoutError());
      }
    }, timeoutMs);

    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

export function resolveApiBase(locationLike?: LocationLike | null): string {
  const runtimeLocation =
    locationLike ?? (typeof window !== "undefined" ? window.location : undefined);

  if (runtimeLocation) {
    return runtimeLocation.origin;
  }

  const configuredBase = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configuredBase) {
    return configuredBase;
  }

  return DEFAULT_LOCAL_API_BASE;
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

type RequestErrorCopy = {
  fallback?: string;
  network?: string;
  timeout?: string;
};

export function describeRequestError(
  error: unknown,
  copy: RequestErrorCopy = {},
): string {
  if (error instanceof ApiError) {
    return error.detail;
  }

  if (error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError")) {
    return copy.timeout || "The backend took too long to respond.";
  }

  if (error instanceof Error) {
    const normalizedMessage = error.message.trim().toLowerCase();
    if (
      normalizedMessage === "failed to fetch" ||
      normalizedMessage.includes("networkerror") ||
      normalizedMessage.includes("load failed")
    ) {
      return copy.network || BACKEND_WAKING_UP_MESSAGE;
    }

    return error.message;
  }

  return copy.fallback || "Connection failed.";
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${resolveApiBase()}${path}`, {
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
