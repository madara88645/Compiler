import { describe, expect, it } from "vitest";
import { getCompileTabContent } from "./compileTabContent";
import type { CompileResponse } from "./api/types";

function makeResult(overrides: Partial<CompileResponse> = {}): CompileResponse {
  return {
    ir: {},
    system_prompt: "v1-system",
    user_prompt: "v1-user",
    plan: "v1-plan",
    expanded_prompt: "v1-expanded",
    system_prompt_v2: "v2-system",
    user_prompt_v2: "v2-user",
    plan_v2: "v2-plan",
    expanded_prompt_v2: "v2-expanded",
    processing_ms: 1,
    request_id: "req_test",
    heuristic_version: "v1",
    ...overrides,
  };
}

describe("getCompileTabContent", () => {
  it("prefers v2 fields for each tab", () => {
    const result = makeResult();
    expect(getCompileTabContent(result, "system")).toBe("v2-system");
    expect(getCompileTabContent(result, "user")).toBe("v2-user");
    expect(getCompileTabContent(result, "plan")).toBe("v2-plan");
    expect(getCompileTabContent(result, "expanded")).toBe("v2-expanded");
  });

  it("falls back to v1 when v2 is missing", () => {
    const result = makeResult({
      system_prompt_v2: null,
      user_prompt_v2: undefined,
      plan_v2: "",
      expanded_prompt_v2: null,
    });
    expect(getCompileTabContent(result, "system")).toBe("v1-system");
    expect(getCompileTabContent(result, "user")).toBe("v1-user");
    expect(getCompileTabContent(result, "plan")).toBe("v1-plan");
    expect(getCompileTabContent(result, "expanded")).toBe("v1-expanded");
  });
});
