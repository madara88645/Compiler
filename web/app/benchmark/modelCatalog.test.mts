import test from "node:test";
import assert from "node:assert/strict";

import {
  BENCHMARK_MODEL_GROUPS,
  BENCHMARK_MODELS,
  getBenchmarkModelById,
} from "./modelCatalog.ts";

test("benchmark catalog is OpenRouter-only and keeps GPT-OSS 20B as the default cheap option", () => {
  const ids = BENCHMARK_MODELS.map((model) => model.id);

  assert.equal(ids.includes("openai/gpt-oss-20b"), true);
  assert.equal(ids.includes("openai/gpt-oss-120b"), true);
  assert.equal(ids.includes("mistralai/mistral-small-3.2-24b-instruct"), true);
  assert.equal(ids.includes("llama-3.1-8b-instant"), false);
  assert.equal(ids[0], "openai/gpt-oss-20b");
});

test("benchmark catalog keeps preview coverage for qwen", () => {
  assert.equal(getBenchmarkModelById("qwen/qwen3-32b")?.availability, "preview");
});

test("benchmark groups keep cheap and balanced models visible", () => {
  const labels = BENCHMARK_MODEL_GROUPS.map((group) => group.label);

  assert.equal(labels.includes("Cheap"), true);
  assert.equal(labels.includes("Balanced"), true);
});
