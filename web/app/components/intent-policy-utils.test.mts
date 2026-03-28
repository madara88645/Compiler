import test from "node:test";
import assert from "node:assert/strict";

test("normalizeIntentPolicy prefers ir_v2 policy fields", async () => {
  const { normalizeIntentPolicy } = await import("./intent-policy-utils.ts");

  const result = normalizeIntentPolicy({
    ir: { domain: "general", persona: "assistant", intents: [] },
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

  assert.equal(result.domain, "finance");
  assert.equal(result.persona, "researcher");
  assert.equal(result.riskLevel, "high");
  assert.equal(result.executionMode, "human_approval_required");
  assert.deepEqual(result.allowedTools, ["workspace_read"]);
});

test("normalizeIntentPolicy falls back to legacy ir metadata when ir_v2 is absent", async () => {
  const { normalizeIntentPolicy } = await import("./intent-policy-utils.ts");

  const result = normalizeIntentPolicy({
    ir: {
      domain: "security",
      persona: "assistant",
      intents: ["risk"],
      metadata: {
        risk_flags: ["security"],
      },
    },
  });

  assert.equal(result.domain, "security");
  assert.equal(result.persona, "assistant");
  assert.equal(result.riskLevel, "medium");
  assert.equal(result.executionMode, "advice_only");
  assert.deepEqual(result.riskDomains, ["security"]);
});
