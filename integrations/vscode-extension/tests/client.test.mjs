import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const {
  buildCompileRequest,
  buildHeaders,
  fetchCompileResult,
  fetchHealth,
  normalizeCompileResponse,
} = require("../src/client.js");

test("buildCompileRequest creates a conservative compile payload", () => {
  const payload = buildCompileRequest("Turn this issue into a plan", true);

  assert.deepEqual(payload, {
    text: "Turn this issue into a plan",
    diagnostics: true,
    v2: true,
    render_v2_prompts: true,
    mode: "conservative",
  });
});

test("buildHeaders adds the API key only when present", () => {
  assert.deepEqual(buildHeaders(), { "Content-Type": "application/json" });
  assert.deepEqual(buildHeaders("secret"), {
    "Content-Type": "application/json",
    "x-api-key": "secret",
  });
});

test("fetchCompileResult calls /compile with timeout-aware request options", async () => {
  let receivedUrl = "";
  let receivedInit = null;

  const payload = await fetchCompileResult({
    baseUrl: "http://127.0.0.1:8080/",
    text: "hello",
    conservativeMode: false,
    timeoutMs: 3210,
    apiKey: "secret",
    fetchImpl: async (url, init) => {
      receivedUrl = url;
      receivedInit = init;
      return {
        ok: true,
        json: async () => ({ ok: true }),
      };
    },
  });

  assert.equal(receivedUrl, "http://127.0.0.1:8080/compile");
  assert.equal(receivedInit.method, "POST");
  assert.equal(receivedInit.headers["x-api-key"], "secret");
  assert.equal(typeof receivedInit.signal?.aborted, "boolean");
  assert.equal(payload.ok, true);
});

test("fetchCompileResult includes response details in thrown errors", async () => {
  await assert.rejects(
    () =>
      fetchCompileResult({
        baseUrl: "http://127.0.0.1:8080",
        text: "hello",
        conservativeMode: true,
        fetchImpl: async () => ({
          ok: false,
          status: 503,
          headers: new Map([["content-type", "application/json"]]),
          json: async () => ({ detail: "worker unavailable" }),
          text: async () => "worker unavailable",
        }),
      }),
    (error) => {
      assert.equal(error.status, 503);
      assert.match(error.message, /worker unavailable/);
      return true;
    }
  );
});

test("fetchHealth hits the health endpoint and returns parsed payload", async () => {
  let receivedUrl = "";

  const payload = await fetchHealth({
    baseUrl: "http://127.0.0.1:8080/",
    timeoutMs: 1500,
    fetchImpl: async (url) => {
      receivedUrl = url;
      return {
        ok: true,
        json: async () => ({ status: "ok" }),
      };
    },
  });

  assert.equal(receivedUrl, "http://127.0.0.1:8080/health");
  assert.deepEqual(payload, { ok: true, status: "ok" });
});

test("normalizeCompileResponse lifts intent, policy, prompts, summary, and raw JSON", () => {
  const normalized = normalizeCompileResponse({
    system_prompt_v2: "system",
    user_prompt_v2: "user",
    plan_v2: "plan",
    expanded_prompt_v2: "expanded",
    request_id: "req_123",
    processing_ms: 42,
    ir_v2: {
      domain: "finance",
      persona: "researcher",
      intents: ["risk"],
      policy: {
        risk_level: "high",
        risk_domains: ["financial"],
        allowed_tools: ["workspace_read"],
        forbidden_tools: ["secret_access"],
        sanitization_rules: ["mask_sensitive_values"],
        data_sensitivity: "confidential",
        execution_mode: "human_approval_required",
      },
    },
  });

  assert.equal(normalized.intent.domain, "finance");
  assert.equal(normalized.policy.executionMode, "human_approval_required");
  assert.equal(normalized.prompts.system, "system");
  assert.equal(normalized.summary.requestId, "req_123");
  assert.equal(normalized.summary.processingMs, 42);
  assert.equal(normalized.raw.ir_v2.policy.risk_level, "high");
});
