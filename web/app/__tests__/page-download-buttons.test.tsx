import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";
import type { CompileResponse } from "../../lib/api/types";

const useCompilerMock = vi.fn();
const useContextManagerMock = vi.fn();
const { downloadFileMock } = vi.hoisted(() => ({
  downloadFileMock: vi.fn(),
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

vi.mock("../lib/downloadFile", () => ({
  downloadFile: downloadFileMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

function makeResult(): CompileResponse {
  return {
    ir: {},
    system_prompt: "system content",
    user_prompt: "user content",
    plan: "plan content",
    expanded_prompt: "expanded content",
    processing_ms: 1,
    request_id: "req_test",
    heuristic_version: "v1",
  } as CompileResponse;
}

describe("Compile output download buttons", () => {
  beforeEach(() => {
    downloadFileMock.mockReset();
    useCompilerMock.mockReturnValue({
      loading: false,
      result: makeResult(),
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

  it("downloads the active text tab's content as <tab>-prompt.md", () => {
    render(<Home />);

    // Default active tab is "user".
    fireEvent.click(screen.getByRole("button", { name: /download as markdown/i }));
    expect(downloadFileMock).toHaveBeenCalledWith(
      "user content",
      "user-prompt.md",
      "text/markdown",
    );

    downloadFileMock.mockClear();
    fireEvent.click(screen.getByRole("tab", { name: /system prompt/i }));
    fireEvent.click(screen.getByRole("button", { name: /download as markdown/i }));
    expect(downloadFileMock).toHaveBeenCalledWith(
      "system content",
      "system-prompt.md",
      "text/markdown",
    );

    downloadFileMock.mockClear();
    fireEvent.click(screen.getByRole("tab", { name: /execution plan/i }));
    fireEvent.click(screen.getByRole("button", { name: /download as markdown/i }));
    expect(downloadFileMock).toHaveBeenCalledWith(
      "plan content",
      "plan-prompt.md",
      "text/markdown",
    );

    downloadFileMock.mockClear();
    fireEvent.click(screen.getByRole("tab", { name: /long-form/i }));
    fireEvent.click(screen.getByRole("button", { name: /download as markdown/i }));
    expect(downloadFileMock).toHaveBeenCalledWith(
      "expanded content",
      "expanded-prompt.md",
      "text/markdown",
    );
  });

  it("downloads the raw compile response as compile-result.json from the JSON tab", () => {
    render(<Home />);

    fireEvent.click(screen.getByRole("tab", { name: /^json$/i }));
    fireEvent.click(screen.getByRole("button", { name: /download as json/i }));

    expect(downloadFileMock).toHaveBeenCalledTimes(1);
    const [content, filename, mimeType] = downloadFileMock.mock.calls[0];
    expect(filename).toBe("compile-result.json");
    expect(mimeType).toBe("application/json");
    expect(JSON.parse(content)).toMatchObject({ user_prompt: "user content" });
  });
});
