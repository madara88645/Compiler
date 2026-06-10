import { expect, test } from "vitest";

import { describeApiError } from "./config.ts";
import {
  formatSearchResultForPrompt,
  normalizeCompileResponse,
  normalizeRagSearchResults,
  normalizeRagUploadResponse,
} from "./lib/api/promptc.ts";

test("describeApiError returns auth-aware copy for 403", () => {
  expect(describeApiError(403, { detail: "Could not validate credentials" })).toBe(
    "Could not validate credentials",
  );
});

test("normalizeRagSearchResults maps legacy source/content fields to canonical shape", () => {
  const results = normalizeRagSearchResults([
    { source: "docs/auth.md", content: "Use API keys", score: 0.75 },
  ]);

  expect(results).toEqual([
    {
      path: "docs/auth.md",
      snippet: "Use API keys",
      score: 0.75,
    },
  ]);
});

test("normalizeRagUploadResponse derives compatibility fields from canonical payload", () => {
  const response = normalizeRagUploadResponse({
    ingested_docs: 1,
    total_chunks: 4,
    elapsed_ms: 12,
    filename: "auth.py",
  });

  expect(response.success).toBe(true);
  expect(response.num_chunks).toBe(4);
  expect(response.message).toMatch(/auth\.py/);
});

test("normalizeCompileResponse preserves nested security metadata", () => {
  const response = normalizeCompileResponse({
    system_prompt: "sys",
    user_prompt: "usr",
    plan: "1. step",
    expanded_prompt: "expanded",
    ir: {
      metadata: {
        security: {
          is_safe: false,
          redacted_text: "safe text",
          findings: [{ type: "api_key", original: "secret", masked: "***" }],
        },
      },
    },
    processing_ms: 25,
  });

  expect(response.processing_ms).toBe(25);
  expect(response.ir.metadata?.security?.is_safe).toBe(false);
  expect(response.ir.metadata?.security?.redacted_text).toBe("safe text");
  expect(response.ir.metadata?.security?.findings[0]?.type).toBe("api_key");
});

test("normalizeCompileResponse rejects empty compile payloads", () => {
  expect(() => normalizeCompileResponse(null)).toThrow(/Invalid compile response/);
  expect(() => normalizeCompileResponse({})).toThrow(/Invalid compile response: missing compiler output/);
});

test("normalizeCompileResponse defaults missing policy fields", () => {
  const response = normalizeCompileResponse({
    system_prompt: "sys",
    user_prompt: "usr",
    plan: "1. step",
    expanded_prompt: "expanded",
    ir: {
      domain: "general",
    },
    ir_v2: {
      domain: "coding",
    },
    processing_ms: 25,
  });

  expect(response.ir.policy?.risk_level).toBe("low");
  expect(response.ir.policy?.allowed_tools).toEqual([]);
  expect(response.ir_v2?.policy?.execution_mode).toBe("advice_only");
});

test("normalizeCompileResponse falls back to ir when ir_v2 is missing", () => {
  const response = normalizeCompileResponse({
    system_prompt: "sys",
    user_prompt: "usr",
    plan: "1. step",
    expanded_prompt: "expanded",
    ir: {
      domain: "security",
      policy: {
        risk_level: "high",
      },
    },
    processing_ms: 25,
  });

  expect(response.ir_v2?.domain).toBe("security");
  expect(response.ir_v2?.policy?.risk_level).toBe("high");
  expect(response.ir_v2?.policy?.data_sensitivity).toBe("public");
});

test("normalizeCompileResponse preserves optional ir_v2 payload", () => {
  const response = normalizeCompileResponse({
    system_prompt: "sys",
    user_prompt: "usr",
    plan: "1. step",
    expanded_prompt: "expanded",
    ir: {},
    ir_v2: {
      domain: "coding",
      metadata: {
        risk_flags: ["security"],
      },
    },
    processing_ms: 25,
  });

  expect(response.ir_v2?.domain).toBe("coding");
  expect(response.ir_v2?.metadata?.risk_flags).toEqual(["security"]);
  expect(response.ir_v2?.policy?.risk_level).toBe("low");
});

test("normalizeCompileResponse preserves backend compile metadata fields", () => {
  const response = normalizeCompileResponse({
    system_prompt: "sys",
    user_prompt: "usr",
    plan: "1. step",
    expanded_prompt: "expanded",
    ir: {
      domain: "general",
    },
    processing_ms: 25,
    request_id: "abc123",
    heuristic_version: "v1",
    heuristic2_version: "v2",
    trace: ["step 1", "step 2"],
  });

  expect(response.request_id).toBe("abc123");
  expect(response.heuristic_version).toBe("v1");
  expect(response.heuristic2_version).toBe("v2");
  expect(response.trace).toEqual(["step 1", "step 2"]);
});

test("formatSearchResultForPrompt includes path header", () => {
  expect(
    formatSearchResultForPrompt({
      path: "docs/auth.md",
      snippet: "Use API keys",
      score: 0.4,
    }),
  ).toBe("[Source: docs/auth.md]\nUse API keys");
});

test("formatSearchResultForPrompt strips search-highlight brackets from the snippet", () => {
  expect(
    formatSearchResultForPrompt({
      path: "docs/launch.md",
      snippet: "The [launch] [date] is confirmed …",
      score: 0.7,
    }),
  ).toBe("[Source: docs/launch.md]\nThe launch date is confirmed …");
});

test("formatSearchResultForPrompt keeps the source header when stripping highlights", () => {
  expect(
    formatSearchResultForPrompt({
      path: "",
      snippet: "[empty] highlights only",
      score: 0.1,
    }),
  ).toBe("[Source: unknown]\nempty highlights only");
});
