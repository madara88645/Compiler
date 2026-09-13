import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentGeneratorPage from "../agent-generator/page";
import AgentPacksPage from "../agent-packs/page";
import SkillsGeneratorPage from "../skills-generator/page";
import type { ProjectBrief } from "@/lib/projects";

const { apiJsonMock, useProjectsMock } = vi.hoisted(() => ({
  apiJsonMock: vi.fn(),
  useProjectsMock: vi.fn(),
}));

vi.mock("@/config", () => ({
  apiJson: apiJsonMock,
  buildGeneratorApiHeaders: (headers: HeadersInit = {}) => headers,
  describeRequestError: (error: unknown) => (error instanceof Error ? error.message : "Connection failed."),
}));

vi.mock("../hooks/useProjects", () => ({
  useProjects: useProjectsMock,
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("../components/InfoButton", () => ({
  default: ({ title }: { title: string }) => <button type="button">{title}</button>,
}));

vi.mock("../components/ContextManager", () => ({
  default: () => <div data-testid="context-manager" />,
}));

vi.mock("../hooks/useContextManager", () => ({
  useContextManager: () => ({
    contextAttached: false,
    contextSource: "none",
    indexStats: null,
    attachContext: vi.fn(),
    detachContext: vi.fn(),
  }),
}));

vi.mock("../lib/showError", () => ({
  showError: vi.fn(),
}));

vi.mock("../agent-generator/components/ExportPanel", () => ({
  default: () => null,
}));

vi.mock("../skills-generator/components/ExportPanel", () => ({
  default: () => null,
}));

vi.mock("../agent-packs/components/FileTree", () => ({
  default: () => null,
}));

vi.mock("../agent-packs/components/InstallChecklist", () => ({
  default: () => null,
}));

vi.mock("../agent-packs/installChecklist", () => ({
  buildInstallChecklist: () => [],
}));

const project: ProjectBrief = {
  id: "alpha",
  name: "Alpha",
  projectType: "SaaS",
  stack: "Next.js + FastAPI",
  goal: "Ship a useful project brief flow.",
  rules: "Keep the task reversible.",
};

function projectsState() {
  return {
    projects: [project],
    ready: true,
    error: null,
    saveProject: vi.fn(),
    deleteProject: vi.fn(),
  };
}

function attachProject() {
  fireEvent.change(screen.getByRole("combobox", { name: "Project context" }), {
    target: { value: project.id },
  });
  fireEvent.click(screen.getByRole("button", { name: "Attach project context" }));
  expect(screen.getByText(/Attached: Alpha\./)).toBeInTheDocument();
}

describe("agentic coding generator project context", () => {
  beforeEach(() => {
    apiJsonMock.mockReset();
    useProjectsMock.mockReturnValue(projectsState());
    vi.stubEnv("NEXT_PUBLIC_REPO_CONTEXT_ENABLED", "false");
    window.history.replaceState({}, "", "/agentic-coding");
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
    window.history.replaceState({}, "", "/agentic-coding");
  });

  it("keeps the agent task unchanged until a project is explicitly attached, then sends context to the same endpoint", async () => {
    apiJsonMock.mockResolvedValueOnce({
      system_prompt: "# Generated Agent",
      example_code_requested: false,
      example_code_present: false,
      example_code_warning: null,
    });

    const firstRender = render(<AgentGeneratorPage />);
    const description = "Build a support agent.";
    fireEvent.change(screen.getByLabelText("Agent Description"), { target: { value: description } });
    fireEvent.click(screen.getByRole("button", { name: /Generate Agent/i }));
    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String(apiJsonMock.mock.calls[0]?.[1]?.body)).description).toBe(description);
    firstRender.unmount();

    apiJsonMock.mockReset();
    apiJsonMock.mockResolvedValueOnce({
      system_prompt: "# Contextual Agent",
      example_code_requested: false,
      example_code_present: false,
      example_code_warning: null,
    });

    render(<AgentGeneratorPage />);
    fireEvent.change(screen.getByLabelText("Agent Description"), { target: { value: description } });
    attachProject();
    fireEvent.click(screen.getByRole("button", { name: /Generate Agent/i }));

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(1));
    const payload = JSON.parse(String(apiJsonMock.mock.calls[0]?.[1]?.body));
    expect(apiJsonMock.mock.calls[0]?.[0]).toBe("/agent-generator/generate");
    expect(payload.description).toContain(description);
    expect(payload.description).toContain("Project context (background for this task):");
    expect(payload.description).toContain("Name: Alpha");
    expect(payload.description).toContain("Stack: Next.js + FastAPI");
  });

  it("appends the attached project brief to the skill description at the existing endpoint", async () => {
    apiJsonMock.mockResolvedValueOnce({
      skill_definition: "# Generated Skill",
      example_code_requested: false,
      example_code_present: false,
      example_code_warning: null,
    });

    render(<SkillsGeneratorPage />);
    const description = "Create a JSON validation skill.";
    fireEvent.change(screen.getByLabelText("Skill Description"), { target: { value: description } });
    attachProject();
    fireEvent.click(screen.getByRole("button", { name: /Generate Skill/i }));

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(1));
    const [path, options] = apiJsonMock.mock.calls[0]!;
    const payload = JSON.parse(String(options.body));
    expect(path).toBe("/skills-generator/generate");
    expect(payload.description).toContain(description);
    expect(payload.description).toContain("Project context (background for this task):");
    expect(payload.description).toContain("Goal: Ship a useful project brief flow.");
  });

  it("appends the attached project brief to the pack goal at the existing endpoint", async () => {
    apiJsonMock.mockResolvedValueOnce({
      provider: "claude",
      pack_type: "project-pack",
      download_name: "alpha-project-pack",
      preview_order: ["claude_md"],
      files: [{ path: "CLAUDE.md", content: "# Generated Pack", kind: "claude_md" }],
    });

    render(<AgentPacksPage />);
    const goal = "Prepare a safe project pack.";
    fireEvent.change(screen.getByLabelText("What should Claude do?"), { target: { value: goal } });
    attachProject();
    fireEvent.click(screen.getAllByRole("button", { name: /Generate Claude Pack/i })[0]!);

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(1));
    const [path, options] = apiJsonMock.mock.calls[0]!;
    const payload = JSON.parse(String(options.body));
    expect(path).toBe("/agent-packs/claude");
    expect(payload.goal).toContain(goal);
    expect(payload.goal).toContain("Project context (background for this task):");
    expect(payload.goal).toContain("Rules:\nKeep the task reversible.");
  });

  it("uses attached pack metadata and restores manual values after detach", async () => {
    const pythonCliProject: ProjectBrief = {
      id: "python-cli",
      name: "Python CLI",
      projectType: "Python CLI",
      stack: "Python + Typer",
      goal: "Ship a reliable command-line tool.",
      rules: "Keep commands deterministic.",
    };
    useProjectsMock.mockReturnValue({
      projects: [pythonCliProject],
      ready: true,
      error: null,
      saveProject: vi.fn(),
      deleteProject: vi.fn(),
    });
    apiJsonMock.mockResolvedValueOnce({
      provider: "claude",
      pack_type: "project-pack",
      download_name: "python-cli-project-pack",
      preview_order: ["claude_md"],
      files: [{ path: "CLAUDE.md", content: "# Generated Pack", kind: "claude_md" }],
    });

    render(<AgentPacksPage />);
    const projectType = screen.getByLabelText("Project Type");
    const stack = screen.getByLabelText("Stack");
    fireEvent.change(projectType, { target: { value: "Personal Tool" } });
    fireEvent.change(stack, { target: { value: "Rust + Axum" } });
    fireEvent.change(screen.getByLabelText("What should Claude do?"), {
      target: { value: "Prepare a safe Python CLI project pack." },
    });

    fireEvent.change(screen.getByRole("combobox", { name: "Project context" }), {
      target: { value: pythonCliProject.id },
    });
    fireEvent.click(screen.getByRole("button", { name: "Attach project context" }));

    expect(projectType).toHaveValue("Python CLI");
    expect(stack).toHaveValue("Python + Typer");
    expect(projectType).toHaveAttribute("readonly");
    expect(stack).toHaveAttribute("readonly");

    fireEvent.click(screen.getAllByRole("button", { name: /Generate Claude Pack/i })[0]!);
    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(1));
    const payload = JSON.parse(String(apiJsonMock.mock.calls[0]?.[1]?.body));
    expect(payload.project_type).toBe("Python CLI");
    expect(payload.stack).toBe("Python + Typer");
    expect(payload.goal).toContain("Project context (background for this task):");

    fireEvent.click(screen.getByRole("button", { name: "Detach project" }));
    expect(projectType).toHaveValue("Personal Tool");
    expect(stack).toHaveValue("Rust + Axum");
    expect(projectType).not.toHaveAttribute("readonly");
    expect(stack).not.toHaveAttribute("readonly");
  });
});
