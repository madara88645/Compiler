import assert from "node:assert/strict";
import test from "node:test";

import { describeApiError } from "./config.ts";
import {
  formatSearchResultForPrompt,
  normalizeCompileResponse,
  normalizeRagSearchResults,
  normalizeRagUploadResponse,
} from "./lib/api/promptc.ts";

test("describeApiError returns auth-aware copy for 403", () => {
  assert.equal(
    describeApiError(403, { detail: "Could not validate credentials" }),
    "Could not validate credentials",
  );
});

test("normalizeRagSearchResults maps legacy source/content fields to canonical shape", () => {
  const results = normalizeRagSearchResults([
    { source: "docs/auth.md", content: "Use API keys", score: 0.75 },
  ]);

  assert.deepEqual(results, [
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

  assert.equal(response.success, true);
  assert.equal(response.num_chunks, 4);
  assert.match(response.message, /auth\.py/);
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

  assert.equal(response.processing_ms, 25);
  assert.equal(response.ir.metadata?.security?.is_safe, false);
  assert.equal(response.ir.metadata?.security?.redacted_text, "safe text");
  assert.equal(response.ir.metadata?.security?.findings[0]?.type, "api_key");
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

  assert.equal(response.ir_v2?.domain, "coding");
  assert.deepEqual(response.ir_v2?.metadata?.risk_flags, ["security"]);
});

test("formatSearchResultForPrompt includes path header", () => {
  assert.equal(
    formatSearchResultForPrompt({
      path: "docs/auth.md",
      snippet: "Use API keys",
      score: 0.4,
    }),
    "[Source: docs/auth.md]\nUse API keys",
  );
});
