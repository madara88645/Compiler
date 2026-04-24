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
});
