import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import ExportPanel from "./ExportPanel";

const { apiFetch } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
}));

const { push } = vi.hoisted(() => ({
  push: vi.fn(),
}));

vi.mock("@/config", () => ({
  apiFetch,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("Agent ExportPanel", () => {
  beforeEach(() => {
    apiFetch.mockReset();
    push.mockReset();
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
    window.localStorage.clear();
  });

  test("exposes pressed state for the selected target and clears output mode tabs for the handoff target", async () => {
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

    expect(sdkButton.getAttribute("aria-checked")).toBe("false");
    expect(projectPackButton.getAttribute("aria-checked")).toBe("true");
    expect(screen.queryByRole("radio", { name: "Python" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "TypeScript" })).toBeNull();

    // Selecting the handoff target must not trigger another export call.
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  test("Claude Project Pack hands off to Agent Packs instead of exporting inline", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("radio", { name: "Claude Project Pack" }));

    const handoffButton = await screen.findByRole("button", { name: /continue in agent packs/i });
    fireEvent.click(handoffButton);

    expect(window.localStorage.getItem("promptc_agent_pack_goal")).toBe("# Agent\n\n## Role\nTest");
    expect(push).toHaveBeenCalledWith("/agent-packs");
    // Still only the initial (Claude Agent SDK) export call — no duplicate export request.
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  test("requests the TypeScript Claude Agent SDK export when TypeScript tab is selected", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("radio", { name: "TypeScript" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const [, options] = apiFetch.mock.calls.at(-1);
    expect(JSON.parse(options.body).format).toBe("claude-agent-sdk-ts");
  });

  test("shows the destination file path for a single-file export result", async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        python_code: null,
        yaml_config: null,
        code: "# Agent\n\nRole: Test",
        files: [{ path: ".claude/agents/test-agent.md", content: "# Agent\n\nRole: Test" }],
      }),
    });

    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("radio", { name: "Claude Subagent" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());

    expect(await screen.findByText(".claude/agents/test-agent.md")).toBeInTheDocument();
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
