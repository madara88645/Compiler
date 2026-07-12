import { render, screen } from "@testing-library/react";
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

function makeResult(): CompileResponse {
  return {
    ir: {},
    system_prompt: "system content",
    user_prompt: "user content",
    plan: "1. Analyze request\n2. Draft the change\n3. Verify",
    expanded_prompt: "expanded content",
    processing_ms: 1,
    request_id: "req_test",
    heuristic_version: "v1",
  } as CompileResponse;
}

describe("Result value strip on home page", () => {
  beforeEach(() => {
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

  it("does not render the value strip before a compile result exists", () => {
    render(<Home />);

    expect(screen.queryByTestId("result-value-strip")).toBeNull();
  });

  it("renders the value strip with pills after a successful compile", () => {
    useCompilerMock.mockReturnValue({
      loading: false,
      result: makeResult(),
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

    expect(screen.getByTestId("result-value-strip")).toBeInTheDocument();
    expect(screen.getByTestId("result-value-pill-plan")).toHaveTextContent("3 plan steps");
  });
});
