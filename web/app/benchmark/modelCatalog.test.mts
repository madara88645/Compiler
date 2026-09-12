import test from "node:test";
import assert from "node:assert/strict";

import {
  BENCHMARK_MODEL_GROUPS,
  BENCHMARK_MODELS,
  getBenchmarkModelById,
} from "./modelCatalog.ts";

test("benchmark catalog leads with reviewed current models and keeps GPT-OSS compatibility", () => {
  const ids = BENCHMARK_MODELS.map((model) => model.id);

  assert.equal(ids.includes("openai/gpt-oss-20b"), true);
  assert.equal(ids.includes("openai/gpt-oss-120b"), true);
  assert.equal(ids.includes("mistralai/mistral-small-3.2-24b-instruct"), true);
  assert.equal(ids.includes("llama-3.1-8b-instant"), false);
  assert.deepEqual(ids.slice(0, 3), [
    "deepseek/deepseek-v4.1-flash",
    "openai/gpt-5.6-luna",
    "google/gemini-3.6-flash",
  ]);
  assert.equal(getBenchmarkModelById("openai/gpt-oss-20b")?.group, "Cheap");
});

test("benchmark catalog keeps preview coverage for qwen", () => {
  assert.equal(getBenchmarkModelById("qwen/qwen3-32b")?.availability, "preview");
});

test("benchmark groups keep cheap and balanced models visible", () => {
  const labels = BENCHMARK_MODEL_GROUPS.map((group) => group.label);

  assert.equal(labels.includes("Cheap"), true);
  assert.equal(labels.includes("Balanced"), true);
});
