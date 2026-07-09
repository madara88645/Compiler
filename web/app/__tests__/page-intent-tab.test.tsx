import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";
import type { CompileResponse } from "../../lib/api/types";

const useCompilerMock = vi.fn();
const useContextManagerMock = vi.fn();

vi.mock("../hooks/useCompiler", () => ({
  useCompiler: () => useCompilerMock(),
}));

vi.mock("../hooks/useContextManager", () => ({
  useContextManager: () => useContextManagerMock(),
}));

vi.mock("../components/ContextManager", () => ({
  default: () => <div data-testid="context-manager" />,
}));

vi.mock("../components/OutputSkeleton", () => ({
  default: () => <div data-testid="output-skeleton" />,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

function makeMinimalResult(): CompileResponse {
  return {
    ir: {},
    system_prompt: "system content",
    user_prompt: "user content",
    plan: "plan content",
    expanded_prompt: "expanded content",
    processing_ms: 1,
    request_id: "req_test",
    heuristic_version: "v1",
  } as CompileResponse;
}

function makeIntentRichResult(): CompileResponse {
  return {
    ...makeMinimalResult(),
    ir_v2: {
      domain: "finance",
      persona: "researcher",
      intents: ["teaching", "risk"],
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
  } as CompileResponse;
}

describe("Intent tab / IntentPolicyPanel", () => {
  beforeEach(() => {
    localStorage.clear();
    useCompilerMock.mockReturnValue({
      loading: false,
      result: null,
      status: "Ready",
      lastError: null,
      securityFindings: [],
      redactedText: "",
      runCompile: vi.fn(),
      retry: vi.fn(),
      resolveSecurityDecision: vi.fn(),
      cancelSecurityReview: vi.fn(),
    });
    useContextManagerMock.mockReturnValue({
      indexStats: null,
    });
  });

  it("does not render IntentPolicyPanel content before a compile result exists", () => {
    render(<Home />);

    expect(screen.queryByRole("tabpanel", { name: /intent/i })).toBeNull();
    expect(screen.queryByText("General Request")).toBeNull();
    expect(screen.queryByText("Allowed Tools")).toBeNull();
  });

  it("renders IntentPolicyPanel with empty-intent fallback after selecting the Intent tab", () => {
    useCompilerMock.mockReturnValue({
      loading: false,
      result: makeMinimalResult(),
      status: "Ready",
      lastError: null,
      securityFindings: [],
      redactedText: "",
      runCompile: vi.fn(),
      retry: vi.fn(),
      resolveSecurityDecision: vi.fn(),
      cancelSecurityReview: vi.fn(),
    });

    render(<Home />);

    fireEvent.click(screen.getByRole("tab", { name: /^intent$/i }));

    const intentPanel = screen.getByRole("tabpanel", { name: /intent/i });
    expect(intentPanel).toBeVisible();
    expect(within(intentPanel).getByText("General Request")).toBeVisible();
    expect(
      within(intentPanel).getByText(
        /no special intent signals were inferred, so the compiler is treating this as a general-purpose request/i,
      ),
    ).toBeVisible();
    expect(within(intentPanel).getByText("Policy")).toBeVisible();
    expect(within(intentPanel).getByText("Allowed Tools")).toBeVisible();
    expect(
      within(intentPanel).getByText("No tool allowlist needed for this request."),
    ).toBeVisible();
  });

  it("renders detected intents and policy details when compile result includes intent metadata", () => {
    useCompilerMock.mockReturnValue({
      loading: false,
      result: makeIntentRichResult(),
      status: "Ready",
      lastError: null,
      securityFindings: [],
      redactedText: "",
      runCompile: vi.fn(),
      retry: vi.fn(),
      resolveSecurityDecision: vi.fn(),
      cancelSecurityReview: vi.fn(),
    });

    render(<Home />);

    fireEvent.click(screen.getByRole("tab", { name: /^intent$/i }));

    const intentPanel = screen.getByRole("tabpanel", { name: /intent/i });
    expect(intentPanel).toBeVisible();
    expect(within(intentPanel).getByText("finance")).toBeVisible();
    expect(within(intentPanel).getByText("Teaching")).toBeVisible();
    expect(within(intentPanel).getByText("Risk")).toBeVisible();
    expect(within(intentPanel).getByText("High")).toBeVisible();
    expect(within(intentPanel).getByText("Human Approval Required")).toBeVisible();
    expect(within(intentPanel).getByText("Workspace Read")).toBeVisible();
    expect(within(intentPanel).getByText("Secret Access")).toBeVisible();
  });
});
