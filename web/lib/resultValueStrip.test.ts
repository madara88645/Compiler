import { describe, expect, it } from "vitest";
import { getResultValuePills } from "./resultValueStrip";
import type { CompileResponse } from "./api/types";

function makeResult(overrides: Partial<CompileResponse> = {}): CompileResponse {
  return {
    ir: {},
    system_prompt: "system",
    user_prompt: "user",
    plan: "1. Analyze request\n   Rationale: establish understanding\n2. Draft the change\n   Rationale: implement\n3. Verify\n   Rationale: check output",
    expanded_prompt: "expanded",
    processing_ms: 1,
    readiness_markdown: "",
    ...overrides,
  };
}

describe("getResultValuePills", () => {
  it("returns all five pills when every field is present", () => {
    const result = makeResult({
      readiness: {
        verdict: "clarify",
        signals: [],
        questions: ["What language?", "Which repo?"],
      },
      ir: {
        policy: {
          risk_level: "high",
          risk_domains: [],
          allowed_tools: [],
          forbidden_tools: [],
          sanitization_rules: [],
          data_sensitivity: "public",
          execution_mode: "human_approval_required",
        },
      },
      critique: {
        verdict: "ACCEPT",
        score: 87,
        issues: [],
        feedback: "Looks solid.",
      },
    });

    const pills = getResultValuePills(result);
    const keys = pills.map((p) => p.key);

    expect(keys).toEqual(["readiness", "clarify", "plan", "risk", "critique"]);

    expect(pills.find((p) => p.key === "readiness")).toMatchObject({ label: "Clarify", tone: "amber" });
    expect(pills.find((p) => p.key === "clarify")).toMatchObject({ label: "2 to clarify", tone: "amber" });
    expect(pills.find((p) => p.key === "plan")).toMatchObject({ label: "3 plan steps", tone: "blue" });
    expect(pills.find((p) => p.key === "risk")).toMatchObject({ label: "High risk", tone: "red" });
    expect(pills.find((p) => p.key === "critique")).toMatchObject({ label: "Critique 87/100", tone: "green" });
  });

  it("omits the critique pill when critique is absent", () => {
    const result = makeResult({
      readiness: { verdict: "ready", signals: [], questions: [] },
      critique: null,
    });

    const pills = getResultValuePills(result);

    expect(pills.some((p) => p.key === "critique")).toBe(false);
  });

  it("still renders a clarify pill with a positive message for zero clarify questions", () => {
    const result = makeResult({
      readiness: { verdict: "ready", signals: [], questions: [] },
    });

    const pills = getResultValuePills(result);
    const clarifyPill = pills.find((p) => p.key === "clarify");

    expect(clarifyPill).toMatchObject({ label: "No open questions", tone: "green" });
  });

  it("omits the readiness and clarify pills when readiness is absent, and the risk pill when policy is absent", () => {
    const result = makeResult({ readiness: null, ir: {} });

    const pills = getResultValuePills(result);
    const keys = pills.map((p) => p.key);

    expect(keys).not.toContain("readiness");
    expect(keys).not.toContain("clarify");
    expect(keys).not.toContain("risk");
    expect(keys).toContain("plan");
  });
});
