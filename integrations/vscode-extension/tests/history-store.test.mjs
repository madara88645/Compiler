import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const {
  createHistoryEntry,
  pushHistoryEntry,
  sanitizeStoredEntries,
} = require("../src/history-store.js");

test("createHistoryEntry keeps compile metadata and artifact previews", () => {
  const entry = createHistoryEntry({
    sourceText: "summarize this spec",
    scope: "selection",
    normalized: {
      intent: { domain: "product", persona: "assistant", intents: ["summary"] },
      policy: { riskLevel: "low" },
      prompts: {
        system: "system text",
        user: "user text",
        plan: "plan text",
        expanded: "expanded text",
      },
      summary: { requestId: "req_1", processingMs: 33 },
    },
  });

  assert.equal(entry.scope, "selection");
  assert.equal(entry.summary.requestId, "req_1");
  assert.equal(entry.artifacts.system, "system text");
  assert.match(entry.preview, /summarize this spec/);
});

test("pushHistoryEntry keeps newest-first ordering and trims to max size", () => {
  const base = [
    { id: "older-1", savedAt: "2026-05-07T10:00:00.000Z" },
    { id: "older-2", savedAt: "2026-05-07T09:00:00.000Z" },
  ];

  const next = pushHistoryEntry(base, { id: "newest", savedAt: "2026-05-07T11:00:00.000Z" }, 2);

  assert.deepEqual(
    next.map((item) => item.id),
    ["newest", "older-1"]
  );
});

test("sanitizeStoredEntries drops malformed persisted records", () => {
  const entries = sanitizeStoredEntries([
    null,
    { id: "", summary: {} },
    {
      id: "valid",
      sourceText: "hello",
      scope: "file",
      savedAt: "2026-05-07T11:00:00.000Z",
      preview: "hello",
      summary: { requestId: "req_1", processingMs: 12, riskLevel: "low", domain: "general" },
      artifacts: { system: "s", user: "u", plan: "p", expanded: "e" },
    },
  ]);

  assert.equal(entries.length, 1);
  assert.equal(entries[0].id, "valid");
});
