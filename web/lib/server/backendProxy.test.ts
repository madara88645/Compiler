import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { proxyBackendRequest, resolveBackendApiBase } from "./backendProxy";

describe("backend proxy", () => {
  beforeEach(() => {
    delete process.env.INTERNAL_API_URL;
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.PROMPTC_SERVER_API_KEY;
    delete process.env.ADMIN_API_KEY;
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

  it("injects the server API key when proxying protected routes", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";
    process.env.PROMPTC_SERVER_API_KEY = "server-secret";

    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ system_prompt: "safe" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const request = new Request("http://localhost:3000/agent-generator/generate", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ description: "review code" }),
    });

    const response = await proxyBackendRequest(request, "/agent-generator/generate", {
      requireServerApiKey: true,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, init] = fetchMock.mock.calls[0]!;
    const proxiedHeaders = new Headers(init?.headers);

    expect(url).toBe("https://api.memo.dev/agent-generator/generate");
    expect(proxiedHeaders.get("x-api-key")).toBe("server-secret");
    expect(proxiedHeaders.get("content-type")).toBe("application/json");
    await expect(response.json()).resolves.toEqual({ system_prompt: "safe" });
  });

  it("returns a config error when a protected route has no server API key", async () => {
    const request = new Request("http://localhost:3000/agent-generator/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: "review code" }),
    });

    const response = await proxyBackendRequest(request, "/agent-generator/generate", {
      requireServerApiKey: true,
    });

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      detail: "PROMPTC_SERVER_API_KEY is not configured on the web server.",
    });
  });
});
