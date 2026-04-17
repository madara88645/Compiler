import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const retryMock = vi.fn();
const useCompilerMock = vi.fn();

vi.mock("../hooks/useCompiler", () => ({
  useCompiler: () => useCompilerMock(),
}));

vi.mock("../components/ContextManager", () => ({
  default: () => <div data-testid="context-manager" />,
}));

describe("Prompt Compiler home", () => {
  beforeEach(() => {
    retryMock.mockReset();
    useCompilerMock.mockReturnValue({
      loading: false,
      result: null,
      status: "Error",
      lastError: new Error("Could not reach the backend. Check the API URL or make sure the server is running."),
      securityFindings: [],
      redactedText: "",
      runCompile: vi.fn(),
      retry: retryMock,
      resolveSecurityDecision: vi.fn(),
      cancelSecurityReview: vi.fn(),
    });
  });

  it("keeps compile failures visible in the output workspace", () => {
    render(<Home />);

    expect(screen.getByText("Compile failed")).toBeTruthy();
    expect(
      screen.getByText("Could not reach the backend. Check the API URL or make sure the server is running."),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Retry compile" }));

    expect(retryMock).toHaveBeenCalledTimes(1);
  });
});
