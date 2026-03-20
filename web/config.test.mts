import test from "node:test";
import assert from "node:assert/strict";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalApiKey = process.env.NEXT_PUBLIC_API_KEY;

test("buildApiHeaders adds x-api-key when NEXT_PUBLIC_API_KEY is set", async () => {
  process.env.NEXT_PUBLIC_API_KEY = "test-key";

  const { buildApiHeaders } = await import("./config.ts");
  const headers = buildApiHeaders({ "Content-Type": "application/json" });
  const normalizedHeaders = new Headers(headers);

  assert.equal(normalizedHeaders.get("content-type"), "application/json");
  assert.equal(normalizedHeaders.get("x-api-key"), "test-key");
});

test("buildApiHeaders leaves headers unchanged when NEXT_PUBLIC_API_KEY is empty", async () => {
  delete process.env.NEXT_PUBLIC_API_KEY;

  const { buildApiHeaders } = await import("./config.ts");
  const headers = buildApiHeaders({ Accept: "application/json" });
  const normalizedHeaders = new Headers(headers);

  assert.equal(normalizedHeaders.get("accept"), "application/json");
  assert.equal(normalizedHeaders.has("x-api-key"), false);
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
