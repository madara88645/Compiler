import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Enable the repo-context UI before the page module is evaluated. The flag is read
// at module load (`process.env.NEXT_PUBLIC_REPO_CONTEXT_ENABLED === "true"`), so we
// have to set it via vi.hoisted to run before the import below.
vi.hoisted(() => {
  process.env.NEXT_PUBLIC_REPO_CONTEXT_ENABLED = "true";
});

import AgentGeneratorPage from "./page";
import { apiJson } from "@/config";

vi.mock("@/config", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/config")>();
  return {
    ...actual,
    apiJson: vi.fn(),
    buildGeneratorApiHeaders: (headers: HeadersInit = {}) => headers,
  };
});

vi.mock("../components/InfoButton", () => ({
  default: ({ title }: { title: string }) => <button type="button">{title}</button>,
}));

vi.mock("../components/ContextManager", () => ({
  default: () => <div data-testid="context-manager" />,
}));

vi.mock("./components/ExportPanel", () => ({
  default: () => null,
}));

vi.mock("../lib/showError", () => ({
  showError: vi.fn(),
}));

const apiJsonMock = vi.mocked(apiJson);

describe("Agent Generator page", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_REPO_CONTEXT_ENABLED", "true");
  });

  beforeEach(() => {
    apiJsonMock.mockReset();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("analyzes a GitHub repo and includes repo_context in the generate request", async () => {
    apiJsonMock
      .mockResolvedValueOnce({
        normalized_repo_url: "https://github.com/openai/openai-python",
        repo_full_name: "openai/openai-python",
        default_branch: "main",
        summary: "Python SDK repo with a compact README and clear manifest signals.",
        highlights: ["Python package", "README present"],
        files_used: ["README.md", "pyproject.toml"],
        detected_stack: ["Python", "httpx"],
      })
      .mockResolvedValueOnce({
        system_prompt: "# Repo-aware Agent",
      });

    render(<AgentGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Agent Description"), {
      target: { value: "Review this repo and generate an agent." },
    });
    fireEvent.change(screen.getByLabelText("GitHub Repo URL"), {
      target: { value: "https://github.com/openai/openai-python" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Analyze Repo" }));

    await screen.findByText("openai/openai-python");
    expect(screen.getByText("Python SDK repo with a compact README and clear manifest signals.")).toBeTruthy();

    fireEvent.click(screen.getAllByTitle("Generate Agent")[0]!);

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(2));

    expect(apiJsonMock.mock.calls[0]?.[0]).toBe("/repo-context/github");
    expect(JSON.parse(String(apiJsonMock.mock.calls[0]?.[1]?.body))).toEqual({
      repo_url: "https://github.com/openai/openai-python",
    });

    expect(apiJsonMock.mock.calls[1]?.[0]).toBe("/agent-generator/generate");
    expect(JSON.parse(String(apiJsonMock.mock.calls[1]?.[1]?.body))).toEqual({
      description: "Review this repo and generate an agent.",
      multi_agent: false,
      include_example_code: false,
      repo_context: {
        normalized_repo_url: "https://github.com/openai/openai-python",
        repo_full_name: "openai/openai-python",
        default_branch: "main",
        summary: "Python SDK repo with a compact README and clear manifest signals.",
        highlights: ["Python package", "README present"],
        files_used: ["README.md", "pyproject.toml"],
        detected_stack: ["Python", "httpx"],
      },
    });
  });

  it("shows a warning when repo analysis fails but still generates without repo context", async () => {
    apiJsonMock
      .mockRejectedValueOnce(new Error("Repository analysis failed"))
      .mockResolvedValueOnce({
        system_prompt: "# Plain Agent",
      });

    render(<AgentGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Agent Description"), {
      target: { value: "Build a safe agent." },
    });
    fireEvent.change(screen.getByLabelText("GitHub Repo URL"), {
      target: { value: "https://github.com/openai/openai-python" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Analyze Repo" }));
    expect(await screen.findByText("Repository analysis failed")).toBeTruthy();

    fireEvent.click(screen.getAllByTitle("Generate Agent")[0]!);

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(apiJsonMock.mock.calls[1]?.[1]?.body))).toEqual({
      description: "Build a safe agent.",
      multi_agent: false,
      include_example_code: false,
    });
  });

  it("keeps the description textarea at a usable desktop height", () => {
    render(<AgentGeneratorPage />);

    const textarea = screen.getByLabelText("Agent Description");
    const classes = textarea.getAttribute("class") || "";

    expect(classes).toContain("md:min-h-[220px]");
    expect(classes).not.toContain("md:min-h-0");
  });

  it("shows a retryable error in the output panel when generation fails", async () => {
    apiJsonMock.mockRejectedValueOnce(new Error("The service is temporarily unavailable."));

    render(<AgentGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Agent Description"), {
      target: { value: "Build a code review agent." },
    });
    fireEvent.click(screen.getAllByTitle("Generate Agent")[0]!);

    expect(await screen.findByText("Agent generation failed")).toBeTruthy();
    expect(screen.getByText("The service is temporarily unavailable.")).toBeTruthy();

    apiJsonMock.mockResolvedValueOnce({ system_prompt: "# Reviewer" });
    fireEvent.click(screen.getByRole("button", { name: "Retry generation" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Reviewer" })).toBeTruthy());
    expect(apiJsonMock).toHaveBeenCalledTimes(2);
  });

  it("toggles both switches from label clicks and preserves payload values", async () => {
    apiJsonMock.mockResolvedValueOnce({ system_prompt: "# Swarm Agent" });

    render(<AgentGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Agent Description"), {
      target: { value: "Build a collaborative agent." },
    });

    fireEvent.click(screen.getByText("Multi-Agent Swarm"));
    fireEvent.click(screen.getByText("Example Code?"));
    fireEvent.click(screen.getAllByTitle("Generate Agent")[0]!);

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String(apiJsonMock.mock.calls[0]?.[1]?.body))).toEqual({
      description: "Build a collaborative agent.",
      multi_agent: true,
      include_example_code: true,
    });
  });

  it("supports keyboard activation for the switch row", () => {
    render(<AgentGeneratorPage />);

    const multiAgentSwitch = screen.getByRole("switch", { name: "Multi-Agent Swarm toggle" });
    expect(multiAgentSwitch.tagName).toBe("BUTTON");
    expect(multiAgentSwitch.getAttribute("type")).toBe("button");
    expect(multiAgentSwitch.getAttribute("aria-checked")).toBe("false");

    multiAgentSwitch.focus();
    expect(document.activeElement).toBe(multiAgentSwitch);

    fireEvent.click(multiAgentSwitch);
    expect(multiAgentSwitch.getAttribute("aria-checked")).toBe("true");
  });
});
