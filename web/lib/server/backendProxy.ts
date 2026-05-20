const DEFAULT_BACKEND_API_BASE = "http://127.0.0.1:8080";
const DEFAULT_UPSTREAM_TIMEOUT_MS = 25_000;
const NETWORK_ERROR_DETAIL =
  "The service is temporarily unavailable or still waking up. Please retry in a few seconds.";
const TIMEOUT_ERROR_DETAIL =
  "The backend did not respond within the upstream timeout. Please retry shortly.";
const PROXY_ATTEMPTS_HEADER = "x-promptc-proxy-attempts";
const PROXY_DURATION_HEADER = "x-promptc-proxy-duration-ms";
const PROXY_TIMED_OUT_HEADER = "x-promptc-proxy-timed-out";

function resolveUpstreamTimeoutMs(): number {
  const raw = process.env.PROMPTC_PROXY_UPSTREAM_TIMEOUT_MS?.trim();
  if (!raw) return DEFAULT_UPSTREAM_TIMEOUT_MS;
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_UPSTREAM_TIMEOUT_MS;
  return parsed;
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError");
}

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

type ProxyOptions = {
  networkRetryAttempts?: number;
  networkRetryDelayMs?: number;
  retryNetworkErrors?: boolean;
  upstreamTimeoutMs?: number;
};


function isBodylessMethod(method: string): boolean {
  return method === "GET" || method === "HEAD";
}

async function drainRequestBody(request: Request): Promise<void> {
  if (isBodylessMethod(request.method)) return;
  try {
    await request.arrayBuffer();
  } catch {
    // Best effort only; the response path should still complete even if draining fails.
  }
}

function copyProxyHeaders(request: Request): Headers {
  const headers = new Headers();

  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  return headers;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function shouldBufferProxyResponse(response: Response): boolean {
  const contentType = response.headers.get("content-type")?.toLowerCase() || "";
  return contentType.includes("application/json") || contentType.startsWith("text/");
}

function addProxyDiagnostics(headers: Headers, attempts: number, durationMs: number): Headers {
  headers.set(PROXY_ATTEMPTS_HEADER, String(attempts));
  headers.set(PROXY_DURATION_HEADER, String(durationMs));
  return headers;
}

async function cloneProxyResponse(response: Response, attempts: number, durationMs: number): Promise<Response> {
  const headers = new Headers(response.headers);
  headers.delete("content-length");
  addProxyDiagnostics(headers, attempts, durationMs);
  if (shouldBufferProxyResponse(response)) {
    headers.delete("content-encoding");
    return new Response(await response.arrayBuffer(), {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  }
  // Stream large binary responses directly so download-style routes keep the
  // lower-memory behavior from the original optimization.
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export function resolveBackendApiBase(): string {
  return process.env.INTERNAL_API_URL?.trim() || process.env.NEXT_PUBLIC_API_URL?.trim() || DEFAULT_BACKEND_API_BASE;
}

export async function proxyBackendRequest(
  request: Request,
  backendPath: string,
  options: ProxyOptions = {},
): Promise<Response> {
  const requestStartedAt = Date.now();
  const headers = copyProxyHeaders(request);

  const base = resolveBackendApiBase().replace(/\/+$/, "");
  const path = backendPath.startsWith("/") ? backendPath : "/" + backendPath;
  const targetUrl = base + path;
  const retryAttempts = options.retryNetworkErrors ? Math.max(1, options.networkRetryAttempts ?? 3) : 1;
  const retryDelayMs = options.networkRetryDelayMs ?? 1000;
  const upstreamTimeoutMs = options.upstreamTimeoutMs ?? resolveUpstreamTimeoutMs();
  const bufferedBody =
    !isBodylessMethod(request.method) && options.retryNetworkErrors ? await request.arrayBuffer() : null;

  for (let attempt = 0; attempt < retryAttempts; attempt += 1) {
    const controller = new AbortController();
    const timeoutHandle = setTimeout(() => controller.abort(), upstreamTimeoutMs);
    try {
      const init: RequestInit & { duplex?: "half" } = {
        method: request.method,
        headers,
        body: isBodylessMethod(request.method) ? undefined : bufferedBody ?? request.body,
        cache: "no-store",
        redirect: "manual",
        signal: controller.signal,
      };
      if (init.body && !bufferedBody) init.duplex = "half";

      const upstreamResponse = await fetch(targetUrl, init as RequestInit);
      const attemptsUsed = attempt + 1;
      const durationMs = Date.now() - requestStartedAt;

      if (attempt > 0) {
        console.info("[backendProxy] upstream recovered after retry", {
          attempts: attemptsUsed,
          backendPath: path,
          durationMs,
        });
      }

      return await cloneProxyResponse(upstreamResponse, attemptsUsed, durationMs);
    } catch (error) {
      const timedOut = isAbortError(error);
      if (attempt === retryAttempts - 1) {
        const attemptsUsed = attempt + 1;
        const durationMs = Date.now() - requestStartedAt;
        const logLabel = timedOut ? "[backendProxy] upstream timed out" : "[backendProxy] upstream unavailable";
        console.error(logLabel, {
          attempts: attemptsUsed,
          backendPath: path,
          durationMs,
          upstreamTimeoutMs,
          timedOut,
          error: error instanceof Error ? error.message : String(error),
        });
        const diagnosticHeaders = addProxyDiagnostics(new Headers(), attemptsUsed, durationMs);
        if (timedOut) {
          diagnosticHeaders.set(PROXY_TIMED_OUT_HEADER, "1");
          return Response.json(
            { detail: TIMEOUT_ERROR_DETAIL },
            { status: 504, headers: diagnosticHeaders },
          );
        }
        return Response.json(
          { detail: NETWORK_ERROR_DETAIL },
          { status: 502, headers: diagnosticHeaders },
        );
      }

      console.warn("[backendProxy] retrying upstream request", {
        attempt: attempt + 1,
        backendPath: path,
        retryDelayMs: retryDelayMs * (attempt + 1),
        timedOut,
      });
      await sleep(retryDelayMs * (attempt + 1));
    } finally {
      clearTimeout(timeoutHandle);
    }
  }

  const diagnosticHeaders = addProxyDiagnostics(new Headers(), retryAttempts, Date.now() - requestStartedAt);
  return Response.json({ detail: NETWORK_ERROR_DETAIL }, { status: 502, headers: diagnosticHeaders });
}
