import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import SkillExportPanel from "./ExportPanel";

const { apiFetch } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
}));

vi.mock("@/config", () => ({
  apiFetch,
}));

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
  });

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
});
