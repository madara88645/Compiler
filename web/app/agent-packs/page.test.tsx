import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import AgentPacksPage from "./page";

const { apiJson, apiFetch } = vi.hoisted(() => ({
  apiJson: vi.fn(),
  apiFetch: vi.fn(),
}));

vi.mock("@/config", () => ({
  apiJson,
  apiFetch,
  buildGeneratorApiHeaders: (headers: HeadersInit = {}) => headers,
}));

vi.mock("../lib/showError", () => ({
  showError: vi.fn(),
}));

describe("Agent Packs page", () => {
  beforeEach(() => {
    apiJson.mockReset();
    apiFetch.mockReset();
    apiJson.mockResolvedValue({
      provider: "claude",
      pack_type: "pr-reviewer",
      download_name: "saas-pr-reviewer-claude",
      preview_order: ["claude_md", "agents", "workflow"],
      files: [
        { path: "CLAUDE.md", content: "# Claude PR Reviewer Memory", kind: "claude_md" },
        { path: ".claude/agents/pr-reviewer.md", content: "review agent", kind: "agents" },
        { path: ".github/workflows/claude.yml", content: "name: Claude", kind: "workflow" },
      ],
    });
    apiFetch.mockResolvedValue(
      new Response("zip-bytes", {
        status: 200,
        headers: {
          "content-disposition": 'attachment; filename="saas-pr-reviewer-claude.zip"',
          "content-type": "application/zip",
        },
      }),
    );
    Object.defineProperty(globalThis.navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    vi.stubGlobal("URL", {
      ...globalThis.URL,
      createObjectURL: vi.fn(() => "blob:preview"),
      revokeObjectURL: vi.fn(),
    });
  });

  test("submits the selected pack type and renders grouped preview output", async () => {
    render(<AgentPacksPage />);

    fireEvent.click(screen.getByRole("button", { name: /PR Reviewer/i }));
    fireEvent.change(screen.getByLabelText("What should Claude do?"), {
      target: { value: "Review pull requests for secret leaks and missing tests." },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate claude pack/i }));

    await waitFor(() => expect(apiJson).toHaveBeenCalledTimes(1));
    const [path, options] = apiJson.mock.calls[0];
    expect(path).toBe("/agent-packs/claude");
    expect(JSON.parse(options.body).pack_type).toBe("pr-reviewer");

    expect(await screen.findByText("Pack Preview")).toBeTruthy();
    expect(screen.getByRole("button", { name: "CLAUDE.md" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "agents" })).toBeTruthy();
  });

  test("downloads the generated pack through the Claude download route", async () => {
    const clickSpy = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", {
          configurable: true,
          value: clickSpy,
        });
      }
      return element;
    });

    render(<AgentPacksPage />);

    fireEvent.change(screen.getByLabelText("What should Claude do?"), {
      target: { value: "Create a full project pack." },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate claude pack/i }));

    await screen.findByText("Pack Preview");
    fireEvent.click(screen.getByRole("button", { name: /download pack/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const [path, options] = apiFetch.mock.calls[0];
    expect(path).toBe("/agent-packs/claude/download");
    expect(JSON.parse(options.body).goal).toBe("Create a full project pack.");
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });
});
