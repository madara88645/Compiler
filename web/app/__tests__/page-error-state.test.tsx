import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const retryMock = vi.fn();
const runCompileMock = vi.fn();
const useCompilerMock = vi.fn();

function buildCompilerState(overrides: Record<string, unknown> = {}) {
  return {
    loading: false,
    result: null,
    status: "Ready",
    lastError: null,
    securityFindings: [],
    redactedText: "",
    runCompile: runCompileMock,
    retry: retryMock,
    resolveSecurityDecision: vi.fn(),
    cancelSecurityReview: vi.fn(),
    ...overrides,
  };
}

function buildCompileResult(suffix: string) {
  return {
    system_prompt: `system ${suffix}`,
    user_prompt: `user ${suffix}`,
    plan: `plan ${suffix}`,
    expanded_prompt: `expanded ${suffix}`,
    system_prompt_v2: `system v2 ${suffix}`,
    user_prompt_v2: `user v2 ${suffix}`,
    plan_v2: `plan v2 ${suffix}`,
    expanded_prompt_v2: `expanded v2 ${suffix}`,
    processing_ms: 42,
    ir: {
      metadata: {
        context_suggestions: [],
        context_snippets: [],
      },
    },
    critique: null,
  };
}

vi.mock("../hooks/useCompiler", () => ({
  useCompiler: () => useCompilerMock(),
}));

vi.mock("../components/ContextManager", () => ({
  default: () => <div data-testid="context-manager" />,
}));

vi.mock("../components/InfoButton", () => ({
  default: ({ title }: { title: string }) => <button type="button">{title}</button>,
}));

vi.mock("../components/QualityCoach", () => ({
  default: ({ prompt }: { prompt: string }) => <div>Quality coach for: {prompt}</div>,
}));

vi.mock("../components/SecurityAlert", () => ({
  default: () => <div>Security alert</div>,
}));

vi.mock("../components/IntentPolicyPanel", () => ({
  default: ({ result }: { result: { expanded_prompt_v2?: string; expanded_prompt?: string } }) => (
    <div data-testid="intent-panel">{result.expanded_prompt_v2 ?? result.expanded_prompt}</div>
  ),
}));

describe("Prompt Compiler home", () => {
  beforeEach(() => {
    retryMock.mockReset();
    runCompileMock.mockReset();
    window.localStorage.clear();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
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

  it("loads conservative mode from localStorage and persists toggle changes", () => {
    window.localStorage.setItem("promptc_conservative_mode", "false");

    render(<Home />);

    const toggle = screen.getByRole("switch", { name: "Conservative mode OFF" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");

    fireEvent.click(toggle);

    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(window.localStorage.getItem("promptc_conservative_mode")).toBe("true");
  });

  it("keeps generate disabled for empty prompts", () => {
    render(<Home />);

    expect(screen.getByRole("button", { name: /Generate/i }).hasAttribute("disabled")).toBe(true);
  });

  it("submits the current prompt with Ctrl/Cmd Enter using the selected mode", () => {
    window.localStorage.setItem("promptc_conservative_mode", "false");

    render(<Home />);

    fireEvent.change(screen.getByLabelText("Describe what you want compiled"), {
      target: { value: "Review this PR diff." },
    });
    fireEvent.keyDown(screen.getByLabelText("Describe what you want compiled"), {
      key: "Enter",
      ctrlKey: true,
    });

    expect(runCompileMock).toHaveBeenCalledTimes(1);
    expect(runCompileMock).toHaveBeenCalledWith("Review this PR diff.", "default");
  });

  it("shows selected tab content, copies it, and resets to intent for a new result", () => {
    const firstResult = buildCompileResult("first");
    const nextResult = buildCompileResult("second");

    useCompilerMock.mockReturnValue(buildCompilerState({ result: firstResult, status: "Done in 42ms" }));

    const { rerender } = render(<Home />);

    fireEvent.click(screen.getByRole("tab", { name: "System" }));

    expect((screen.getByLabelText("Compiled prompt output") as HTMLTextAreaElement).value).toBe("system v2 first");

    fireEvent.click(screen.getByRole("button", { name: "Copy to Clipboard" }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("system v2 first");

    useCompilerMock.mockReturnValue(buildCompilerState({ result: nextResult, status: "Done in 42ms" }));
    rerender(<Home />);

    expect(screen.getByRole("tab", { name: "Intent" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("intent-panel").textContent).toContain("expanded v2 second");
  });
});
