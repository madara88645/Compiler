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

const BENCHMARK_CTA_LABEL = "Benchmark this prompt — raw vs compiled";

describe("Compile-to-benchmark handoff", () => {
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

  it("does not render the benchmark CTA before a compile result exists", () => {
    render(<Home />);

    expect(screen.queryByRole("button", { name: BENCHMARK_CTA_LABEL })).toBeNull();
  });

  it("writes the raw typed prompt to localStorage and navigates to /benchmark after a compile result exists", () => {
    useCompilerMock.mockReturnValue({
      loading: false,
      result: { system_prompt: "Compiled system prompt", user_prompt: "Compiled user prompt" },
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

    fireEvent.change(screen.getByLabelText("Describe what you want compiled"), {
      target: { value: "Summarize this nginx log file for suspicious IPs." },
    });

    const cta = screen.getByRole("button", { name: BENCHMARK_CTA_LABEL });
    fireEvent.click(cta);

    expect(localStorage.getItem("promptc_benchmark_prompt")).toBe(
      "Summarize this nginx log file for suspicious IPs.",
    );
    expect(routerPushMock).toHaveBeenCalledWith("/benchmark");
  });
});
