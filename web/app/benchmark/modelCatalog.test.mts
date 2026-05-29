import test from "node:test";
import assert from "node:assert/strict";

import {
  BENCHMARK_MODEL_GROUPS,
  BENCHMARK_MODELS,
  getBenchmarkModelById,
} from "./modelCatalog.ts";

test("benchmark catalog removes deprecated Maverick and includes production + preview targets", () => {
  const ids = BENCHMARK_MODELS.map((model) => model.id);

  assert.equal(ids.includes("meta-llama/llama-4-maverick-17b-128e-instruct"), false);
  assert.equal(ids.includes("qwen/qwen3-32b"), true);
  assert.equal(ids.includes("meta-llama/llama-4-scout-17b-16e-instruct"), true);
});

test("benchmark catalog exposes preview badges for scout and qwen", () => {
  assert.equal(getBenchmarkModelById("meta-llama/llama-4-scout-17b-16e-instruct")?.availability, "preview");
  assert.equal(getBenchmarkModelById("qwen/qwen3-32b")?.availability, "preview");
});

test("benchmark groups keep cheap and balanced models visible", () => {
  const labels = BENCHMARK_MODEL_GROUPS.map((group) => group.label);

  assert.equal(labels.includes("Cheap"), true);
  assert.equal(labels.includes("Balanced"), true);
});

test("getBenchmarkModelById returns the correct model for a valid ID", () => {
  const model = getBenchmarkModelById("llama-3.1-8b-instant");
  assert.notEqual(model, undefined);
  assert.equal(model?.id, "llama-3.1-8b-instant");
  assert.equal(model?.label, "Llama 3.1 8B Instant");
});

test("getBenchmarkModelById returns undefined for an invalid ID", () => {
  const model = getBenchmarkModelById("non-existent-model");
  assert.equal(model, undefined);
});
