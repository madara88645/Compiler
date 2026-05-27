import { afterAll, expect, test } from "vitest";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalApiKey = process.env.NEXT_PUBLIC_API_KEY;

test("buildApiHeaders does not inject x-api-key from NEXT_PUBLIC_API_KEY", async () => {
  process.env.NEXT_PUBLIC_API_KEY = "test-key";

  const { buildApiHeaders } = await import("./config.ts");
  const headers = buildApiHeaders({ "Content-Type": "application/json" });
  const normalizedHeaders = new Headers(headers);

  expect(normalizedHeaders.get("content-type")).toBe("application/json");
  expect(normalizedHeaders.has("x-api-key")).toBe(false);
});

test("buildApiHeaders leaves headers unchanged when NEXT_PUBLIC_API_KEY is empty", async () => {
  delete process.env.NEXT_PUBLIC_API_KEY;

  const { buildApiHeaders } = await import("./config.ts");
  const headers = buildApiHeaders({ Accept: "application/json" });
  const normalizedHeaders = new Headers(headers);

  expect(normalizedHeaders.get("accept")).toBe("application/json");
  expect(normalizedHeaders.has("x-api-key")).toBe(false);
});

test("buildGeneratorApiHeaders does not inject x-api-key from NEXT_PUBLIC_API_KEY", async () => {
  process.env.NEXT_PUBLIC_API_KEY = "test-key";

  const { buildGeneratorApiHeaders } = await import("./config.ts");
  const headers = buildGeneratorApiHeaders({ "Content-Type": "application/json" });
  const normalizedHeaders = new Headers(headers);

  expect(normalizedHeaders.get("content-type")).toBe("application/json");
  expect(normalizedHeaders.has("x-api-key")).toBe(false);
});

test("buildGeneratorApiHeaders leaves x-api-key unset when NEXT_PUBLIC_API_KEY is empty", async () => {
  delete process.env.NEXT_PUBLIC_API_KEY;

  const { buildGeneratorApiHeaders } = await import("./config.ts");
  const headers = buildGeneratorApiHeaders({ Accept: "application/json" });
  const normalizedHeaders = new Headers(headers);

  expect(normalizedHeaders.get("accept")).toBe("application/json");
  expect(normalizedHeaders.has("x-api-key")).toBe(false);
});

test("resolveApiBase prefers same-origin in non-local browser environments when env is unset", async () => {
  delete process.env.NEXT_PUBLIC_API_URL;

  const { resolveApiBase } = await import("./config.ts");
  const apiBase = resolveApiBase({
    hostname: "compiler.memo.dev",
    origin: "https://compiler.memo.dev",
  });

  expect(apiBase).toBe("https://compiler.memo.dev");
});

test("resolveApiBase ignores NEXT_PUBLIC_API_URL for browser requests and keeps same-origin", async () => {
  process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

  const { resolveApiBase } = await import("./config.ts");
  const apiBase = resolveApiBase({
    hostname: "compiler.memo.dev",
    origin: "https://compiler.memo.dev",
  });

  expect(apiBase).toBe("https://compiler.memo.dev");
});

test("resolveApiBase keeps localhost same-origin for browser development", async () => {
  delete process.env.NEXT_PUBLIC_API_URL;

  const { resolveApiBase } = await import("./config.ts");
  const apiBase = resolveApiBase({
    hostname: "localhost",
    origin: "http://localhost:3000",
  });

  expect(apiBase).toBe("http://localhost:3000");
});

test("describeRequestError rewrites raw browser fetch failures into helpful copy", async () => {
  const { describeRequestError } = await import("./config.ts");

  expect(describeRequestError(new Error("Failed to fetch"))).toBe(
    "The service is temporarily unavailable or still waking up. Please retry in a few seconds.",
  );
});

afterAll(() => {
  if (originalApiUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_URL;
  } else {
    process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
  }

  if (originalApiKey === undefined) {
    delete process.env.NEXT_PUBLIC_API_KEY;
  } else {
    process.env.NEXT_PUBLIC_API_KEY = originalApiKey;
  }
});
