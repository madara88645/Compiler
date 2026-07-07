import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const runCompileMock = vi.fn();
const useCompilerMock = vi.fn();
const useContextManagerMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

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

describe("Heuristics-only engine toggle", () => {
  beforeEach(() => {
    localStorage.clear();
    runCompileMock.mockReset();
    useCompilerMock.mockReturnValue({
      loading: false,
      result: null,
      status: "Ready",
      lastError: null,
      securityFindings: [],
      redactedText: "",
      runCompile: runCompileMock,
      retry: vi.fn(),
      resolveSecurityDecision: vi.fn(),
      cancelSecurityReview: vi.fn(),
    });
    useContextManagerMock.mockReturnValue({
      indexStats: null,
    });
  });

  it("defaults to the LLM-backed engine and shows AI MODE", () => {
    render(<Home />);

    const toggle = screen.getByRole("switch", { name: "Heuristics-only engine OFF" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText("AI MODE")).toBeTruthy();
  });

  it("switches to the heuristic engine and stops claiming AI MODE", () => {
    render(<Home />);

    const toggle = screen.getByRole("switch", { name: "Heuristics-only engine OFF" });
    fireEvent.click(toggle);

    expect(screen.getByRole("switch", { name: "Heuristics-only engine ON" })).toBeTruthy();
    expect(screen.getByText("HEURISTIC MODE")).toBeTruthy();
    expect(screen.queryByText("AI MODE")).toBeNull();
  });

  it("disables Conservative mode once the heuristic engine is active", () => {
    render(<Home />);

    fireEvent.click(screen.getByRole("switch", { name: "Heuristics-only engine OFF" }));

    const conservativeToggle = screen.getByRole("switch", { name: "Conservative mode ON" });
    expect(conservativeToggle).toBeDisabled();
  });

  it("passes the heuristic engine choice through to the compile call", () => {
    render(<Home />);

    fireEvent.click(screen.getByRole("switch", { name: "Heuristics-only engine OFF" }));

    fireEvent.change(screen.getByLabelText("Describe what you want compiled"), {
      target: { value: "Summarize this incident report." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Compile Prompt/i })[0]);

    expect(runCompileMock).toHaveBeenCalledWith("Summarize this incident report.", "conservative", false);
  });
});
