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

  test("requests the Claude project pack export", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("button", { name: "Claude Project Pack" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const [, options] = apiFetch.mock.calls.at(-1);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body).format).toBe("claude-project-pack");
  });

  test("requests the TypeScript Claude Agent SDK export when TypeScript tab is selected", async () => {
    render(<ExportPanel systemPrompt={"# Agent\n\n## Role\nTest"} isMultiAgent={false} />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.click(screen.getByRole("button", { name: "TypeScript" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const [, options] = apiFetch.mock.calls.at(-1);
    expect(JSON.parse(options.body).format).toBe("claude-agent-sdk-ts");
  });
});
