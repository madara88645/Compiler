import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as backendProxy from "@/lib/server/backendProxy";
import { GET as healthRoute } from "./health/route";
import { POST as compileRoute } from "./compile/route";
import { POST as agentPacksClaudeRoute } from "./agent-packs/claude/route";
import { POST as agentPacksClaudeDownloadRoute } from "./agent-packs/claude/download/route";
import { POST as agentGenerateRoute } from "./agent-generator/generate/route";
import { POST as agentExportRoute } from "./agent-generator/export/route";
import { POST as benchmarkRunRoute } from "./benchmark/run/route";
import { GET as optimizeGetRoute, POST as optimizeRoute } from "./optimize/route";
import { POST as ragSearchRoute } from "./rag/search/route";
import { GET as ragStatsRoute } from "./rag/stats/route";
import { POST as skillsGenerateRoute } from "./skills-generator/generate/route";
import { POST as skillsExportRoute } from "./skills-generator/export/route";
import { POST as ragUploadRoute } from "./rag/upload/route";
import { POST as ragIngestRoute } from "./rag/ingest/route";
import { POST as repoContextGithubRoute } from "./repo-context/github/route";

type RouteCase = {
  name: string;
  handler: (request: Request) => Promise<Response>;
  requestUrl: string;
  requestMethod?: string;
  requestBody?: Record<string, unknown>;
  expectedUrl: string;
};

const AGENT_PACK_REQUEST_BODY = {
  project_type: "SaaS",
  stack: "FastAPI",
  goal: "Generate a project pack",
  pack_type: "project-pack",
};

describe("Next backend proxy route wiring", () => {
  beforeEach(() => {
    delete process.env.INTERNAL_API_URL;
    delete process.env.NEXT_PUBLIC_API_URL;
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

  it("retries compile requests after a transient backend connection failure", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new Error("fetch failed"))
      .mockResolvedValueOnce(
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

    expect(fetchMock).toHaveBeenCalledTimes(2);
    await expect(response.json()).resolves.toEqual({ system_prompt: "safe" });
  });

  it.each([
    {
      name: "agent packs",
      handler: agentPacksClaudeRoute,
      requestUrl: "http://localhost:3000/agent-packs/claude",
      requestBody: AGENT_PACK_REQUEST_BODY,
      backendPath: "/agent-packs/claude",
    },
    {
      name: "agent pack download",
      handler: agentPacksClaudeDownloadRoute,
      requestUrl: "http://localhost:3000/agent-packs/claude/download",
      requestBody: AGENT_PACK_REQUEST_BODY,
      backendPath: "/agent-packs/claude/download",
    },
  ])("passes the extended upstream timeout to $name routes", async ({
    handler,
    requestUrl,
    requestBody,
    backendPath,
  }) => {
    const proxySpy = vi.spyOn(backendProxy, "proxyBackendRequest").mockResolvedValue(
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

    expect(proxySpy).toHaveBeenCalledTimes(1);
    const [, proxiedPath, proxyOptions] = proxySpy.mock.calls[0]!;
    expect(proxiedPath).toBe(backendPath);
    expect(proxyOptions).toEqual(
      expect.objectContaining({
        retryNetworkErrors: true,
        upstreamTimeoutMs: 60_000,
      }),
    );
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it("keeps compile requests on the default timeout budget", async () => {
    const proxySpy = vi.spyOn(backendProxy, "proxyBackendRequest").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await compileRoute(
      new Request("http://localhost:3000/compile", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: "summarize this" }),
      }),
    );

    expect(proxySpy).toHaveBeenCalledTimes(1);
    const [, proxiedPath, proxyOptions] = proxySpy.mock.calls[0]!;
    expect(proxiedPath).toBe("/compile");
    expect(proxyOptions).toEqual(expect.objectContaining({ retryNetworkErrors: true }));
    expect(proxyOptions).not.toHaveProperty("upstreamTimeoutMs");
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it.each<RouteCase>([
    {
      name: "agent packs",
      handler: agentPacksClaudeRoute,
      requestUrl: "http://localhost:3000/agent-packs/claude",
      requestBody: AGENT_PACK_REQUEST_BODY,
      expectedUrl: "http://127.0.0.1:8080/agent-packs/claude",
    },
    {
      name: "agent pack download",
      handler: agentPacksClaudeDownloadRoute,
      requestUrl: "http://localhost:3000/agent-packs/claude/download",
      requestBody: AGENT_PACK_REQUEST_BODY,
      expectedUrl: "http://127.0.0.1:8080/agent-packs/claude/download",
    },
    {
      name: "repo context analysis",
      handler: repoContextGithubRoute,
      requestUrl: "http://localhost:3000/repo-context/github",
      requestBody: { repo_url: "https://github.com/openai/openai-python" },
      expectedUrl: "http://127.0.0.1:8080/repo-context/github",
    },
    {
      name: "optimize",
      handler: optimizeRoute,
      requestUrl: "http://localhost:3000/optimize",
      requestBody: { system_prompt: "hello" },
      expectedUrl: "http://127.0.0.1:8080/optimize",
    },
    {
      name: "agent export",
      handler: agentExportRoute,
      requestUrl: "http://localhost:3000/agent-generator/export",
      requestBody: { type: "code" },
      expectedUrl: "http://127.0.0.1:8080/agent-generator/export",
    },
    {
      name: "skills export",
      handler: skillsExportRoute,
      requestUrl: "http://localhost:3000/skills-generator/export",
      requestBody: { type: "code" },
      expectedUrl: "http://127.0.0.1:8080/skills-generator/export",
    },
  ])("retries $name requests after a transient backend connection failure", async ({
    handler,
    requestUrl,
    requestMethod,
    requestBody,
    expectedUrl,
  }) => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new Error("fetch failed"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );

    const response = await handler(
      new Request(requestUrl, {
        method: requestMethod || "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: requestBody ? JSON.stringify(requestBody) : undefined,
      }),
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(expectedUrl);
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it("does not retry a benchmark run after a transient backend connection failure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("fetch failed"));

    const response = await benchmarkRunRoute(
      new Request("http://localhost:3000/benchmark/run", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ model: "gpt-4" }),
      }),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8080/benchmark/run");
    expect(response.status).toBe(502);
  });

  it.each<RouteCase>([
    {
      name: "agent generation",
      handler: agentGenerateRoute,
      requestUrl: "http://localhost:3000/agent-generator/generate",
      requestBody: { description: "review this PR" },
      expectedUrl: "http://127.0.0.1:8080/agent-generator/generate",
    },
    {
      name: "skills generation",
      handler: skillsGenerateRoute,
      requestUrl: "http://localhost:3000/skills-generator/generate",
      requestBody: { description: "search docs" },
      expectedUrl: "http://127.0.0.1:8080/skills-generator/generate",
    },
  ])("does not retry $name requests after a transient backend connection failure", async ({
    handler,
    requestUrl,
    requestBody,
    expectedUrl,
  }) => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("fetch failed"));

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
    expect(fetchMock.mock.calls[0]?.[0]).toBe(expectedUrl);
    expect(response.status).toBe(502);
  });

  it.each<RouteCase>([
    {
      name: "RAG search",
      handler: ragSearchRoute,
      requestUrl: "http://localhost:3000/rag/search",
      requestBody: { query: "test" },
      expectedUrl: "http://127.0.0.1:8080/rag/search",
    },
    {
      name: "RAG stats",
      handler: ragStatsRoute as (request: Request) => Promise<Response>,
      requestUrl: "http://localhost:3000/rag/stats",
      requestMethod: "GET",
      expectedUrl: "http://127.0.0.1:8080/rag/stats",
    },
  ])("forwards optional-auth $name requests without requiring a server API key", async ({ handler, requestUrl, requestMethod, requestBody, expectedUrl }) => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await handler(
      new Request(requestUrl, {
        method: requestMethod || "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: requestBody ? JSON.stringify(requestBody) : undefined,
      }),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, init] = fetchMock.mock.calls[0]!;
    const proxiedHeaders = new Headers(init?.headers);

    expect(url).toBe(expectedUrl);
    expect(proxiedHeaders.has("x-api-key")).toBe(false);
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it.each<RouteCase>([
    {
      name: "agent packs",
      handler: agentPacksClaudeRoute,
      requestUrl: "http://localhost:3000/agent-packs/claude",
      requestBody: AGENT_PACK_REQUEST_BODY,
      expectedUrl: "https://api.memo.dev/agent-packs/claude",
    },
    {
      name: "agent pack download",
      handler: agentPacksClaudeDownloadRoute,
      requestUrl: "http://localhost:3000/agent-packs/claude/download",
      requestBody: AGENT_PACK_REQUEST_BODY,
      expectedUrl: "https://api.memo.dev/agent-packs/claude/download",
    },
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
      name: "repo context analysis",
      handler: repoContextGithubRoute,
      requestUrl: "http://localhost:3000/repo-context/github",
      requestBody: { repo_url: "https://github.com/openai/openai-python" },
      expectedUrl: "https://api.memo.dev/repo-context/github",
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
    {
      name: "agent export",
      handler: agentExportRoute,
      requestUrl: "http://localhost:3000/agent-generator/export",
      requestBody: { type: "code" },
      expectedUrl: "https://api.memo.dev/agent-generator/export",
    },
    {
      name: "benchmark run",
      handler: benchmarkRunRoute,
      requestUrl: "http://localhost:3000/benchmark/run",
      requestBody: { model: "gpt-4" },
      expectedUrl: "https://api.memo.dev/benchmark/run",
    },
    {
      name: "optimize",
      handler: optimizeRoute,
      requestUrl: "http://localhost:3000/optimize",
      requestBody: { system_prompt: "hello" },
      expectedUrl: "https://api.memo.dev/optimize",
    },
    {
      name: "skills export",
      handler: skillsExportRoute,
      requestUrl: "http://localhost:3000/skills-generator/export",
      requestBody: { type: "code" },
      expectedUrl: "https://api.memo.dev/skills-generator/export",
    },


  ])("proxies $name requests to the backend", async ({ handler, requestUrl, requestMethod, requestBody, expectedUrl }) => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await handler(
      new Request(requestUrl, {
        method: requestMethod || "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "x-api-key": "caller-key",
        },
        body: requestBody ? JSON.stringify(requestBody) : undefined,
      }),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, init] = fetchMock.mock.calls[0]!;
    const proxiedHeaders = new Headers(init?.headers);

    expect(url).toBe(expectedUrl);
    expect(proxiedHeaders.get("x-api-key")).toBe("caller-key");
    expect(proxiedHeaders.get("content-type")).toBe("application/json");
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it("redirects GET /optimize to /optimizer without touching the POST proxy", async () => {
    const getResponse = await optimizeGetRoute(
      new Request("http://localhost:3000/optimize", { method: "GET" }),
    );

    expect(getResponse.status).toBe(307);
    expect(getResponse.headers.get("location")).toBe("http://localhost:3000/optimizer");

    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const postResponse = await optimizeRoute(
      new Request("http://localhost:3000/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ system_prompt: "hello" }),
      }),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8080/optimize");
    await expect(postResponse.json()).resolves.toEqual({ ok: true });
  });
});
