import test from "node:test";
import assert from "node:assert/strict";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalApiKey = process.env.NEXT_PUBLIC_API_KEY;

test("buildApiHeaders does not inject x-api-key from NEXT_PUBLIC_API_KEY", async () => {
  process.env.NEXT_PUBLIC_API_KEY = "test-key";

  const { buildApiHeaders } = await import("./config.ts");
  const headers = buildApiHeaders({ "Content-Type": "application/json" });
  const normalizedHeaders = new Headers(headers);

  assert.equal(normalizedHeaders.get("content-type"), "application/json");
  assert.equal(normalizedHeaders.has("x-api-key"), false);
});

test("buildApiHeaders leaves headers unchanged when NEXT_PUBLIC_API_KEY is empty", async () => {
  delete process.env.NEXT_PUBLIC_API_KEY;

  const { buildApiHeaders } = await import("./config.ts");
  const headers = buildApiHeaders({ Accept: "application/json" });
  const normalizedHeaders = new Headers(headers);

  assert.equal(normalizedHeaders.get("accept"), "application/json");
  assert.equal(normalizedHeaders.has("x-api-key"), false);
});

test("buildGeneratorApiHeaders does not inject x-api-key from NEXT_PUBLIC_API_KEY", async () => {
  process.env.NEXT_PUBLIC_API_KEY = "test-key";

  const { buildGeneratorApiHeaders } = await import("./config.ts");
  const headers = buildGeneratorApiHeaders({ "Content-Type": "application/json" });
  const normalizedHeaders = new Headers(headers);

  assert.equal(normalizedHeaders.get("content-type"), "application/json");
  assert.equal(normalizedHeaders.has("x-api-key"), false);
});

test("buildGeneratorApiHeaders leaves x-api-key unset when NEXT_PUBLIC_API_KEY is empty", async () => {
  delete process.env.NEXT_PUBLIC_API_KEY;

  const { buildGeneratorApiHeaders } = await import("./config.ts");
  const headers = buildGeneratorApiHeaders({ Accept: "application/json" });
  const normalizedHeaders = new Headers(headers);

  assert.equal(normalizedHeaders.get("accept"), "application/json");
  assert.equal(normalizedHeaders.has("x-api-key"), false);
});

test("resolveApiBase prefers same-origin in non-local browser environments when env is unset", async () => {
  delete process.env.NEXT_PUBLIC_API_URL;

  const { resolveApiBase } = await import("./config.ts");
  const apiBase = resolveApiBase({
    hostname: "compiler.memo.dev",
    origin: "https://compiler.memo.dev",
  });

  assert.equal(apiBase, "https://compiler.memo.dev");
});

test("resolveApiBase ignores NEXT_PUBLIC_API_URL for browser requests and keeps same-origin", async () => {
  process.env.NEXT_PUBLIC_API_URL = "https://api.memo.dev";

  const { resolveApiBase } = await import("./config.ts");
  const apiBase = resolveApiBase({
    hostname: "compiler.memo.dev",
    origin: "https://compiler.memo.dev",
  });

  assert.equal(apiBase, "https://compiler.memo.dev");
});

test("resolveApiBase keeps localhost same-origin for browser development", async () => {
  delete process.env.NEXT_PUBLIC_API_URL;

  const { resolveApiBase } = await import("./config.ts");
  const apiBase = resolveApiBase({
    hostname: "localhost",
    origin: "http://localhost:3000",
  });

  assert.equal(apiBase, "http://localhost:3000");
});

test("describeRequestError rewrites raw browser fetch failures into helpful copy", async () => {
  const { describeRequestError } = await import("./config.ts");

  assert.equal(
    describeRequestError(new Error("Failed to fetch")),
    "Could not reach the backend. Check the API URL or make sure the server is running.",
  );
});

test.after(() => {
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
