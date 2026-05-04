import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET as healthRoute } from "./health/route";
import { POST as compileRoute } from "./compile/route";
import { POST as agentGenerateRoute } from "./agent-generator/generate/route";
import { POST as skillsGenerateRoute } from "./skills-generator/generate/route";
import { POST as ragUploadRoute } from "./rag/upload/route";
import { POST as ragIngestRoute } from "./rag/ingest/route";

type RouteCase = {
  name: string;
  handler: (request: Request) => Promise<Response>;
  requestUrl: string;
  requestBody?: Record<string, unknown>;
  expectedUrl: string;
};

describe("Next backend proxy route wiring", () => {
  beforeEach(() => {
    delete process.env.INTERNAL_API_URL;
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.PROMPTC_SERVER_API_KEY;
    delete process.env.ADMIN_API_KEY;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("forwards public health requests without requiring a server API key", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await healthRoute(
      new Request("http://localhost:3000/health", {
        method: "GET",
        headers: { Accept: "application/json" },
      }),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, init] = fetchMock.mock.calls[0]!;
    const proxiedHeaders = new Headers(init?.headers);

    expect(url).toBe("http://127.0.0.1:8080/health");
    expect(init?.method).toBe("GET");
    expect(proxiedHeaders.has("x-api-key")).toBe(false);
    await expect(response.json()).resolves.toEqual({ status: "ok" });
  });

  it("forwards public compile requests to the compile backend path", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ system_prompt: "safe" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await compileRoute(
      new Request("http://localhost:3000/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "summarize this" }),
      }),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8080/compile");
    await expect(response.json()).resolves.toEqual({ system_prompt: "safe" });
  });

  it.each<RouteCase>([
    {
      name: "agent generation",
      handler: agentGenerateRoute,
      requestUrl: "http://localhost:3000/agent-generator/generate",
      requestBody: { description: "review this PR" },
      expectedUrl: "https://api.memo.dev/agent-generator/generate",
    },
    {
      name: "skills generation",
      handler: skillsGenerateRoute,
      requestUrl: "http://localhost:3000/skills-generator/generate",
      requestBody: { description: "search docs" },
      expectedUrl: "https://api.memo.dev/skills-generator/generate",
    },
    {
      name: "RAG upload",
      handler: ragUploadRoute,
      requestUrl: "http://localhost:3000/rag/upload",
      requestBody: { filename: "README.md", content: "hello" },
      expectedUrl: "https://api.memo.dev/rag/upload",
    },
    {
      name: "RAG ingest",
      handler: ragIngestRoute,
      requestUrl: "http://localhost:3000/rag/ingest",
      requestBody: { path: "docs/README.md" },
      expectedUrl: "https://api.memo.dev/rag/ingest",
    },
  ])("returns a config error when $name route is missing a server API key", async ({ handler, requestUrl, requestBody }) => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await handler(
      new Request(requestUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      }),
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      detail: "PROMPTC_SERVER_API_KEY is not configured on the web server.",
    });
  });

  it.each<RouteCase>([
    {
      name: "agent generation",
      handler: agentGenerateRoute,
      requestUrl: "http://localhost:3000/agent-generator/generate",
      requestBody: { description: "review this PR" },
      expectedUrl: "https://api.memo.dev/agent-generator/generate",
    },
    {
      name: "skills generation",
      handler: skillsGenerateRoute,
      requestUrl: "http://localhost:3000/skills-generator/generate",
      requestBody: { description: "search docs" },
      expectedUrl: "https://api.memo.dev/skills-generator/generate",
    },
    {
      name: "RAG upload",
      handler: ragUploadRoute,
      requestUrl: "http://localhost:3000/rag/upload",
      requestBody: { filename: "README.md", content: "hello" },
      expectedUrl: "https://api.memo.dev/rag/upload",
    },
    {
      name: "RAG ingest",
      handler: ragIngestRoute,
      requestUrl: "http://localhost:3000/rag/ingest",
      requestBody: { path: "docs/README.md" },
      expectedUrl: "https://api.memo.dev/rag/ingest",
    },
  ])("injects the server API key and proxies $name to the backend", async ({ handler, requestUrl, requestBody, expectedUrl }) => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";
    process.env.PROMPTC_SERVER_API_KEY = "server-secret";

    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await handler(
      new Request(requestUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      }),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, init] = fetchMock.mock.calls[0]!;
    const proxiedHeaders = new Headers(init?.headers);

    expect(url).toBe(expectedUrl);
    expect(proxiedHeaders.get("x-api-key")).toBe("server-secret");
    expect(proxiedHeaders.get("content-type")).toBe("application/json");
    await expect(response.json()).resolves.toEqual({ ok: true });
  });
});
