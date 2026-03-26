import test from "node:test";
import assert from "node:assert/strict";

import {
  PREVIEW_HISTORY_LIMIT,
  buildPreviewEntry,
  mergePreviewHistory,
  resolveSiteLabel,
} from "./preview-history.mjs";

test("resolveSiteLabel maps supported chat domains to friendly names", () => {
  assert.equal(resolveSiteLabel("https://chatgpt.com/c/123"), "ChatGPT");
  assert.equal(resolveSiteLabel("https://claude.ai/new"), "Claude");
  assert.equal(resolveSiteLabel("https://gemini.google.com/app"), "Gemini");
});

test("buildPreviewEntry keeps original and optimized text plus source metadata", () => {
  const entry = buildPreviewEntry({
    originalText: "Original prompt",
    optimizedText: "Optimized prompt",
    sourceUrl: "https://claude.ai/new",
    now: 1700000000000,
  });

  assert.equal(entry.originalText, "Original prompt");
  assert.equal(entry.optimizedText, "Optimized prompt");
  assert.equal(entry.siteLabel, "Claude");
  assert.equal(entry.createdAt, 1700000000000);
});

test("mergePreviewHistory prepends newest entry and keeps only recent items", () => {
  const history = Array.from({ length: PREVIEW_HISTORY_LIMIT }, (_, index) =>
    buildPreviewEntry({
      originalText: `Original ${index}`,
      optimizedText: `Optimized ${index}`,
      sourceUrl: "https://chatgpt.com",
      now: 1700000000000 + index,
    }),
  );

  const latest = buildPreviewEntry({
    originalText: "Newest original",
    optimizedText: "Newest optimized",
    sourceUrl: "https://gemini.google.com",
    now: 1800000000000,
  });

  const merged = mergePreviewHistory(history, latest);

  assert.equal(merged.length, PREVIEW_HISTORY_LIMIT);
  assert.equal(merged[0].optimizedText, "Newest optimized");
  assert.equal(merged.at(-1)?.optimizedText, "Optimized 1");
});
