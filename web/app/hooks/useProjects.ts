"use client";

import { useCallback, useSyncExternalStore } from "react";

import {
  loadProjects,
  persistProjects,
  PROJECTS_STORAGE_EVENT,
  PROJECTS_STORAGE_KEY,
  validateProject,
  type ProjectBrief,
  type ProjectStorageReadResult,
} from "../../lib/projects";

export type ProjectsState = {
  projects: ProjectBrief[];
  ready: boolean;
  error: string | null;
  saveProject: (project: ProjectBrief) => boolean;
  deleteProject: (id: string) => boolean;
};

type ProjectStoreSnapshot = {
  projects: ProjectBrief[];
  ready: boolean;
  error: string | null;
  writesBlocked: boolean;
};

const EMPTY_SNAPSHOT: ProjectStoreSnapshot = {
  projects: [],
  ready: false,
  error: null,
  writesBlocked: false,
};
const LOADING_MESSAGE = "Projects are still loading. Try saving again in a moment.";

// localStorage is an external browser store. useSyncExternalStore keeps the
// server snapshot empty for hydration, then subscribes to both browser storage
// events and a same-tab event emitted by the storage helper.
let snapshot = EMPTY_SNAPSHOT;
const listeners = new Set<() => void>();
let eventsAttached = false;

function snapshotFromStorage(stored: ProjectStorageReadResult): ProjectStoreSnapshot {
  return {
    projects: stored.projects,
    ready: true,
    error: stored.error,
    // Any read error means the hook must fail closed. A malformed payload is
    // never silently replaced by a later save.
    writesBlocked: Boolean(stored.error),
  };
}

function snapshotsEqual(left: ProjectStoreSnapshot, right: ProjectStoreSnapshot): boolean {
  return (
    left.projects === right.projects &&
    left.ready === right.ready &&
    left.error === right.error &&
    left.writesBlocked === right.writesBlocked
  );
}

function publish(next: ProjectStoreSnapshot): void {
  if (snapshotsEqual(snapshot, next)) {
    return;
  }

  snapshot = next;
  listeners.forEach((listener) => listener());
}

function refreshFromStorage(): ProjectStorageReadResult {
  const stored = loadProjects();
  publish(snapshotFromStorage(stored));
  return stored;
}

function handleStorageChange(event: Event): void {
  if (event.type === "storage") {
    const storageEvent = event as StorageEvent;
    if (storageEvent.key !== null && storageEvent.key !== PROJECTS_STORAGE_KEY) {
      return;
    }
  }
  refreshFromStorage();
}

function subscribe(listener: () => void): () => void {
  const firstSubscriber = listeners.size === 0;
  listeners.add(listener);

  if (typeof window !== "undefined") {
    if (firstSubscriber) {
      // Hydrate during subscription rather than in an effect. React will check
      // the snapshot again after subscribing, avoiding a cascading effect render.
      const stored = loadProjects();
      snapshot = snapshotFromStorage(stored);
    }

    if (!eventsAttached) {
      window.addEventListener("storage", handleStorageChange);
      window.addEventListener(PROJECTS_STORAGE_EVENT, handleStorageChange);
      eventsAttached = true;
    }
  }

  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && eventsAttached && typeof window !== "undefined") {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener(PROJECTS_STORAGE_EVENT, handleStorageChange);
      eventsAttached = false;
    }
  };
}

function getClientSnapshot(): ProjectStoreSnapshot {
  return snapshot;
}

function getServerSnapshot(): ProjectStoreSnapshot {
  return EMPTY_SNAPSHOT;
}

/**
 * Browser-only project brief state. Changes are explicit: typing in the hub
 * edits a page-local draft and only saveProject writes to localStorage.
 */
export function useProjects(): ProjectsState {
  const current = useSyncExternalStore(subscribe, getClientSnapshot, getServerSnapshot);

  const saveProject = useCallback(
    (project: ProjectBrief): boolean => {
      if (!current.ready) {
        publish({ ...snapshot, error: LOADING_MESSAGE });
        return false;
      }

      const validation = validateProject(project);
      if (!validation.valid) {
        publish({ ...snapshot, error: validation.error });
        return false;
      }

      // Another tab may have saved a brief since this hook rendered. Read the
      // latest valid snapshot before calculating the next list so this write
      // cannot erase that tab's work. Read errors fail closed until reset.
      const latest = refreshFromStorage();
      if (latest.error) {
        return false;
      }

      const nextProjects = latest.projects.some((candidate) => candidate.id === validation.project.id)
        ? latest.projects.map((candidate) =>
            candidate.id === validation.project.id ? validation.project : candidate,
          )
        : [validation.project, ...latest.projects];

      const persisted = persistProjects(nextProjects);
      if (!persisted.ok) {
        publish({ ...snapshot, error: persisted.error });
        return false;
      }

      publish({
        projects: nextProjects,
        ready: true,
        error: null,
        writesBlocked: false,
      });
      return true;
    },
    [current.ready],
  );

  const deleteProject = useCallback(
    (id: string): boolean => {
      if (!current.ready) {
        publish({ ...snapshot, error: LOADING_MESSAGE });
        return false;
      }

      const normalizedId = id.trim();
      if (!normalizedId) {
        publish({ ...snapshot, error: "Project id is required to remove a brief." });
        return false;
      }

      // As with save, use the latest snapshot before deleting so a stale tab
      // cannot remove or rewrite a newer list accidentally.
      const latest = refreshFromStorage();
      if (latest.error) {
        return false;
      }

      if (!latest.projects.some((project) => project.id === normalizedId)) {
        publish({ ...snapshot, error: "That project brief is no longer available in this browser." });
        return false;
      }

      const nextProjects = latest.projects.filter((project) => project.id !== normalizedId);
      const persisted = persistProjects(nextProjects);
      if (!persisted.ok) {
        publish({ ...snapshot, error: persisted.error });
        return false;
      }

      publish({
        projects: nextProjects,
        ready: true,
        error: null,
        writesBlocked: false,
      });
      return true;
    },
    [current.ready],
  );

  return {
    projects: current.projects,
    ready: current.ready,
    error: current.error,
    saveProject,
    deleteProject,
  };
}
