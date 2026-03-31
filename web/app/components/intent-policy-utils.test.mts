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

test("normalizeIntentPolicy returns ordered intent details with human-friendly labels", async () => {
  const { humanizeIntentPolicyValue, normalizeIntentPolicy } = await import("./intent-policy-utils.ts");

  const result = normalizeIntentPolicy({
    ir_v2: {
      intents: ["risk", "review", "teaching", "debug"],
      policy: {
        allowed_tools: ["workspace_read", "run_tests"],
        forbidden_tools: ["write_outside_workspace"],
        sanitization_rules: ["mask_sensitive_values"],
        execution_mode: "human_approval_required",
      },
    },
  });

  assert.deepEqual(
    result.intentDetails.map((item) => item.key),
    ["teaching", "review", "debug", "risk"],
  );
  assert.equal(result.intentDetails[0]?.label, "Teaching");
  assert.equal(result.intentDetails[1]?.description.includes("review"), true);
  assert.equal(humanizeIntentPolicyValue(result.allowedTools[0]), "Workspace Read");
  assert.equal(humanizeIntentPolicyValue(result.allowedTools[1]), "Run Tests");
  assert.equal(humanizeIntentPolicyValue(result.forbiddenTools[0]), "Write Outside Workspace");
  assert.equal(humanizeIntentPolicyValue(result.sanitizationRules[0]), "Mask Sensitive Values");
  assert.equal(humanizeIntentPolicyValue(result.executionMode), "Human Approval Required");
});

test("normalizeIntentPolicy humanizes unknown intents without breaking", async () => {
  const { normalizeIntentPolicy } = await import("./intent-policy-utils.ts");

  const result = normalizeIntentPolicy({
    ir_v2: {
      intents: ["future_magic", "compare"],
    },
  });

  assert.deepEqual(
    result.intentDetails.map((item) => ({ key: item.key, label: item.label })),
    [
      { key: "compare", label: "Comparison" },
      { key: "future_magic", label: "Future Magic" },
    ],
  );
});
