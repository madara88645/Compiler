import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const retryMock = vi.fn();
const useCompilerMock = vi.fn();

function buildCompilerState(overrides: Record<string, unknown> = {}) {
  return {
    loading: false,
    result: null,
    status: "Ready",
    lastError: null,
    securityFindings: [],
    redactedText: "",
    runCompile: vi.fn(),
    retry: retryMock,
    resolveSecurityDecision: vi.fn(),
    cancelSecurityReview: vi.fn(),
    ...overrides,
  };
}

vi.mock("../hooks/useCompiler", () => ({
  useCompiler: () => useCompilerMock(),
}));

vi.mock("../components/ContextManager", () => ({
  default: () => <div data-testid="context-manager" />,
}));

describe("Prompt Compiler home", () => {
  beforeEach(() => {
    retryMock.mockReset();
    useCompilerMock.mockReturnValue(buildCompilerState());
  });

  it("keeps compile failures visible in the output workspace", () => {
    useCompilerMock.mockReturnValue(
      buildCompilerState({
        status: "Error",
        lastError: new Error("Could not reach the backend. Check the API URL or make sure the server is running."),
      }),
    );

    render(<Home />);

    expect(screen.getByText("Compile failed")).toBeTruthy();
    expect(
      screen.getByText("Could not reach the backend. Check the API URL or make sure the server is running."),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Retry compile" }));

    expect(retryMock).toHaveBeenCalledTimes(1);
  });

  it("renders stable homepage copy without mojibake glyphs", () => {
    render(<Home />);

    expect(screen.getAllByText("Prompt Compiler").length).toBeGreaterThan(0);
    expect(screen.getByText("Start with any rough request")).toBeTruthy();
    expect(screen.getAllByText("Ctrl/Cmd Enter").length).toBeGreaterThan(0);
    expect(screen.queryByText("ğŸ’ ")).toBeNull();
    expect(screen.queryByText("ğŸ•µï¸")).toBeNull();
    expect(screen.queryByText("â”€â”€")).toBeNull();
  });
});
