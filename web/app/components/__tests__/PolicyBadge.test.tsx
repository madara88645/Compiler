import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PolicyBadge from "../PolicyBadge";
import type { CompilePolicy, CompileResponse } from "../../../lib/api/types";

function makeResult(policy: Partial<CompilePolicy> | undefined): CompileResponse {
  const base = {
    system_prompt: "",
    user_prompt: "",
    plan: "",
    expanded_prompt: "",
    processing_ms: 0,
  };
  if (!policy) {
    return { ...base, ir: { metadata: {} } } as CompileResponse;
  }
  const fullPolicy: CompilePolicy = {
    risk_level: "low",
    risk_domains: [],
    allowed_tools: [],
    forbidden_tools: [],
    sanitization_rules: [],
    data_sensitivity: "public",
    execution_mode: "auto_ok",
    ...policy,
  };
  return {
    ...base,
    ir: { metadata: {}, policy: fullPolicy },
    ir_v2: { metadata: {}, policy: fullPolicy },
  } as CompileResponse;
}

describe("PolicyBadge", () => {
  it("renders the green Auto OK badge for auto_ok mode", () => {
    render(<PolicyBadge result={makeResult({ execution_mode: "auto_ok" })} />);

    const badge = screen.getByTestId("policy-badge");
    expect(badge.textContent).toContain("Auto OK");
    expect(badge.getAttribute("data-tone")).toBe("green");
  });

  it("renders the amber Approval Required badge for human_approval_required mode", () => {
    render(
      <PolicyBadge
        result={makeResult({
          execution_mode: "human_approval_required",
          risk_level: "high",
          risk_domains: ["financial"],
        })}
      />,
    );

    const badge = screen.getByTestId("policy-badge");
    expect(badge.textContent).toContain("Approval Required");
    expect(badge.getAttribute("data-tone")).toBe("amber");
  });

  it("renders the blue Advice Only badge for advice_only mode", () => {
    render(<PolicyBadge result={makeResult({ execution_mode: "advice_only" })} />);

    const badge = screen.getByTestId("policy-badge");
    expect(badge.textContent).toContain("Advice Only");
    expect(badge.getAttribute("data-tone")).toBe("blue");
  });

  it("renders nothing when neither ir nor ir_v2 has a policy", () => {
    const { container } = render(<PolicyBadge result={makeResult(undefined)} />);
    expect(container.firstChild).toBeNull();
  });

  it("exposes risk level and top risk domain in the tooltip", () => {
    render(
      <PolicyBadge
        result={makeResult({
          execution_mode: "human_approval_required",
          risk_level: "medium",
          risk_domains: ["legal", "privacy"],
        })}
      />,
    );

    const badge = screen.getByTestId("policy-badge");
    const tooltip = badge.getAttribute("title") ?? "";
    expect(tooltip).toContain("medium");
    expect(tooltip).toContain("legal");
  });
});
