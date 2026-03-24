import test from "node:test";
import assert from "node:assert/strict";

import {
  formatPreviewDelta,
  getActivePreviewEntry,
  getRestoreText,
} from "./popup-preview.mjs";

const previewEntries = [
  {
    id: "latest",
    originalText: "Short prompt",
    optimizedText: "Expanded prompt",
    siteLabel: "ChatGPT",
    createdAt: 1700000000000,
  },
  {
    id: "older",
    originalText: "Another prompt",
    optimizedText: "Another optimized prompt",
    siteLabel: "Claude",
    createdAt: 1690000000000,
  },
];

test("getActivePreviewEntry returns the selected history item when available", () => {
  const entry = getActivePreviewEntry(previewEntries, "older");

  assert.equal(entry?.id, "older");
});

test("getActivePreviewEntry falls back to the latest item when selection is missing", () => {
  const entry = getActivePreviewEntry(previewEntries, "missing");

  assert.equal(entry?.id, "latest");
});

test("getRestoreText returns the optimized text for the selected preview", () => {
  const text = getRestoreText(previewEntries[1]);

  assert.equal(text, "Another optimized prompt");
});

test("formatPreviewDelta reports positive and negative char deltas", () => {
  assert.equal(formatPreviewDelta(previewEntries[0]), "+3 chars");
  assert.equal(
    formatPreviewDelta({
      originalText: "Longer original prompt",
      optimizedText: "Short",
    }),
    "-17 chars",
  );
});
