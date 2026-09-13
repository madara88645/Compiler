import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgenticCodingProjectsPage from "./page";
import { PROJECTS_STORAGE_KEY } from "../../lib/projects";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("Agentic Coding project hub", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/agentic-coding");
  });

  it("creates and edits a brief without writing draft keystrokes, then links the saved id", async () => {
    render(<AgenticCodingProjectsPage />);

    expect(await screen.findByText("No project briefs yet.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "Signal board" } });
    fireEvent.change(screen.getByLabelText("Project type"), { target: { value: "Web app" } });
    fireEvent.change(screen.getByLabelText("Stack"), { target: { value: "Next.js + TypeScript" } });
    fireEvent.change(screen.getByLabelText("Goal"), { target: { value: "Make signals easy to explore." } });
    fireEvent.change(screen.getByLabelText("Rules"), { target: { value: "Keep the release easy to run locally." } });

    // Drafts remain page-local until the explicit save action.
    expect(window.localStorage.getItem(PROJECTS_STORAGE_KEY)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Save project" }));

    const projectHeading = await screen.findByRole("heading", { name: "Signal board" });
    const card = projectHeading.closest("article");
    expect(card).not.toBeNull();
    expect(within(card!).getByText("Next.js + TypeScript")).toBeInTheDocument();

    const createAgent = within(card!).getByRole("link", { name: /create agent/i });
    const createSkill = within(card!).getByRole("link", { name: /create skill\/tool/i });
    const exportPack = within(card!).getByRole("link", { name: /export pack/i });
    const agentProjectId = new URL(createAgent.getAttribute("href")!, "https://compiler.test").searchParams.get("project");

    expect(agentProjectId).toMatch(/^project-/);
    expect(createSkill).toHaveAttribute("href", `/agentic-coding/skills?project=${agentProjectId}`);
    expect(exportPack).toHaveAttribute("href", `/agentic-coding/projects/export?project=${agentProjectId}`);

    fireEvent.click(within(card!).getByRole("button", { name: "Edit brief" }));
    expect(screen.getByRole("heading", { name: "Edit project" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Goal"), { target: { value: "Make signals searchable and easy to explore." } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.getByText("Make signals searchable and easy to explore.")).toBeInTheDocument());
    expect(JSON.parse(window.localStorage.getItem(PROJECTS_STORAGE_KEY)!)).toMatchObject({
      version: 1,
      projects: [
        expect.objectContaining({
          id: agentProjectId,
          goal: "Make signals searchable and easy to explore.",
        }),
      ],
    });
  });

  it("requires an inline delete confirmation and surfaces corrupt local data", async () => {
    window.localStorage.setItem(PROJECTS_STORAGE_KEY, "{not-json");

    render(<AgenticCodingProjectsPage />);

    const storageAlert = await screen.findByRole("alert");
    expect(storageAlert).toHaveTextContent(/could not be read/i);
    expect(screen.getByRole("button", { name: "Reset local data" })).toBeInTheDocument();

    // A corrupted payload cannot be overwritten by a casual save; the reset
    // control is the explicit recovery path.
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "Recovery brief" } });
    fireEvent.click(screen.getByRole("button", { name: "Save project" }));
    expect(window.localStorage.getItem(PROJECTS_STORAGE_KEY)).toBe("{not-json");
  });

  it("keeps a dirty draft visible until the user explicitly discards it", async () => {
    render(<AgenticCodingProjectsPage />);
    await screen.findByText("No project briefs yet.");

    const name = screen.getByLabelText("Project name");
    fireEvent.change(name, { target: { value: "Unfinished brief" } });
    fireEvent.click(screen.getByRole("button", { name: "New project" }));

    expect(screen.getByRole("alertdialog", { name: "Unsaved project draft" })).toBeInTheDocument();
    expect(name).toHaveValue("Unfinished brief");

    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(name).toHaveValue("Unfinished brief");

    fireEvent.click(screen.getByRole("button", { name: "New project" }));
    fireEvent.click(screen.getByRole("button", { name: "Discard and continue" }));
    await waitFor(() => expect(screen.getByLabelText("Project name")).toHaveValue(""));
  });

  it("resets corrupt local data without discarding the current draft", async () => {
    window.localStorage.setItem(PROJECTS_STORAGE_KEY, "{not-json");
    render(<AgenticCodingProjectsPage />);

    await screen.findByRole("alert");
    const name = screen.getByLabelText("Project name");
    fireEvent.change(name, { target: { value: "Recovery brief" } });
    fireEvent.click(screen.getByRole("button", { name: "Reset local data" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm reset" }));

    await waitFor(() => expect(window.localStorage.getItem(PROJECTS_STORAGE_KEY)).toBeNull());
    expect(screen.getByLabelText("Project name")).toHaveValue("Recovery brief");
    expect(screen.getByText(/current draft stays on this page/i)).toBeInTheDocument();
  });

  it("requires an explicit overwrite before saving over a brief changed in another tab", async () => {
    const savedProject = {
      id: "shared-brief",
      name: "Shared brief",
      projectType: "Web app",
      stack: "Next.js",
      goal: "Original goal",
      rules: "Original rules",
    };
    window.localStorage.setItem(
      PROJECTS_STORAGE_KEY,
      JSON.stringify({ version: 1, projects: [savedProject] }),
    );

    render(<AgenticCodingProjectsPage />);
    const cardHeading = await screen.findByRole("heading", { name: "Shared brief" });
    fireEvent.click(within(cardHeading.closest("article")!).getByRole("button", { name: "Edit brief" }));
    fireEvent.change(screen.getByLabelText("Goal"), { target: { value: "Local draft goal" } });

    const remoteProject = { ...savedProject, goal: "Remote goal" };
    window.localStorage.setItem(
      PROJECTS_STORAGE_KEY,
      JSON.stringify({ version: 1, projects: [remoteProject] }),
    );
    window.dispatchEvent(new StorageEvent("storage", { key: PROJECTS_STORAGE_KEY }));

    expect(await screen.findByText(/changed in another tab/i)).toBeInTheDocument();
    const saveChanges = screen.getByRole("button", { name: "Save changes" });
    expect(saveChanges).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Overwrite latest brief" }));
    expect(saveChanges).toBeEnabled();
    fireEvent.click(saveChanges);

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem(PROJECTS_STORAGE_KEY)!)).toMatchObject({
        projects: [expect.objectContaining({ id: "shared-brief", goal: "Local draft goal" })],
      });
    });
  });
});
