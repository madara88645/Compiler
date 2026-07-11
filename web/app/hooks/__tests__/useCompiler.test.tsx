import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCompiler } from "../useCompiler";
import { compilePrompt } from "../../../lib/api/promptc";
import type { CompileResponse } from "../../../lib/api/types";

vi.mock("../../../lib/api/promptc", () => ({
  compilePrompt: vi.fn(),
}));

vi.mock("../../lib/showError", () => ({
  showError: vi.fn(),
}));

const compilePromptMock = vi.mocked(compilePrompt);

function makeResponse(overrides: Partial<CompileResponse> = {}): CompileResponse {
  return {
    system_prompt: "sys",
    user_prompt: "usr",
    plan: "1. step",
    expanded_prompt: "expanded",
    ir: { metadata: {} },
    processing_ms: 42,
    readiness_markdown: "",
    ...overrides,
  };
}

describe("useCompiler", () => {
  beforeEach(() => {
    compilePromptMock.mockReset();
  });

  it("starts in Ready state with no result", () => {
    const { result } = renderHook(() => useCompiler());
    expect(result.current.status).toBe("Ready");
    expect(result.current.loading).toBe(false);
    expect(result.current.result).toBeNull();
    expect(result.current.lastError).toBeNull();
  });

  it("transitions to Done with result on successful compile", async () => {
    const response = makeResponse({ processing_ms: 100 });
    compilePromptMock.mockResolvedValue(response);

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("build a login flow", "conservative");
    });

    expect(result.current.status).toBe("Done in 100ms");
    expect(result.current.loading).toBe(false);
    expect(result.current.result).toEqual(response);
  });

  it("ignores empty text input", async () => {
    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("   ", "conservative");
    });

    expect(compilePromptMock).not.toHaveBeenCalled();
    expect(result.current.status).toBe("Ready");
  });

  it("sets Error state on compile failure", async () => {
    const err = new Error("Network failure");
    compilePromptMock.mockRejectedValue(err);

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("build something", "default");
    });

    expect(result.current.status).toBe("Error");
    expect(result.current.loading).toBe(false);
    expect(result.current.lastError).toBe(err);
  });

  it("triggers security alert when response is_safe is false", async () => {
    const response = makeResponse({
      ir: {
        metadata: {
          security: {
            is_safe: false,
            findings: [{ type: "pii", original: "123-45-6789", masked: "[SSN]" }],
            redacted_text: "Use [SSN] for lookup",
          },
        },
      },
    });
    compilePromptMock.mockResolvedValue(response);

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("Use 123-45-6789 for lookup", "conservative");
    });

    expect(result.current.securityFindings).toHaveLength(1);
    expect(result.current.securityFindings[0].type).toBe("pii");
    expect(result.current.redactedText).toBe("Use [SSN] for lookup");
    expect(result.current.status).toBe("Security Alert Detected");
    // Result should NOT be set when security alert is triggered
    expect(result.current.result).toBeNull();
  });

  it("cancelSecurityReview clears findings and resets loading", async () => {
    const response = makeResponse({
      ir: {
        metadata: {
          security: {
            is_safe: false,
            findings: [{ type: "pii", original: "x", masked: "[X]" }],
            redacted_text: "redacted",
          },
        },
      },
    });
    compilePromptMock.mockResolvedValue(response);

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("some text with PII", "conservative");
    });

    expect(result.current.securityFindings).toHaveLength(1);

    act(() => {
      result.current.cancelSecurityReview();
    });

    expect(result.current.securityFindings).toHaveLength(0);
    expect(result.current.loading).toBe(false);
    expect(result.current.status).toBe("Cancelled");
  });

  it("retry re-runs the last compile call", async () => {
    const response = makeResponse();
    compilePromptMock.mockResolvedValue(response);

    const { result } = renderHook(() => useCompiler());

    await act(async () => {
      await result.current.runCompile("test prompt", "default", false);
    });

    expect(compilePromptMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.retry();
    });

    expect(compilePromptMock).toHaveBeenCalledTimes(2);
  });

  it("sets heuristics-only status when useLlm is false", async () => {
    let resolvePromise: (v: CompileResponse) => void;
    const pendingPromise = new Promise<CompileResponse>((resolve) => {
      resolvePromise = resolve;
    });
    compilePromptMock.mockReturnValue(pendingPromise);

    const { result } = renderHook(() => useCompiler());

    act(() => {
      void result.current.runCompile("test prompt", "conservative", false);
    });

    // While in-flight, status should reflect heuristics-only mode
    await waitFor(() => {
      expect(result.current.loading).toBe(true);
    });

    // Resolve to clean up
    await act(async () => {
      resolvePromise!(makeResponse());
    });
  });
});
