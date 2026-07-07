import { act, fireEvent, render, screen } from "@testing-library/react";
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

function mockMatchMedia(prefersReducedMotion: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: prefersReducedMotion,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

describe("Example autocompile", () => {
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

  it("auto-compiles the example text once the typewriter fill completes (reduced motion)", () => {
    mockMatchMedia(true);
    render(<Home />);

    const exampleButton = screen.getByRole("button", { name: "or try an example" });
    fireEvent.click(exampleButton);

    expect(runCompileMock).toHaveBeenCalledTimes(1);
    const [text, mode] = runCompileMock.mock.calls[0];
    expect(text).toMatch(/nginx access\.log/);
    expect(mode).toBe("conservative");
  });

  it("auto-compiles after the typewriter animation finishes (motion allowed)", async () => {
    mockMatchMedia(false);
    vi.useFakeTimers();

    render(<Home />);

    const exampleButton = screen.getByRole("button", { name: "or try an example" });
    fireEvent.click(exampleButton);

    // Typewriter has not finished yet — no compile call should have happened.
    expect(runCompileMock).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(runCompileMock).toHaveBeenCalledTimes(1);
    const [text] = runCompileMock.mock.calls[0];
    expect(text).toMatch(/nginx access\.log/);

    vi.useRealTimers();
  });

  it("does not auto-compile when the visitor types manually into the textarea", () => {
    mockMatchMedia(true);
    render(<Home />);

    const textarea = screen.getByLabelText("Describe what you want compiled");
    fireEvent.change(textarea, { target: { value: "My own manual prompt" } });

    expect(runCompileMock).not.toHaveBeenCalled();

    const compileButtons = screen.getAllByRole("button", { name: /Compile Prompt/ });
    fireEvent.click(compileButtons[0]);

    expect(runCompileMock).toHaveBeenCalledTimes(1);
    expect(runCompileMock.mock.calls[0][0]).toBe("My own manual prompt");
  });
});
