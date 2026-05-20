import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { proxyBackendRequest, resolveBackendApiBase } from "./backendProxy";

describe("backend proxy", () => {
  beforeEach(() => {
    delete process.env.INTERNAL_API_URL;
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.PROMPTC_PROXY_UPSTREAM_TIMEOUT_MS;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("defaults server-side proxying to the local backend base", () => {
    expect(resolveBackendApiBase()).toBe("http://127.0.0.1:8080");
  });

  it("prefers INTERNAL_API_URL over NEXT_PUBLIC_API_URL on the server", () => {
    process.env.INTERNAL_API_URL = "http://backend:8080";
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

    expect(resolveBackendApiBase()).toBe("http://backend:8080");
  });


  it("buffers JSON responses before returning them to the browser", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

    const upstreamResponse = new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
    const arrayBufferSpy = vi.spyOn(upstreamResponse, "arrayBuffer");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(upstreamResponse);

    const request = new Request("http://localhost:3000/agent-packs/claude", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "x-api-key": "caller-key",
      },
      body: JSON.stringify({ goal: "review code" }),
    });

    const response = await proxyBackendRequest(request, "/agent-packs/claude");

    expect(arrayBufferSpy).toHaveBeenCalledTimes(1);
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it("keeps binary responses streaming", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

    const upstreamResponse = new Response("zip-bytes", {
      status: 200,
      headers: { "content-type": "application/zip" },
    });
    const arrayBufferSpy = vi.spyOn(upstreamResponse, "arrayBuffer");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(upstreamResponse);

    const request = new Request("http://localhost:3000/agent-packs/claude/download", {
      method: "POST",
      headers: {
        Accept: "application/octet-stream",
        "Content-Type": "application/json",
        "x-api-key": "caller-key",
      },
      body: JSON.stringify({ goal: "download code" }),
    });

    const response = await proxyBackendRequest(request, "/agent-packs/claude/download");

    expect(arrayBufferSpy).not.toHaveBeenCalled();
    await expect(response.text()).resolves.toBe("zip-bytes");
  });

  it("retries retryable JSON requests when the first backend fetch throws", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new Error("fetch failed"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );

    const request = new Request("http://localhost:3000/compile", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text: "summarize this" }),
    });

    const response = await proxyBackendRequest(request, "/compile", {
      retryNetworkErrors: true,
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(response.headers.get("x-promptc-proxy-attempts")).toBe("2");
    expect(response.headers.get("x-promptc-proxy-duration-ms")).toBeTruthy();
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it("does not retry non-retryable requests when the backend fetch throws", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("fetch failed"));

    const request = new Request("http://localhost:3000/rag/upload", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "x-api-key": "caller-key",
      },
      body: JSON.stringify({ filename: "README.md", content: "hello" }),
    });

    const response = await proxyBackendRequest(request, "/rag/upload");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(502);
  });



  it("allows proxying with a caller-supplied x-api-key", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const request = new Request("http://localhost:3000/agent-generator/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": "caller-key",
      },
      body: JSON.stringify({ description: "review code" }),
    });

    const response = await proxyBackendRequest(request, "/agent-generator/generate");

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0]!;
    const proxiedHeaders = new Headers(init?.headers);
    expect(proxiedHeaders.get("x-api-key")).toBe("caller-key");
  });


  it("returns a 504 with a timed-out diagnostic header when the upstream fetch hangs past the budget", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      const signal = init?.signal as AbortSignal | undefined;
      return new Promise((_, reject) => {
        if (signal) {
          signal.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        }
        // Never resolve — only the AbortSignal can end this promise.
      });
    });

    const request = new Request("http://localhost:3000/repo-context/github", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: "https://github.com/openai/openai-python" }),
    });

    const startedAt = Date.now();
    const response = await proxyBackendRequest(request, "/repo-context/github", {
      upstreamTimeoutMs: 100,
    });
    const elapsedMs = Date.now() - startedAt;

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(504);
    expect(response.headers.get("x-promptc-proxy-timed-out")).toBe("1");
    expect(response.headers.get("x-promptc-proxy-attempts")).toBe("1");
    expect(elapsedMs).toBeLessThan(2000);
    await expect(response.json()).resolves.toEqual({
      detail: "The backend did not respond within the upstream timeout. Please retry shortly.",
    });
  });

  it("returns a 502 bad gateway when the upstream fetch throws a network error", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("fetch failed"));

    const request = new Request("http://localhost:3000/health", {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    const response = await proxyBackendRequest(request, "/health", {});

    expect(response.status).toBe(502);
    expect(response.headers.get("x-promptc-proxy-attempts")).toBe("1");
    await expect(response.json()).resolves.toEqual({
      detail: "The service is temporarily unavailable or still waking up. Please retry in a few seconds.",
    });
  });
});
