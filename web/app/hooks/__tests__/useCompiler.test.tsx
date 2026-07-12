import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCompiler } from "../useCompiler";
import { showError } from "../../lib/showError";
import { compilePrompt } from "../../../lib/api/promptc";
import type { CompileResponse } from "../../../lib/api/types";

vi.mock("../../../lib/api/promptc", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api/promptc")>(
    "../../../lib/api/promptc",
  );
  return {
    ...actual,
    compilePrompt: vi.fn(),
  };
});

vi.mock("../../lib/showError", () => ({
  showError: vi.fn(),
}));

const compilePromptMock = vi.mocked(compilePrompt);
const showErrorMock = vi.mocked(showError);

function buildSuccessResponse(overrides: Partial<CompileResponse> = {}): CompileResponse {
  return {
    system_prompt: "system",
    user_prompt: "user",
    plan: "plan",
    expanded_prompt: "expanded",
    ir: {},
    processing_ms: 42,
    readiness_markdown: "",
    ...overrides,
  };
}

describe("useCompiler", () => {
  beforeEach(() => {
    compilePromptMock.mockReset();
    showErrorMock.mockReset();
  });

  it("exposes the initial ready state", () => {
    const { result } = renderHook(() => useCompiler());

    expect(result.current.loading).toBe(false);
    expect(result.current.result).toBeNull();
    expect(result.current.status).toBe("Ready");
    expect(result.current.lastError).toBeNull();
    expect(result.current.securityFindings).toEqual([]);
    expect(result.current.redactedText).toBe("");
  });

  it("enters loading state while a compile request is in flight", async () => {
    let resolveCompile: ((value: CompileResponse) => void) | null = null;
    compilePromptMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveCompile = resolve;
        }),
    );

    const { result } = renderHook(() => useCompiler());

    let compilePromise!: Promise<void>;
    act(() => {
      compilePromise = result.current.runCompile("Summarize the incident report.", "default", true);
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(true);
    });
    expect(result.current.status).toBe("AI Thinking...");
    expect(result.current.result).toBeNull();

    resolveCompile?.(buildSuccessResponse());
    await act(async () => {
      await compilePromise;
    });
  });

  it("stores a successful compile response and reports processing time", async () => {
    compilePromptMock.mockResolvedValueOnce(buildSuccessResponse({ processing_ms: 128 }));

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("Summarize the incident report.", "conservative", true);
    });

    expect(compilePromptMock).toHaveBeenCalledWith(
      {
        text: "Summarize the incident report.",
        diagnostics: true,
        v2: true,
        render_v2_prompts: true,
        mode: "conservative",
      },
      expect.any(AbortSignal),
    );
    expect(result.current.loading).toBe(false);
    expect(result.current.result?.expanded_prompt).toBe("expanded");
    expect(result.current.status).toBe("Done in 128ms");
    expect(result.current.lastError).toBeNull();
  });

  it("uses the heuristic-only status when LLM mode is disabled", async () => {
    compilePromptMock.mockResolvedValueOnce(buildSuccessResponse());

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("Compile with heuristics only.", "default", false);
    });

    expect(compilePromptMock).toHaveBeenCalledWith(
      expect.objectContaining({ v2: false }),
      expect.any(AbortSignal),
    );
    expect(result.current.status).toBe("Done in 42ms");
  });

  it("surfaces compile failures and calls showError", async () => {
    const error = new Error("Backend unavailable");
    compilePromptMock.mockRejectedValueOnce(error);

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("Summarize the incident report.", "default", true);
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.result).toBeNull();
    expect(result.current.status).toBe("Error");
    expect(result.current.lastError).toBe(error);
    expect(showErrorMock).toHaveBeenCalledWith(error);
  });

  it("pauses on unsafe content and resumes with the chosen security decision", async () => {
    compilePromptMock
      .mockResolvedValueOnce(
        buildSuccessResponse({
          ir: {
            metadata: {
              security: {
                is_safe: false,
                findings: [{ type: "openai_key", original: "sk-live-abc", masked: "sk-live-***" }],
                redacted_text: "Summarize the [REDACTED] report.",
              },
            },
          },
        }),
      )
      .mockResolvedValueOnce(buildSuccessResponse({ processing_ms: 77 }));

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("Summarize the sk-live-abc report.", "default", true);
    });

    expect(result.current.securityFindings).toHaveLength(1);
    expect(result.current.redactedText).toBe("Summarize the [REDACTED] report.");
    expect(result.current.status).toBe("Security Alert Detected");
    expect(result.current.result).toBeNull();

    await act(async () => {
      await result.current.resolveSecurityDecision(true, "default", true);
    });

    expect(result.current.securityFindings).toEqual([]);
    expect(compilePromptMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ text: "Summarize the [REDACTED] report." }),
      expect.any(AbortSignal),
    );
    expect(result.current.result?.expanded_prompt).toBe("expanded");
    expect(result.current.status).toBe("Done in 77ms");
  });

  it("can proceed with the original prompt after a security alert", async () => {
    compilePromptMock
      .mockResolvedValueOnce(
        buildSuccessResponse({
          ir: {
            metadata: {
              security: {
                is_safe: false,
                findings: [{ type: "openai_key", original: "sk-live-abc", masked: "sk-live-***" }],
                redacted_text: "Summarize the [REDACTED] report.",
              },
            },
          },
        }),
      )
      .mockResolvedValueOnce(buildSuccessResponse({ processing_ms: 55 }));

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("Summarize the sk-live-abc report.", "default", true);
    });

    await act(async () => {
      await result.current.resolveSecurityDecision(false, "conservative", false);
    });

    expect(compilePromptMock).toHaveBeenLastCalledWith(
      {
        text: "Summarize the sk-live-abc report.",
        diagnostics: true,
        v2: false,
        render_v2_prompts: true,
        mode: "conservative",
      },
      expect.any(AbortSignal),
    );
    expect(result.current.status).toBe("Done in 55ms");
  });

  it("cancels the security review and returns to a cancelled status", async () => {
    compilePromptMock.mockResolvedValueOnce(
      buildSuccessResponse({
        ir: {
          metadata: {
            security: {
              is_safe: false,
              findings: [{ type: "openai_key", original: "sk-live-abc", masked: "sk-live-***" }],
              redacted_text: "Summarize the [REDACTED] report.",
            },
          },
        },
      }),
    );

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("Summarize the sk-live-abc report.", "default", true);
    });

    act(() => {
      result.current.cancelSecurityReview();
    });

    expect(result.current.securityFindings).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.status).toBe("Cancelled");
  });

  it("ignores abort errors from superseded requests and keeps the latest result", async () => {
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    let rejectFirst: ((error: unknown) => void) | null = null;

    compilePromptMock
      .mockImplementationOnce(
        () =>
          new Promise((_resolve, reject) => {
            rejectFirst = reject;
          }),
      )
      .mockResolvedValueOnce(buildSuccessResponse({ processing_ms: 90 }));

    const { result } = renderHook(() => useCompiler());

    let firstCompile!: Promise<void>;
    act(() => {
      firstCompile = result.current.runCompile("First prompt text.", "default", true);
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(true);
    });

    await act(async () => {
      await result.current.runCompile("Second prompt text.", "default", true);
    });

    rejectFirst?.(abortError);
    await act(async () => {
      await firstCompile;
    });

    expect(result.current.result?.expanded_prompt).toBe("expanded");
    expect(result.current.status).toBe("Done in 90ms");
    expect(result.current.lastError).toBeNull();
    expect(showErrorMock).not.toHaveBeenCalled();
  });

  it("skips empty compile requests and retries the last successful call", async () => {
    compilePromptMock.mockResolvedValue(buildSuccessResponse({ processing_ms: 33 }));

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("   ", "default", true);
    });
    expect(compilePromptMock).not.toHaveBeenCalled();

    await act(async () => {
      await result.current.runCompile("Retry me later.", "conservative", false);
    });
    compilePromptMock.mockClear();

    await act(async () => {
      await result.current.retry();
    });

    expect(compilePromptMock).toHaveBeenCalledWith(
      {
        text: "Retry me later.",
        diagnostics: true,
        v2: false,
        render_v2_prompts: true,
        mode: "conservative",
      },
      expect.any(AbortSignal),
    );
    expect(result.current.status).toBe("Done in 33ms");
  });
});
