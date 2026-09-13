import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearProjectsStorage,
  PROJECTS_STORAGE_KEY,
  PROJECTS_STORAGE_VERSION,
  type ProjectBrief,
} from "../../lib/projects";
import { useProjects } from "./useProjects";

function makeProject(id: string, overrides: Partial<ProjectBrief> = {}): ProjectBrief {
  return {
    id,
    name: id[0]?.toUpperCase() + id.slice(1),
    projectType: "SaaS",
    stack: "Next.js + FastAPI",
    goal: `Build ${id}.`,
    rules: "Keep the brief focused.",
    ...overrides,
  };
}

function writeStoredProjects(projects: ProjectBrief[]): void {
  window.localStorage.setItem(
    PROJECTS_STORAGE_KEY,
    JSON.stringify({ version: PROJECTS_STORAGE_VERSION, projects }),
  );
}

function readStoredProjects(): ProjectBrief[] {
  const raw = window.localStorage.getItem(PROJECTS_STORAGE_KEY);
  if (!raw) return [];
  return (JSON.parse(raw) as { projects: ProjectBrief[] }).projects;
}

function dispatchCrossTabUpdate(): void {
  window.dispatchEvent(
    new StorageEvent("storage", {
      key: PROJECTS_STORAGE_KEY,
      newValue: window.localStorage.getItem(PROJECTS_STORAGE_KEY),
      storageArea: window.localStorage,
    }),
  );
}

async function waitForReady(result: { current: { ready: boolean } }): Promise<void> {
  await waitFor(() => expect(result.current.ready).toBe(true));
}

describe("useProjects", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("hydrates saved projects through the external store subscription", async () => {
    const saved = makeProject("saved");
    writeStoredProjects([saved]);

    const { result } = renderHook(() => useProjects());

    await waitFor(() => expect(result.current.projects).toEqual([saved]));
    expect(result.current.ready).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("notifies two hook instances when one instance saves a project", async () => {
    const saved = makeProject("saved");
    const first = renderHook(() => useProjects());
    const second = renderHook(() => useProjects());

    await waitForReady(first.result);
    await waitForReady(second.result);

    act(() => {
      expect(first.result.current.saveProject(saved)).toBe(true);
    });

    await waitFor(() => {
      expect(first.result.current.projects).toEqual([saved]);
      expect(second.result.current.projects).toEqual([saved]);
    });
  });

  it("merges a cross-tab update before saving another project", async () => {
    const firstProject = makeProject("first");
    const secondProject = makeProject("second");
    const thirdProject = makeProject("third");
    const { result } = renderHook(() => useProjects());

    await waitForReady(result);

    act(() => {
      expect(result.current.saveProject(firstProject)).toBe(true);
    });
    await waitFor(() => expect(result.current.projects).toEqual([firstProject]));

    // Another tab adds a project based on the list it read, then emits the
    // browser storage event that this hook subscribes to.
    writeStoredProjects([secondProject, firstProject]);
    act(dispatchCrossTabUpdate);
    await waitFor(() => expect(result.current.projects).toEqual([secondProject, firstProject]));

    act(() => {
      expect(result.current.saveProject(thirdProject)).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.projects).toEqual([thirdProject, secondProject, firstProject]);
    });
    expect(readStoredProjects()).toEqual([thirdProject, secondProject, firstProject]);
  });

  it("fails closed on corrupt storage without changing the stored bytes", async () => {
    const corruptPayload = '{"version":1,"projects":[';
    window.localStorage.setItem(PROJECTS_STORAGE_KEY, corruptPayload);
    const { result } = renderHook(() => useProjects());

    await waitFor(() => expect(result.current.error).toMatch(/could not be read/i));
    const bytesBeforeMutation = window.localStorage.getItem(PROJECTS_STORAGE_KEY);

    act(() => {
      expect(result.current.saveProject(makeProject("blocked"))).toBe(false);
    });

    expect(window.localStorage.getItem(PROJECTS_STORAGE_KEY)).toBe(bytesBeforeMutation);
    expect(result.current.projects).toEqual([]);
  });

  it("keeps the current list when local storage rejects a save", async () => {
    const saved = makeProject("saved");
    const rejected = makeProject("rejected");
    const { result } = renderHook(() => useProjects());

    await waitForReady(result);
    act(() => {
      expect(result.current.saveProject(saved)).toBe(true);
    });
    await waitFor(() => expect(result.current.projects).toEqual([saved]));
    const bytesBeforeMutation = window.localStorage.getItem(PROJECTS_STORAGE_KEY);

    const setItemSpy = vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new DOMException("Quota exceeded", "QuotaExceededError");
    });

    act(() => {
      expect(result.current.saveProject(rejected)).toBe(false);
    });
    setItemSpy.mockRestore();

    expect(result.current.projects).toEqual([saved]);
    expect(result.current.error).toMatch(/could not be saved/i);
    expect(window.localStorage.getItem(PROJECTS_STORAGE_KEY)).toBe(bytesBeforeMutation);
  });

  it("recovers from corrupt storage after an explicit clear", async () => {
    window.localStorage.setItem(PROJECTS_STORAGE_KEY, "not-json");
    const { result } = renderHook(() => useProjects());

    await waitFor(() => expect(result.current.error).toMatch(/could not be read/i));

    let clearResult: ReturnType<typeof clearProjectsStorage> | undefined;
    act(() => {
      clearResult = clearProjectsStorage();
    });

    expect(clearResult?.ok).toBe(true);
    await waitFor(() => {
      expect(result.current.projects).toEqual([]);
      expect(result.current.error).toBeNull();
    });

    const recovered = makeProject("recovered");
    act(() => {
      expect(result.current.saveProject(recovered)).toBe(true);
    });

    await waitFor(() => expect(result.current.projects).toEqual([recovered]));
    expect(readStoredProjects()).toEqual([recovered]);
    expect(window.localStorage.getItem(PROJECTS_STORAGE_KEY)).toContain(
      `"version":${PROJECTS_STORAGE_VERSION}`,
    );
  });
});
