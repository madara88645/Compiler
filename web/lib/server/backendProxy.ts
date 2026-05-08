const DEFAULT_BACKEND_API_BASE = "http://127.0.0.1:8080";
const CONFIG_ERROR_DETAIL = "PROMPTC_SERVER_API_KEY is not configured on the web server.";
const NETWORK_ERROR_DETAIL = "Could not reach the backend from the web server.";

if (!process.env.PROMPTC_SERVER_API_KEY?.trim()) {
  console.warn("PROMPTC_SERVER_API_KEY not set - protected proxy routes will forward no API key");
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
  requireServerApiKey?: boolean;
  retryNetworkErrors?: boolean;
};

function resolveServerApiKey(): string {
  return process.env.PROMPTC_SERVER_API_KEY?.trim() || "";
}

function isBodylessMethod(method: string): boolean {
  return method === "GET" || method === "HEAD";
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

async function cloneProxyResponse(response: Response): Promise<Response> {
  const headers = new Headers(response.headers);
  headers.delete("content-length");
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
  const serverApiKey = resolveServerApiKey();
  const callerApiKey = request.headers.get("x-api-key")?.trim() || "";

  if (options.requireServerApiKey && !serverApiKey && !callerApiKey) {
    return Response.json({ detail: CONFIG_ERROR_DETAIL }, { status: 500 });
  }

  const headers = copyProxyHeaders(request);
  if (serverApiKey) {
    headers.set("x-api-key", serverApiKey);
  }

  const base = resolveBackendApiBase().replace(/\/+$/, "");
  const path = backendPath.startsWith("/") ? backendPath : "/" + backendPath;
  const targetUrl = base + path;
  const retryAttempts = options.retryNetworkErrors ? Math.max(1, options.networkRetryAttempts ?? 3) : 1;
  const retryDelayMs = options.networkRetryDelayMs ?? 1000;
  const bufferedBody =
    !isBodylessMethod(request.method) && options.retryNetworkErrors ? await request.arrayBuffer() : null;

  for (let attempt = 0; attempt < retryAttempts; attempt += 1) {
    try {
      const init: RequestInit & { duplex?: "half" } = {
        method: request.method,
        headers,
        body: isBodylessMethod(request.method) ? undefined : bufferedBody ?? request.body,
        cache: "no-store",
        redirect: "manual",
      };
      if (init.body && !bufferedBody) init.duplex = "half";

      const upstreamResponse = await fetch(targetUrl, init as RequestInit);
      return await cloneProxyResponse(upstreamResponse);
    } catch {
      if (attempt === retryAttempts - 1) {
        return Response.json({ detail: NETWORK_ERROR_DETAIL }, { status: 502 });
      }
      await sleep(retryDelayMs * (attempt + 1));
    }
  }

  return Response.json({ detail: NETWORK_ERROR_DETAIL }, { status: 502 });
}
