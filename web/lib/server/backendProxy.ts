const DEFAULT_BACKEND_API_BASE = "http://127.0.0.1:8080";
const CONFIG_ERROR_DETAIL = "PROMPTC_SERVER_API_KEY is not configured on the web server.";
const NETWORK_ERROR_DETAIL = "Could not reach the backend from the web server.";
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
  requireServerApiKey?: boolean;
};

function resolveServerApiKey(): string {
  return (
    process.env.PROMPTC_SERVER_API_KEY?.trim() ||
    process.env.ADMIN_API_KEY?.trim() ||
    ""
  );
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

async function cloneProxyResponse(response: Response): Promise<Response> {
  const headers = new Headers(response.headers);
  headers.delete("content-length");
  return new Response(await response.arrayBuffer(), {
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

  if (options.requireServerApiKey && !serverApiKey) {
    return Response.json({ detail: CONFIG_ERROR_DETAIL }, { status: 500 });
  }

  const headers = copyProxyHeaders(request);
  if (serverApiKey) {
    headers.set("x-api-key", serverApiKey);
  }

  const targetUrl = `${resolveBackendApiBase()}${backendPath}`;

  try {
    const upstreamResponse = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: isBodylessMethod(request.method) ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
    });

    return cloneProxyResponse(upstreamResponse);
  } catch {
    return Response.json({ detail: NETWORK_ERROR_DETAIL }, { status: 502 });
  }
}
