import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ProjectContextPicker, { withProjectContext } from "./ProjectContextPicker";
import { formatProjectContext, type ProjectBrief } from "@/lib/projects";

const { useProjectsMock } = vi.hoisted(() => ({
  useProjectsMock: vi.fn(),
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

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

function makeProject(overrides: Partial<ProjectBrief> = {}): ProjectBrief {
  return {
    id: "alpha",
    name: "Alpha",
    projectType: "SaaS",
    stack: "Next.js + FastAPI",
    goal: "Ship a useful project brief flow.",
    rules: "Keep the task reversible.",
    ...overrides,
  };
}

function projectsState(projects: ProjectBrief[] = [makeProject(), makeProject({ id: "beta", name: "Beta" })]) {
  return {
    projects,
    ready: true,
    error: null,
    saveProject: vi.fn(),
    deleteProject: vi.fn(),
  };
}

describe("ProjectContextPicker", () => {
  beforeEach(() => {
    useProjectsMock.mockReturnValue(projectsState());
    window.history.replaceState({}, "", "/agent-generator");
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/agent-generator");
  });

  it("preserves an unlinked description and appends a labeled linked brief", () => {
    const description = "Keep this task exactly as written.\nSecond line.";
    const project = makeProject();

    expect(withProjectContext(description, null)).toBe(description);
    expect(withProjectContext(description, project)).toBe(
      `${description}\n\nProject context (background for this task):\n${formatProjectContext(project)}`,
    );
  });

  it("preselects a query project without attaching it until the user clicks Attach", async () => {
    window.history.replaceState({}, "", "/agent-generator?project=alpha");
    const onChange = vi.fn();
    render(<ProjectContextPicker onChange={onChange} />);

    const select = screen.getByRole("combobox", { name: "Project context" });
    await waitFor(() => expect(select).toHaveValue("alpha"));
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(select, { target: { value: "beta" } });
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Attach project context" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith(makeProject({ id: "beta", name: "Beta" }));
  });

  it("updates preselection after a client-side URL change without attaching the project", async () => {
    const onChange = vi.fn();
    const view = render(<ProjectContextPicker onChange={onChange} />);
    const select = screen.getByRole("combobox", { name: "Project context" });

    expect(select).toHaveValue("");
    window.history.replaceState({}, "", "/agent-generator?project=alpha");
    view.rerender(<ProjectContextPicker onChange={onChange} />);

    await waitFor(() => expect(select).toHaveValue("alpha"));
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText("No project attached. This tool works on its own.")).toBeInTheDocument();
  });

  it("holds the attached snapshot while switching candidates and supports explicit detach", async () => {
    const alpha = makeProject();
    const beta = makeProject({ id: "beta", name: "Beta" });
    const onChange = vi.fn();
    const { rerender } = render(<ProjectContextPicker onChange={onChange} />);
    const select = screen.getByRole("combobox", { name: "Project context" });

    fireEvent.change(select, { target: { value: alpha.id } });
    fireEvent.click(screen.getByRole("button", { name: "Attach project context" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0]?.[0]).toEqual(alpha);
    expect(onChange.mock.calls[0]?.[0]).not.toBe(alpha);

    fireEvent.change(select, { target: { value: beta.id } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Attached: Alpha\./)).toBeInTheDocument();

    const changedAlpha = makeProject({ goal: "A changed saved goal." });
    useProjectsMock.mockReturnValue(projectsState([changedAlpha, beta]));
    rerender(<ProjectContextPicker onChange={onChange} />);

    expect(screen.getByText(/Attached: Alpha\./)).toBeInTheDocument();
    expect(screen.getByText(/saved project changed or was removed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Detach project" }));
    expect(onChange).toHaveBeenLastCalledWith(null);
    expect(screen.getByText("No project attached. This tool works on its own.")).toBeInTheDocument();
  });

  it("reports an unavailable query project and continues without attaching anything", async () => {
    window.history.replaceState({}, "", "/agent-generator?project=missing");
    const onChange = vi.fn();
    render(<ProjectContextPicker onChange={onChange} />);

    expect(await screen.findByText(/This project is unavailable in this browser/i)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Project context" })).toHaveValue("");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("rejects an oversized linked request but leaves an unlinked description untouched", () => {
    const project = makeProject({ rules: "x".repeat(2500) });
    const longDescription = "x".repeat(8000);

    expect(withProjectContext(longDescription, null)).toBe(longDescription);
    expect(() => withProjectContext(longDescription, project)).toThrow(/8,000 characters/i);
  });
});
