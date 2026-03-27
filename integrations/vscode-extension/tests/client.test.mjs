import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { buildCompileRequest, normalizeCompileResponse } = require("../src/client.js");

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

test("normalizeCompileResponse lifts intent, policy, prompts, and raw JSON", () => {
  const normalized = normalizeCompileResponse({
    system_prompt_v2: "system",
    user_prompt_v2: "user",
    plan_v2: "plan",
    expanded_prompt_v2: "expanded",
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
  assert.equal(normalized.raw.ir_v2.policy.risk_level, "high");
});
