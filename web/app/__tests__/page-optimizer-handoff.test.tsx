import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const useCompilerMock = vi.fn();
const useContextManagerMock = vi.fn();
const routerPushMock = vi.fn();

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
    push: routerPushMock,
  }),
}));

const SEND_TO_OPTIMIZER_LABEL = "Send to Optimizer";

describe("Compile-to-optimizer handoff", () => {
  beforeEach(() => {
    localStorage.clear();
    routerPushMock.mockReset();
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

  it("does not render the Send to Optimizer button before a compile result exists", () => {
    render(<Home />);

    expect(screen.queryByRole("button", { name: SEND_TO_OPTIMIZER_LABEL })).toBeNull();
  });

  it("writes the active tab's (user prompt) content to promptc_optimizer_prompt and navigates to /optimizer", () => {
    useCompilerMock.mockReturnValue({
      loading: false,
      result: {
        system_prompt: "Compiled system prompt",
        user_prompt: "Compiled user prompt for the active tab",
      },
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

    const cta = screen.getByRole("button", { name: SEND_TO_OPTIMIZER_LABEL });
    fireEvent.click(cta);

    expect(localStorage.getItem("promptc_optimizer_prompt")).toBe(
      "Compiled user prompt for the active tab",
    );
    expect(routerPushMock).toHaveBeenCalledWith("/optimizer");
  });

  it("sends the active tab's content — not the user tab's — when a different tab is selected", () => {
    useCompilerMock.mockReturnValue({
      loading: false,
      result: {
        system_prompt: "Compiled system prompt for the system tab",
        user_prompt: "Compiled user prompt",
      },
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

    fireEvent.click(screen.getByRole("tab", { name: /System Prompt/i }));

    const cta = screen.getByRole("button", { name: SEND_TO_OPTIMIZER_LABEL });
    fireEvent.click(cta);

    expect(localStorage.getItem("promptc_optimizer_prompt")).toBe(
      "Compiled system prompt for the system tab",
    );
    expect(routerPushMock).toHaveBeenCalledWith("/optimizer");
  });
});
