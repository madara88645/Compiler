import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

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

describe("Conservative mode toggle", () => {
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

  it("renders as a switch with conservative mode on by default", () => {
    render(<Home />);

    const toggle = screen.getByRole("switch", { name: "Conservative mode ON" });

    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });

  it("toggles conservative mode off and on when clicked", () => {
    render(<Home />);

    const toggle = screen.getByRole("switch", { name: "Conservative mode ON" });

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(toggle.getAttribute("aria-label")).toBe("Conservative mode OFF");

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(toggle.getAttribute("aria-label")).toBe("Conservative mode ON");
  });

  it("receives keyboard focus", () => {
    render(<Home />);

    const toggle = screen.getByRole("switch", { name: "Conservative mode ON" });
    toggle.focus();

    expect(document.activeElement).toBe(toggle);
  });
});
