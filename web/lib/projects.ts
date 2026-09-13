/**
 * The small, browser-only project brief model used by the Agentic Coding hub.
 *
 * Project briefs intentionally stay separate from repository state. They are a
 * reusable description that a person can attach to a generator request; this
 * module never reads a path, contacts a server, or claims to synchronize a repo.
 */

export type ProjectBrief = {
  id: string;
  name: string;
  projectType: string;
  stack: string;
  goal: string;
  rules: string;
};

export const PROJECTS_STORAGE_KEY = "promptc_projects_v1";
export const PROJECTS_STORAGE_VERSION = 1;
export const PROJECTS_STORAGE_EVENT = "promptc_projects_changed";

/** Maximum number of briefs and maximum characters per saved field. */
export const PROJECT_LIMITS = {
  maxProjects: 50,
  id: 100,
  name: 120,
  projectType: 120,
  stack: 200,
  goal: 2500,
  rules: 2500,
} as const;

const PROJECT_FIELDS = ["id", "name", "projectType", "stack", "goal", "rules"] as const;
type ProjectField = (typeof PROJECT_FIELDS)[number];

const STORAGE_UNAVAILABLE_MESSAGE =
  "Project storage is unavailable in this browser. Your brief stays on this page until local storage is available.";
const STORAGE_READ_MESSAGE =
  "Saved project data could not be read. Reset the local project data to start fresh; your current brief stays on this page.";
const STORAGE_VERSION_MESSAGE =
  "Saved project data uses an unsupported version. Reset the local project data to start fresh.";
const STORAGE_WRITE_MESSAGE =
  "The project brief could not be saved to this browser. Check available storage and try again.";
const STORAGE_DELETE_MESSAGE =
  "The project brief could not be removed from this browser. Check available storage and try again.";

type StorageEnvelope = {
  version: number;
  projects: unknown;
};

export type ProjectValidationResult =
  | { valid: true; project: ProjectBrief }
  | { valid: false; error: string };

export type ProjectStorageReadResult = {
  projects: ProjectBrief[];
  error: string | null;
  available: boolean;
};

export type ProjectStorageWriteResult = {
  ok: boolean;
  error: string | null;
};

function getBrowserStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function trimProjectField(value: string): string {
  return value.trim();
}

function fieldLimit(field: ProjectField): number {
  return PROJECT_LIMITS[field];
}

/**
 * Validate and normalize one brief before it enters state or local storage.
 * Name and id identify a usable brief; the other fields may be empty while a
 * person is sketching a project, but every field must remain a string.
 */
export function validateProject(project: unknown): ProjectValidationResult {
  if (!isRecord(project)) {
    return { valid: false, error: "A project brief must be an object." };
  }

  for (const field of PROJECT_FIELDS) {
    if (typeof project[field] !== "string") {
      return { valid: false, error: `Project ${field} must be a string.` };
    }
  }

  const normalized: ProjectBrief = {
    id: trimProjectField(project.id as string),
    name: trimProjectField(project.name as string),
    projectType: trimProjectField(project.projectType as string),
    stack: trimProjectField(project.stack as string),
    goal: trimProjectField(project.goal as string),
    rules: trimProjectField(project.rules as string),
  };

  if (!normalized.id) {
    return { valid: false, error: "Project id is required." };
  }

  if (!normalized.name) {
    return { valid: false, error: "Project name is required." };
  }

  for (const field of PROJECT_FIELDS) {
    if (normalized[field].length > fieldLimit(field)) {
      return {
        valid: false,
        error: `Project ${field} is too long (maximum ${fieldLimit(field)} characters).`,
      };
    }
  }

  return { valid: true, project: normalized };
}

function validateProjectList(projects: unknown): { projects: ProjectBrief[]; error: string | null } {
  if (!Array.isArray(projects)) {
    return { projects: [], error: "Saved project data is missing its project list." };
  }

  if (projects.length > PROJECT_LIMITS.maxProjects) {
    return {
      projects: [],
      error: `Saved project data exceeds the ${PROJECT_LIMITS.maxProjects}-project limit. Reset the local project data to start fresh.`,
    };
  }

  const validProjects: ProjectBrief[] = [];
  const seenIds = new Set<string>();
  for (const candidate of projects) {
    const validated = validateProject(candidate);
    if (!validated.valid) {
      return { projects: validProjects, error: `${STORAGE_READ_MESSAGE} (${validated.error})` };
    }

    if (seenIds.has(validated.project.id)) {
      return {
        projects: validProjects,
        error: `${STORAGE_READ_MESSAGE} (duplicate project id: ${validated.project.id})`,
      };
    }

    seenIds.add(validated.project.id);
    validProjects.push(validated.project);
  }

  return { projects: validProjects, error: null };
}

/** Read the versioned project envelope from browser local storage. */
export function loadProjects(storage?: Storage | null): ProjectStorageReadResult {
  const target = storage === undefined ? getBrowserStorage() : storage;
  if (!target) {
    return { projects: [], error: STORAGE_UNAVAILABLE_MESSAGE, available: false };
  }

  let raw: string | null;
  try {
    raw = target.getItem(PROJECTS_STORAGE_KEY);
  } catch {
    return { projects: [], error: STORAGE_UNAVAILABLE_MESSAGE, available: false };
  }

  if (raw === null) {
    return { projects: [], error: null, available: true };
  }

  let decoded: unknown;
  try {
    decoded = JSON.parse(raw);
  } catch {
    return { projects: [], error: STORAGE_READ_MESSAGE, available: true };
  }

  const projectsValue =
    isRecord(decoded) && (decoded as StorageEnvelope).version === PROJECTS_STORAGE_VERSION
      ? (decoded as StorageEnvelope).projects
      : undefined;

  if (projectsValue === undefined) {
    return { projects: [], error: STORAGE_VERSION_MESSAGE, available: true };
  }

  const result = validateProjectList(projectsValue);
  return { ...result, available: true };
}

/** Persist a complete project list as one atomic local-storage write. */
export function persistProjects(
  projects: ProjectBrief[],
  storage?: Storage | null,
): ProjectStorageWriteResult {
  const target = storage === undefined ? getBrowserStorage() : storage;
  if (!target) {
    return { ok: false, error: STORAGE_UNAVAILABLE_MESSAGE };
  }

  const validation = validateProjectList(projects);
  if (validation.error) {
    return { ok: false, error: validation.error };
  }

  const payload: StorageEnvelope = {
    version: PROJECTS_STORAGE_VERSION,
    projects: validation.projects,
  };

  try {
    target.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(payload));
    dispatchProjectsChanged();
    return { ok: true, error: null };
  } catch {
    return { ok: false, error: STORAGE_WRITE_MESSAGE };
  }
}

/** Remove all saved briefs so a malformed or stale local payload can recover. */
export function clearProjectsStorage(storage?: Storage | null): ProjectStorageWriteResult {
  const target = storage === undefined ? getBrowserStorage() : storage;
  if (!target) {
    return { ok: false, error: STORAGE_UNAVAILABLE_MESSAGE };
  }

  try {
    target.removeItem(PROJECTS_STORAGE_KEY);
    dispatchProjectsChanged();
    return { ok: true, error: null };
  } catch {
    return { ok: false, error: STORAGE_DELETE_MESSAGE };
  }
}

function dispatchProjectsChanged(): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.dispatchEvent(new Event(PROJECTS_STORAGE_EVENT));
  } catch {
    // Storage writes already succeeded. An event failure only means another
    // same-tab consumer will refresh on its next mount or browser event.
  }
}

/**
 * Turn a brief into labeled context for a generator request.
 * This is descriptive project context, not a system instruction.
 */
export function formatProjectContext(project: ProjectBrief): string {
  const valueOrPlaceholder = (value: string, placeholder: string) => value.trim() || placeholder;

  return [
    `Name: ${valueOrPlaceholder(project.name, "(unnamed project)")}`,
    `Type: ${valueOrPlaceholder(project.projectType, "(not specified)")}`,
    `Stack: ${valueOrPlaceholder(project.stack, "(not specified)")}`,
    `Goal: ${valueOrPlaceholder(project.goal, "(not specified)")}`,
    `Rules:\n${valueOrPlaceholder(project.rules, "(none specified)")}`,
  ].join("\n\n");
}
