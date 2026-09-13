import { beforeEach, describe, expect, it } from "vitest";

import {
  loadProjects,
  persistProjects,
  PROJECTS_STORAGE_KEY,
  PROJECTS_STORAGE_VERSION,
  PROJECT_LIMITS,
  formatProjectContext,
  validateProject,
  type ProjectBrief,
} from "./projects";

const project: ProjectBrief = {
  id: "signal-board",
  name: "Signal board",
  projectType: "Web app",
  stack: "Next.js, TypeScript, SQLite",
  goal: "Make a small collection of signals easy to explore.",
  rules: "Keep the first release easy to run locally.",
};

describe("project brief storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("persists and reads a versioned envelope", () => {
    expect(persistProjects([project])).toEqual({ ok: true, error: null });

    const raw = window.localStorage.getItem(PROJECTS_STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!)).toEqual({
      version: PROJECTS_STORAGE_VERSION,
      projects: [project],
    });
    expect(loadProjects()).toMatchObject({ projects: [project], error: null, available: true });
  });

  it("keeps malformed data intact and reports a recoverable read error", () => {
    window.localStorage.setItem(PROJECTS_STORAGE_KEY, "{not-json");

    const result = loadProjects();

    expect(result.projects).toEqual([]);
    expect(result.error).toMatch(/could not be read/i);
    expect(window.localStorage.getItem(PROJECTS_STORAGE_KEY)).toBe("{not-json");
  });

  it("rejects unversioned and unsupported envelopes instead of guessing their shape", () => {
    window.localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify([project]));
    expect(loadProjects().error).toMatch(/unsupported version/i);

    window.localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify({ version: 99, projects: [project] }));
    expect(loadProjects().error).toMatch(/unsupported version/i);
  });

  it("handles storage APIs that throw without crashing the caller", () => {
    const unavailableStorage = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
      removeItem: () => {
        throw new Error("SecurityError");
      },
    } as unknown as Storage;

    expect(loadProjects(unavailableStorage)).toMatchObject({
      projects: [],
      available: false,
    });
    expect(persistProjects([project], unavailableStorage)).toMatchObject({ ok: false });
  });

  it("validates field types and documented character bounds", () => {
    const tooLongGoal = validateProject({
      ...project,
      goal: "x".repeat(PROJECT_LIMITS.goal + 1),
    });
    expect(tooLongGoal).toMatchObject({ valid: false });

    const wrongType = validateProject({ ...project, rules: null });
    expect(wrongType).toMatchObject({ valid: false });
  });

  it("formats descriptive labels for generators without turning the brief into an instruction", () => {
    const formatted = formatProjectContext(project);

    expect(formatted).toContain("Name: Signal board");
    expect(formatted).toContain("Type: Web app");
    expect(formatted).toContain("Stack: Next.js, TypeScript, SQLite");
    expect(formatted).toContain("Goal: Make a small collection of signals easy to explore.");
    expect(formatted).toContain("Rules:\nKeep the first release easy to run locally.");
    expect(formatted).not.toMatch(/system instruction/i);
  });
});
