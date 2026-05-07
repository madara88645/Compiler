import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const {
  ensureHealthyBackend,
  requestCompileWithAuthRetry,
} = require("../src/workflow.js");

test("ensureHealthyBackend returns success for healthy backend responses", async () => {
  const result = await ensureHealthyBackend({
    baseUrl: "http://127.0.0.1:8080",
    timeoutMs: 3000,
    fetchHealth: async () => ({ ok: true, status: "ok" }),
  });

  assert.deepEqual(result, { ok: true, status: "ok" });
});

test("ensureHealthyBackend returns actionable connection metadata when backend is unavailable", async () => {
  const result = await ensureHealthyBackend({
    baseUrl: "http://127.0.0.1:8080",
    timeoutMs: 3000,
    fetchHealth: async () => {
      throw new Error("connect ECONNREFUSED");
    },
  });

  assert.equal(result.ok, false);
  assert.equal(result.kind, "connection");
  assert.match(result.docsUrl, /\/docs$/);
});

test("requestCompileWithAuthRetry prompts once, stores the key, and retries the request", async () => {
  const calls = [];
  let storedApiKey = null;

  const response = await requestCompileWithAuthRetry({
    initialApiKey: null,
    promptForApiKey: async () => "fresh-key",
    storeApiKey: async (value) => {
      storedApiKey = value;
    },
    compile: async ({ apiKey }) => {
      calls.push(apiKey);
      if (!apiKey) {
        const error = new Error("Unauthorized");
        error.status = 401;
        throw error;
      }
      return { ok: true };
    },
  });

  assert.deepEqual(calls, [null, "fresh-key"]);
  assert.equal(storedApiKey, "fresh-key");
  assert.deepEqual(response, { ok: true });
});
