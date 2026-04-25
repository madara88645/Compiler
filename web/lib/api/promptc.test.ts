import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiJson } from "../../config";
import { compilePrompt, normalizeCompileResponse } from "./promptc";

vi.mock("../../config", async () => {
  const actual = await vi.importActual<typeof import("../../config")>("../../config");
  return {
    ...actual,
    apiJson: vi.fn(),
  };
});

const apiJsonMock = vi.mocked(apiJson);

describe("compile response normalization", () => {
  it("treats incomplete security metadata without findings as safe", () => {
    const response = normalizeCompileResponse({
      system_prompt: "system",
      user_prompt: "user",
      plan: "plan",
      expanded_prompt: "expanded",
      ir: {
        metadata: {
          security: {},
        },
      },
    });

    expect(response.ir.metadata?.security?.is_safe).toBe(true);
    expect(response.ir.metadata?.security?.findings).toEqual([]);
  });

  it("fills policy defaults when ir_v2 is missing policy fields", () => {
    const response = normalizeCompileResponse({
      system_prompt: "system",
      user_prompt: "user",
      plan: "plan",
      expanded_prompt: "expanded",
      ir: {},
      ir_v2: {
        domain: "finance",
      },
    });

    expect(response.ir_v2?.policy?.risk_level).toBe("low");
    expect(response.ir_v2?.policy?.execution_mode).toBe("advice_only");
    expect(response.ir_v2?.policy?.risk_domains).toEqual([]);
  });
});

describe("compilePrompt", () => {
  beforeEach(() => {
    apiJsonMock.mockReset();
  });

  it("retries transient compile API failures once", async () => {
    apiJsonMock
      .mockRejectedValueOnce(new ApiError(503, "Backend unavailable", null))
      .mockResolvedValueOnce({
        system_prompt: "system",
        user_prompt: "user",
        plan: "plan",
        expanded_prompt: "expanded",
        ir: {},
      });

    const response = await compilePrompt({
      text: "Summarize an incident report.",
      diagnostics: true,
      v2: true,
      render_v2_prompts: true,
      mode: "conservative",
    });

    expect(apiJsonMock).toHaveBeenCalledTimes(2);
    expect(response.expanded_prompt).toBe("expanded");
  });

  it("retries a null compile response once", async () => {
    apiJsonMock
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        system_prompt: "system",
        user_prompt: "user",
        plan: "plan",
        expanded_prompt: "expanded",
        ir: {},
      });

    const response = await compilePrompt({
      text: "Summarize an incident report.",
      diagnostics: true,
      v2: true,
      render_v2_prompts: true,
      mode: "conservative",
    });

    expect(apiJsonMock).toHaveBeenCalledTimes(2);
    expect(response.expanded_prompt).toBe("expanded");
  });

  it("retries an empty compile response once", async () => {
    apiJsonMock
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({
        system_prompt: "system",
        user_prompt: "user",
        plan: "plan",
        expanded_prompt: "expanded",
        ir: {},
      });

    const response = await compilePrompt({
      text: "Summarize an incident report.",
      diagnostics: true,
      v2: true,
      render_v2_prompts: true,
      mode: "conservative",
    });

    expect(apiJsonMock).toHaveBeenCalledTimes(2);
    expect(response.expanded_prompt).toBe("expanded");
  });

  it("throws after two invalid compile responses", async () => {
    apiJsonMock.mockResolvedValueOnce(null).mockResolvedValueOnce({});

    await expect(
      compilePrompt({
        text: "Summarize an incident report.",
        diagnostics: true,
        v2: true,
        render_v2_prompts: true,
        mode: "conservative",
      }),
    ).rejects.toThrow("Invalid compile response");

    expect(apiJsonMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry non-transient compile API failures", async () => {
    const error = new ApiError(400, "Bad request", null);
    apiJsonMock.mockRejectedValueOnce(error);

    await expect(
      compilePrompt({
        text: "Summarize an incident report.",
        diagnostics: true,
        v2: true,
        render_v2_prompts: true,
        mode: "conservative",
      }),
    ).rejects.toBe(error);

    expect(apiJsonMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry aborted compile requests", async () => {
    const controller = new AbortController();
    const abortedError = new DOMException("The operation was aborted.", "AbortError");
    controller.abort();

    apiJsonMock.mockRejectedValueOnce(abortedError);

    await expect(
      compilePrompt(
        {
          text: "Summarize an incident report.",
          diagnostics: true,
          v2: true,
          render_v2_prompts: true,
          mode: "conservative",
        },
        controller.signal,
      ),
    ).rejects.toMatchObject({ name: "AbortError" });

    expect(apiJsonMock).toHaveBeenCalledTimes(1);
  });
});
