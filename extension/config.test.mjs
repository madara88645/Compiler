import test from "node:test";
import assert from "node:assert/strict";

import { resolveRuntimeConfig } from "./config.mjs";

test("resolveRuntimeConfig reports missing credentials without embedded defaults", () => {
  const result = resolveRuntimeConfig({});

  assert.equal(result.ok, false);
  assert.equal(result.error, "Extension is not configured yet. Add your backend URL in the popup.");
});

test("resolveRuntimeConfig normalizes backend URLs without requiring an API key", () => {
  const result = resolveRuntimeConfig({
    backendUrl: "compiler-production-626b.up.railway.app/",
  });

  assert.equal(result.ok, true);
  assert.equal(result.value?.backendUrl, "https://compiler-production-626b.up.railway.app");
  assert.equal(result.value?.apiKey, "");
});

test("resolveRuntimeConfig passes through trimmed API key when set", () => {
  const result = resolveRuntimeConfig({
    backendUrl: "https://example.com",
    apiKey: "  secret  ",
  });

  assert.equal(result.ok, true);
  assert.equal(result.value?.apiKey, "secret");
});
