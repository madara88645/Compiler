import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Enable the repo-context UI before the page module is evaluated. The flag is read
// at module load (`process.env.NEXT_PUBLIC_REPO_CONTEXT_ENABLED === "true"`), so we
// have to set it via vi.hoisted to run before the import below.
vi.hoisted(() => {
  process.env.NEXT_PUBLIC_REPO_CONTEXT_ENABLED = "true";
});

import SkillsGeneratorPage from "./page";
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
const plainSkillResponse = {
  skill_definition: "## Plain Skill",
  example_code_requested: false,
  example_code_present: false,
  example_code_warning: null,
};

describe("Skills Generator page", () => {
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

  it("analyzes a GitHub repo and includes repo_context in the skill request", async () => {
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
        skill_definition: "# Repo-aware Skill",
        example_code_requested: false,
        example_code_present: false,
        example_code_warning: null,
      });

    render(<SkillsGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Skill Description"), {
      target: { value: "Generate a skill for this repo." },
    });
    fireEvent.change(screen.getByLabelText("GitHub Repo URL"), {
      target: { value: "https://github.com/openai/openai-python" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Analyze Repo" }));

    await screen.findByText("openai/openai-python");
    expect(screen.getByText("Python SDK repo with a compact README and clear manifest signals.")).toBeTruthy();

    fireEvent.click(screen.getAllByRole("button", { name: /Generate Skill/i })[0]!);

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(apiJsonMock.mock.calls[1]?.[1]?.body))).toEqual({
      description: "Generate a skill for this repo.",
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

  it("requires re-analysis after the repo URL changes", async () => {
    apiJsonMock
      .mockResolvedValueOnce({
        normalized_repo_url: "https://github.com/openai/openai-python",
        repo_full_name: "openai/openai-python",
        default_branch: "main",
        summary: "Python SDK repo with a compact README and clear manifest signals.",
        highlights: ["Python package"],
        files_used: ["README.md"],
        detected_stack: ["Python"],
      })
      .mockResolvedValueOnce(plainSkillResponse);

    render(<SkillsGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Skill Description"), {
      target: { value: "Generate a skill for this repo." },
    });
    fireEvent.change(screen.getByLabelText("GitHub Repo URL"), {
      target: { value: "https://github.com/openai/openai-python" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze Repo" }));

    await screen.findByText("openai/openai-python");

    fireEvent.change(screen.getByLabelText("GitHub Repo URL"), {
      target: { value: "https://github.com/vercel/next.js" },
    });

    expect(screen.getByText("Repo URL changed. Re-analyze to attach fresh repo context.")).toBeTruthy();

    fireEvent.click(screen.getAllByRole("button", { name: /Generate Skill/i })[0]!);

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(apiJsonMock.mock.calls[1]?.[1]?.body))).toEqual({
      description: "Generate a skill for this repo.",
      include_example_code: false,
    });
  });

  it("keeps the description textarea at a usable desktop height", () => {
    render(<SkillsGeneratorPage />);

    const textarea = screen.getByLabelText("Skill Description");
    const classes = textarea.getAttribute("class") || "";

    expect(classes).toContain("md:min-h-[220px]");
    expect(classes).not.toContain("md:min-h-0");
  });

  it("starts as a centered single-form view and only opens the output pane once generation begins", async () => {
    apiJsonMock.mockImplementationOnce(
      () =>
        new Promise(() => {
          // Keep the request pending so the loading-state split layout stays visible.
        }),
    );

    render(<SkillsGeneratorPage />);

    const textarea = screen.getByLabelText("Skill Description");
    const formPane = textarea.closest("div")?.parentElement;

    expect(formPane?.className).toContain("max-w-2xl");
    expect(formPane?.className).not.toContain("md:w-[38%]");
    expect(screen.getAllByRole("button", { name: /Generate Skill/i })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "or try an example" })).toBeTruthy();
    expect(screen.queryByText("Forging skill definition...")).toBeNull();

    fireEvent.change(textarea, {
      target: { value: "Summarize pages into three bullets." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Generate Skill/i }));

    expect(await screen.findByText("Forging skill definition...")).toBeTruthy();
    expect(formPane?.className).toContain("md:w-[38%]");
    expect(formPane?.className).not.toContain("max-w-2xl");
    expect(screen.queryByRole("button", { name: "or try an example" })).toBeNull();
  });

  it("shows a retryable error in the output panel when generation fails", async () => {
    apiJsonMock.mockRejectedValueOnce(new Error("The service is temporarily unavailable."));

    render(<SkillsGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Skill Description"), {
      target: { value: "Parse JSON and validate schemas." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Generate Skill/i })[0]!);

    expect(await screen.findByText("Skill generation failed")).toBeTruthy();
    expect(screen.getByText("The service is temporarily unavailable.")).toBeTruthy();

    apiJsonMock.mockResolvedValueOnce({
      skill_definition: "## json-validator",
      example_code_requested: false,
      example_code_present: false,
      example_code_warning: null,
    });
    fireEvent.click(screen.getByRole("button", { name: "Retry generation" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "json-validator" })).toBeTruthy());
    expect(apiJsonMock).toHaveBeenCalledTimes(2);
  });

  it("keeps example-code enabled after generation and preserves payload values", async () => {
    apiJsonMock.mockResolvedValueOnce({
      skill_definition: "## example-skill",
      example_code_requested: true,
      example_code_present: true,
      example_code_warning: null,
    });

    render(<SkillsGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Skill Description"), {
      target: { value: "Generate a code-heavy skill." },
    });

    fireEvent.click(screen.getByText("Example Code?"));
    fireEvent.click(screen.getAllByRole("button", { name: /Generate Skill/i })[0]!);

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String(apiJsonMock.mock.calls[0]?.[1]?.body))).toEqual({
      description: "Generate a code-heavy skill.",
      include_example_code: true,
    });
    expect(screen.getByRole("switch", { name: "Include Example Code toggle" }).getAttribute("aria-checked")).toBe(
      "true",
    );
    expect(screen.getByText("With Example Code")).toBeTruthy();
  });

  it("shows a warning when example code is requested but missing", async () => {
    apiJsonMock.mockResolvedValueOnce({
      skill_definition: "## text-only-skill",
      example_code_requested: true,
      example_code_present: false,
      example_code_warning:
        "Example Code was requested, but the generator returned a text-only skill definition. You can still use this result or try generating again.",
    });

    render(<SkillsGeneratorPage />);

    fireEvent.change(screen.getByLabelText("Skill Description"), {
      target: { value: "Generate a code-heavy skill." },
    });

    fireEvent.click(screen.getByText("Example Code?"));
    fireEvent.click(screen.getAllByRole("button", { name: /Generate Skill/i })[0]!);

    expect(
      await screen.findByText(
        "Example Code was requested, but the generator returned a text-only skill definition. You can still use this result or try generating again.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Example Code Missing")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "text-only-skill" })).toBeTruthy();
  });

  it("supports keyboard activation for the switch row", () => {
    render(<SkillsGeneratorPage />);

    const exampleCodeSwitch = screen.getByRole("switch", { name: "Include Example Code toggle" });
    expect(exampleCodeSwitch.tagName).toBe("BUTTON");
    expect(exampleCodeSwitch.getAttribute("type")).toBe("button");
    expect(exampleCodeSwitch.getAttribute("aria-checked")).toBe("false");

    exampleCodeSwitch.focus();
    expect(document.activeElement).toBe(exampleCodeSwitch);

    fireEvent.click(exampleCodeSwitch);
    expect(exampleCodeSwitch.getAttribute("aria-checked")).toBe("true");
  });
});
