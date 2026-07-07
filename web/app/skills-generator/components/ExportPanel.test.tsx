import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import SkillExportPanel from "./ExportPanel";

const { apiFetch } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
}));

vi.mock("@/config", async () => {
  const actual = await vi.importActual<typeof import("@/config")>("@/config");
  return {
    ...actual,
    apiFetch,
  };
});

describe("Skill ExportPanel", () => {
  beforeEach(() => {
    apiFetch.mockReset();
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        python_code: "def tool(): pass",
        json_config: '{"name":"tool"}',
        code: "def tool(): pass",
        files: [],
      }),
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    vi.stubGlobal("URL", {
      ...globalThis.URL,
      createObjectURL: vi.fn(() => "blob:export"),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function spyOnAnchorClicks() {
    const clickSpy = vi.fn();
    const anchors: HTMLAnchorElement[] = [];
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", { configurable: true, value: clickSpy });
        anchors.push(element as HTMLAnchorElement);
      }
      return element;
    });
    return { clickSpy, anchors };
  }

  test("exposes pressed state for the selected target and output mode", async () => {
    render(<SkillExportPanel skillDefinition={"# Tool\n\n## Name\nweb_search"} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    const claudeToolButton = screen.getByRole("radio", { name: "Claude Tool" });
    const mcpToolButton = screen.getByRole("radio", { name: "Claude MCP Tool" });
    const jsonButton = screen.getByRole("radio", { name: "JSON" });
    const pythonButton = screen.getByRole("radio", { name: "Python" });

    expect(claudeToolButton.getAttribute("aria-checked")).toBe("true");
    expect(mcpToolButton.getAttribute("aria-checked")).toBe("false");
    expect(jsonButton.getAttribute("aria-checked")).toBe("true");
    expect(pythonButton.getAttribute("aria-checked")).toBe("false");

    fireEvent.click(mcpToolButton);

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2));

    expect(claudeToolButton.getAttribute("aria-checked")).toBe("false");
    expect(mcpToolButton.getAttribute("aria-checked")).toBe("true");
    expect(screen.queryByRole("radio", { name: "JSON" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "Python" })).toBeNull();

    const filesButton = screen.getByRole("radio", { name: "Files" });
    expect(filesButton.getAttribute("aria-checked")).toBe("true");
  });

  test("requests the Claude MCP tool export", async () => {
    render(<SkillExportPanel skillDefinition={"# Tool\n\n## Name\nweb_search"} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("radio", { name: "Claude MCP Tool" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const [, options] = apiFetch.mock.calls.at(-1);
    expect(JSON.parse(options.body).format).toBe("claude-mcp-tool-stub");
  });

  test("shows the destination file path for a single-file export result", async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        python_code: null,
        json_config: null,
        code: null,
        files: [{ path: ".claude/mcp/tool.py", content: "def tool(): pass" }],
      }),
    });

    render(<SkillExportPanel skillDefinition={"# Tool\n\n## Name\nweb_search"} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("radio", { name: "Claude MCP Tool" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());

    expect(await screen.findByText(".claude/mcp/tool.py")).toBeInTheDocument();
  });

  test("announces copy success via sr-only live region, not the copy button", async () => {
    render(<SkillExportPanel skillDefinition={"# Tool\n\n## Name\nweb_search"} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    const copyButton = screen.getByRole("button", { name: "Copy code" });
    expect(copyButton.getAttribute("aria-live")).toBeNull();

    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('{"name":"tool"}');
    });

    const liveRegion = copyButton.querySelector(".sr-only");
    expect(liveRegion).not.toBeNull();
    expect(liveRegion?.getAttribute("aria-live")).toBe("polite");
    expect(liveRegion).toHaveTextContent("Copied to clipboard");
    expect(copyButton.getAttribute("aria-label")).toBe("Copied to clipboard");
  });

  test("downloads the current single-value export as a blob named after its format", async () => {
    const { clickSpy, anchors } = spyOnAnchorClicks();

    render(<SkillExportPanel skillDefinition={"# Tool\n\n## Name\nweb_search"} />);
    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    // No zip button for a single-value (in this case zero bundled files) result.
    expect(screen.queryByRole("button", { name: "Download .zip" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Download file" }));

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(anchors[anchors.length - 1].download).toBe("claude-tool-use.json");
  });

  test("shows a working zip download only when the export produced multiple files", async () => {
    apiFetch.mockImplementation(async (_url: string, options: { body: string }) => {
      const body = JSON.parse(options.body);
      if (body.format === "claude-mcp-tool-stub") {
        return {
          ok: true,
          json: async () => ({
            python_code: "from mcp.server.fastmcp import FastMCP",
            json_config: null,
            code: "from mcp.server.fastmcp import FastMCP",
            files: [
              { path: "server.py", content: "from mcp.server.fastmcp import FastMCP" },
              { path: "README.md", content: "# web_search MCP Tool Stub" },
            ],
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          python_code: "def tool(): pass",
          json_config: '{"name":"tool"}',
          code: "def tool(): pass",
          files: [],
        }),
      };
    });

    const { clickSpy, anchors } = spyOnAnchorClicks();

    render(<SkillExportPanel skillDefinition={"# Tool\n\n## Name\nweb_search"} />);
    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("radio", { name: "Claude MCP Tool" }));
    await screen.findByRole("button", { name: "Download .zip" });

    // Both files still show up in the existing multi-file selector.
    expect(screen.getByRole("option", { name: "server.py" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "README.md" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Download .zip" }));

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(anchors[anchors.length - 1].download).toBe("claude-mcp-tool-stub-export.zip");
  });

  test("shows a friendly message for a failed export and retries via the retry button", async () => {
    apiFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    render(<SkillExportPanel skillDefinition={"# Tool\n\n## Name\nweb_search"} />);
    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "The service is temporarily unavailable or still waking up. Please retry in a few seconds.",
    );
    expect(alert).not.toHaveTextContent("Failed to fetch");

    apiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        python_code: "def tool(): pass",
        json_config: '{"name":"tool"}',
        code: "def tool(): pass",
        files: [],
      }),
    });

    fireEvent.click(screen.getByRole("button", { name: /retry export/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('{"name":"tool"}')).toBeInTheDocument();
  });
});
