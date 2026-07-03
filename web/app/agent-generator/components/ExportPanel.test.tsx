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
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  test("exposes pressed state for the selected target and output mode", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    const sdkButton = screen.getByRole("radio", { name: "Claude Agent SDK" });
    const projectPackButton = screen.getByRole("radio", { name: "Claude Project Pack" });
    const pythonButton = screen.getByRole("radio", { name: "Python" });
    const typeScriptButton = screen.getByRole("radio", { name: "TypeScript" });

    expect(sdkButton.getAttribute("aria-checked")).toBe("true");
    expect(projectPackButton.getAttribute("aria-checked")).toBe("false");
    expect(pythonButton.getAttribute("aria-checked")).toBe("true");
    expect(typeScriptButton.getAttribute("aria-checked")).toBe("false");

    fireEvent.click(projectPackButton);

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2));

    expect(sdkButton.getAttribute("aria-checked")).toBe("false");
    expect(projectPackButton.getAttribute("aria-checked")).toBe("true");
    expect(screen.queryByRole("radio", { name: "Python" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "TypeScript" })).toBeNull();

    const filesButton = screen.getByRole("radio", { name: "Files" });
    expect(filesButton.getAttribute("aria-checked")).toBe("true");
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

  test("announces copy success via sr-only live region, not the copy button", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    const copyButton = screen.getByRole("button", { name: "Copy code" });
    expect(copyButton.getAttribute("aria-live")).toBeNull();

    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("print('hello')");
    });

    const liveRegion = copyButton.querySelector(".sr-only");
    expect(liveRegion).not.toBeNull();
    expect(liveRegion?.getAttribute("aria-live")).toBe("polite");
    expect(liveRegion).toHaveTextContent("Copied to clipboard");
    expect(copyButton.getAttribute("aria-label")).toBe("Copied to clipboard");
  });
});
