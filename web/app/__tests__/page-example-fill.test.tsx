import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const useCompilerMock = vi.fn();
const useContextManagerMock = vi.fn();

vi.mock("../hooks/useCompiler", () => ({ useCompiler: () => useCompilerMock() }));
vi.mock("../hooks/useContextManager", () => ({ useContextManager: () => useContextManagerMock() }));
vi.mock("../components/ContextManager", () => ({ default: () => <div data-testid="context-manager" /> }));
vi.mock("../components/OutputSkeleton", () => ({ default: () => <div data-testid="output-skeleton" /> }));

describe("main page example fill", () => {
  beforeEach(() => {
    localStorage.clear();
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
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
    useContextManagerMock.mockReturnValue({ indexStats: null });
  });

  it("fills the prompt textarea from the example button", () => {
    render(<Home />);

    fireEvent.click(screen.getByText(/or try an example/i));

    const textarea = screen.getByLabelText("Describe what you want compiled") as HTMLTextAreaElement;
    expect(textarea.value.length).toBeGreaterThan(0);
  });
});
