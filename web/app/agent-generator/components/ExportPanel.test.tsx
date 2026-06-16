import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import ExportPanel from "./ExportPanel";

const { apiFetch } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
}));

vi.mock("@/config", () => ({
  apiFetch,
}));

describe("Agent ExportPanel", () => {
  beforeEach(() => {
    apiFetch.mockReset();
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        python_code: "print('hello')",
        yaml_config: null,
        code: "print('hello')",
        files: [],
      }),
    });
  });

  test("exposes pressed state for the selected target and output mode", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    const sdkButton = screen.getByRole("button", { name: "Claude Agent SDK" });
    const projectPackButton = screen.getByRole("button", { name: "Claude Project Pack" });
    const pythonButton = screen.getByRole("button", { name: "Python" });
    const typeScriptButton = screen.getByRole("button", { name: "TypeScript" });

    expect(sdkButton.getAttribute("aria-pressed")).toBe("true");
    expect(projectPackButton.getAttribute("aria-pressed")).toBe("false");
    expect(pythonButton.getAttribute("aria-pressed")).toBe("true");
    expect(typeScriptButton.getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(projectPackButton);

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2));

    expect(sdkButton.getAttribute("aria-pressed")).toBe("false");
    expect(projectPackButton.getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByRole("button", { name: "Python" })).toBeNull();
    expect(screen.queryByRole("button", { name: "TypeScript" })).toBeNull();

    const filesButton = screen.getByRole("button", { name: "Files" });
    expect(filesButton.getAttribute("aria-pressed")).toBe("true");
  });

  test("requests the Claude project pack export", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("radio", { name: "Claude Project Pack" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const [, options] = apiFetch.mock.calls.at(-1);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body).format).toBe("claude-project-pack");
  });

  test("requests the TypeScript Claude Agent SDK export when TypeScript tab is selected", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("radio", { name: "TypeScript" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const [, options] = apiFetch.mock.calls.at(-1);
    expect(JSON.parse(options.body).format).toBe("claude-agent-sdk-ts");
  });
});
