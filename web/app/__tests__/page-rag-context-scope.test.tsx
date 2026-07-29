import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const useCompilerMock = vi.fn();
const useContextManagerMock = vi.fn();

vi.mock("../hooks/useCompiler", () => ({
  useCompiler: () => useCompilerMock(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
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

describe("RAG context scope banner", () => {
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
  });

  it("does not show active RAG banner for persisted docs until attached", () => {
    useContextManagerMock.mockReturnValue({
      indexStats: { docs: 2858, chunks: 6899, total_bytes: 1_000_000 },
      contextAttached: false,
      contextSource: "none",
      attachContext: vi.fn(),
      detachContext: vi.fn(),
    });

    render(<Home />);

    expect(screen.queryByText("RAG Context Active")).toBeNull();
  });

  it("shows active RAG banner with detach when session scope is attached", () => {
    const detachContext = vi.fn();
    useContextManagerMock.mockReturnValue({
      indexStats: { docs: 2, chunks: 8, total_bytes: 4096 },
      contextAttached: true,
      contextSource: "library",
      attachContext: vi.fn(),
      detachContext,
    });

    render(<Home />);

    expect(screen.getByText("RAG Context Active")).toBeTruthy();
    expect(screen.getByText("2 docs attached")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Detach" }));
    expect(detachContext).toHaveBeenCalledTimes(1);
  });
});
