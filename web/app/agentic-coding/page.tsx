"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import {
  ArrowUpRight,
  Boxes,
  Check,
  ChevronRight,
  CircleAlert,
  Code2,
  FolderKanban,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import {
  clearProjectsStorage,
  PROJECT_LIMITS,
  type ProjectBrief,
} from "../../lib/projects";
import { useProjects } from "../hooks/useProjects";

type ProjectDraft = Omit<ProjectBrief, "id">;
type PendingDraftAction =
  | { kind: "new" }
  | { kind: "starter" }
  | { kind: "edit"; project: ProjectBrief };

const EMPTY_DRAFT: ProjectDraft = {
  name: "",
  projectType: "",
  stack: "",
  goal: "",
  rules: "",
};

const STARTER_DRAFT: ProjectDraft = {
  name: "Signal board",
  projectType: "Web app",
  stack: "Next.js, TypeScript, SQLite",
  goal: "Turn a small collection of signals into a clear, searchable dashboard.",
  rules: "Keep the first release easy to run locally. Prefer small, reviewable changes.",
};

function createProjectId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return `project-${crypto.randomUUID()}`;
    }
  } catch {
    // Some privacy modes expose crypto but block randomUUID. The fallback is
    // still local and only needs to be unique among this browser's briefs.
  }

  return `project-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function projectLink(path: string, id: string): string {
  return `${path}?project=${encodeURIComponent(id)}`;
}

function sameProject(left: ProjectBrief, right: ProjectBrief): boolean {
  return (
    left.id === right.id &&
    left.name === right.name &&
    left.projectType === right.projectType &&
    left.stack === right.stack &&
    left.goal === right.goal &&
    left.rules === right.rules
  );
}

function draftMatchesProject(draft: ProjectDraft, project: ProjectBrief): boolean {
  return (
    draft.name === project.name &&
    draft.projectType === project.projectType &&
    draft.stack === project.stack &&
    draft.goal === project.goal &&
    draft.rules === project.rules
  );
}

function draftIsEmpty(draft: ProjectDraft): boolean {
  return Object.values(draft).every((value) => !value.trim());
}

function ProjectField({
  id,
  label,
  value,
  onChange,
  maxLength,
  multiline = false,
  placeholder,
  hint,
  rows,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  maxLength: number;
  multiline?: boolean;
  placeholder: string;
  hint: string;
  rows?: number;
}) {
  const hintId = `${id}-hint`;
  const commonProps = {
    id,
    value,
    maxLength,
    onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(event.target.value),
    placeholder,
    "aria-describedby": hintId,
    className:
      "w-full rounded-xl border border-white/10 bg-[#080a0e]/90 px-3.5 py-3 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-cyan-300/50 focus:ring-2 focus:ring-cyan-300/10",
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-zinc-200">
          {label}
        </label>
        <span className="text-[11px] tabular-nums text-zinc-600">
          {value.length}/{maxLength}
        </span>
      </div>
      <p id={hintId} className="text-xs leading-relaxed text-zinc-500">
        {hint}
      </p>
      {multiline ? <textarea {...commonProps} rows={rows ?? 5} /> : <input {...commonProps} />}
    </div>
  );
}

function ProjectCard({
  project,
  confirmingDelete,
  onEdit,
  onRequestDelete,
  onConfirmDelete,
  onCancelDelete,
}: {
  project: ProjectBrief;
  confirmingDelete: boolean;
  onEdit: (project: ProjectBrief) => void;
  onRequestDelete: (id: string) => void;
  onConfirmDelete: (id: string) => void;
  onCancelDelete: () => void;
}) {
  return (
    <article
      aria-labelledby={`project-title-${project.id}`}
      className="group relative flex min-h-[285px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#10141a]/90 shadow-[0_16px_48px_rgba(0,0,0,0.2)] transition-colors hover:border-cyan-300/25"
    >
      <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-cyan-300 via-cyan-400/70 to-blue-500/30" aria-hidden="true" />
      <div className="flex flex-1 flex-col p-5 pl-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="mb-3 flex items-center gap-2 text-xs text-cyan-200/80">
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-lg border border-cyan-300/20 bg-cyan-300/10">
                <FolderKanban size={13} aria-hidden="true" />
              </span>
              <span className="truncate">{project.projectType || "Project brief"}</span>
            </div>
            <h3 id={`project-title-${project.id}`} className="truncate text-xl font-semibold tracking-tight text-white">
              {project.name}
            </h3>
          </div>
          <span className="shrink-0 rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2.5 py-1 text-[11px] font-medium text-emerald-200">
            Saved locally
          </span>
        </div>

        <div className="mt-5 space-y-4">
          <div>
            <p className="mb-1 text-[11px] font-medium text-zinc-500">Stack</p>
            <p className="line-clamp-2 text-sm leading-relaxed text-zinc-200">
              {project.stack || "No stack recorded yet."}
            </p>
          </div>
          <div>
            <p className="mb-1 text-[11px] font-medium text-zinc-500">Goal</p>
            <p className="line-clamp-3 text-sm leading-relaxed text-zinc-400">
              {project.goal || "Add a goal when you are ready."}
            </p>
          </div>
        </div>

        <div className="mt-auto pt-5">
          <div className="flex flex-wrap gap-2 border-t border-white/8 pt-4">
            <Link
              href={projectLink("/agentic-coding/agents", project.id)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-200 transition hover:border-cyan-300/30 hover:bg-cyan-300/10 hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              Create agent <ArrowUpRight size={13} aria-hidden="true" />
            </Link>
            <Link
              href={projectLink("/agentic-coding/skills", project.id)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-200 transition hover:border-cyan-300/30 hover:bg-cyan-300/10 hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              Create skill/tool <ArrowUpRight size={13} aria-hidden="true" />
            </Link>
            <Link
              href={projectLink("/agentic-coding/instructions", project.id)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-300/20 bg-cyan-300/5 px-3 py-2 text-xs font-medium text-cyan-200 transition hover:bg-cyan-300/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              Review instructions <ArrowUpRight size={13} aria-hidden="true" />
            </Link>
            <Link
              href={projectLink("/agentic-coding/projects/export", project.id)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-400 transition hover:border-cyan-300/30 hover:bg-cyan-300/10 hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              Export pack <ArrowUpRight size={13} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-white/8 bg-black/10 px-5 py-3 pl-6">
        <button
          type="button"
          onClick={() => onEdit(project)}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-zinc-400 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
        >
          <Code2 size={13} aria-hidden="true" /> Edit brief
        </button>
        {confirmingDelete ? (
          <div className="flex items-center gap-2" role="group" aria-label={`Delete ${project.name}`}>
            <span className="text-xs text-rose-200">Remove this brief?</span>
            <button
              type="button"
              onClick={() => onConfirmDelete(project.id)}
              className="rounded-lg border border-rose-400/25 bg-rose-400/10 px-2.5 py-1.5 text-xs font-medium text-rose-200 transition hover:bg-rose-400/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/60"
            >
              Confirm
            </button>
            <button
              type="button"
              onClick={onCancelDelete}
              className="rounded-lg px-2 py-1.5 text-xs text-zinc-400 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              Keep
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => onRequestDelete(project.id)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-zinc-500 transition hover:bg-rose-400/10 hover:text-rose-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/60"
          >
            <Trash2 size={13} aria-hidden="true" /> Delete
          </button>
        )}
      </div>
    </article>
  );
}

export default function AgenticCodingProjectsPage() {
  const { projects, ready, error, saveProject, deleteProject } = useProjects();
  const [draft, setDraft] = useState<ProjectDraft>(EMPTY_DRAFT);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingOriginal, setEditingOriginal] = useState<ProjectBrief | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [resetPending, setResetPending] = useState(false);
  const [pendingDraftAction, setPendingDraftAction] = useState<PendingDraftAction | null>(null);
  const [staleOverwriteConfirmed, setStaleOverwriteConfirmed] = useState(false);

  const currentEditingProject = editingId ? projects.find((project) => project.id === editingId) : undefined;
  const draftIsStale = Boolean(
    editingOriginal && (!currentEditingProject || !sameProject(editingOriginal, currentEditingProject)),
  );
  const draftHasChanges = editingOriginal ? !draftMatchesProject(draft, editingOriginal) : !draftIsEmpty(draft);

  const focusProjectName = () => {
    if (typeof window === "undefined") return;
    window.setTimeout(() => {
      const input = document.getElementById("project-name") as HTMLInputElement | null;
      if (!input) return;
      input.focus({ preventScroll: true });
      input.scrollIntoView?.({ block: "nearest" });
    }, 0);
  };

  const updateDraft = (field: keyof ProjectDraft, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }));
    setFormError(null);
    setNotice(null);
  };

  const applyNewProject = () => {
    setEditingId(null);
    setEditingOriginal(null);
    setDraft(EMPTY_DRAFT);
    setFormError(null);
    setNotice(null);
    setConfirmingDeleteId(null);
    setStaleOverwriteConfirmed(false);
    focusProjectName();
  };

  const applyStarter = () => {
    setEditingId(null);
    setEditingOriginal(null);
    setDraft(STARTER_DRAFT);
    setFormError(null);
    setNotice("Starter fields loaded. Save the brief when it looks right.");
    setStaleOverwriteConfirmed(false);
    focusProjectName();
  };

  const applyEdit = (project: ProjectBrief) => {
    setEditingId(project.id);
    setEditingOriginal(project);
    setDraft({
      name: project.name,
      projectType: project.projectType,
      stack: project.stack,
      goal: project.goal,
      rules: project.rules,
    });
    setFormError(null);
    setNotice(null);
    setConfirmingDeleteId(null);
    setStaleOverwriteConfirmed(false);
    focusProjectName();
  };

  const requestNewProject = () => {
    if (draftHasChanges) {
      setPendingDraftAction({ kind: "new" });
      return;
    }
    applyNewProject();
  };

  const requestStarter = () => {
    if (draftHasChanges) {
      setPendingDraftAction({ kind: "starter" });
      return;
    }
    applyStarter();
  };

  const requestEdit = (project: ProjectBrief) => {
    if (draftHasChanges) {
      setPendingDraftAction({ kind: "edit", project });
      return;
    }
    applyEdit(project);
  };

  const discardDraftAndContinue = () => {
    if (!pendingDraftAction) return;
    const action = pendingDraftAction;
    setPendingDraftAction(null);
    if (action.kind === "new") {
      applyNewProject();
    } else if (action.kind === "starter") {
      applyStarter();
    } else {
      applyEdit(action.project);
    }
  };

  const handleSave = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft.name.trim()) {
      setFormError("Give this project a name before saving.");
      return;
    }
    if (draftIsStale && !staleOverwriteConfirmed) {
      setFormError("This brief changed in another tab. Choose Overwrite latest brief before saving.");
      return;
    }

    const saved = saveProject({
      id: editingId ?? createProjectId(),
      ...draft,
    });
    if (!saved) {
      setFormError(error ?? "The brief could not be saved. Check the storage message above and try again.");
      return;
    }

    setDraft(EMPTY_DRAFT);
    setEditingId(null);
    setEditingOriginal(null);
    setFormError(null);
    setNotice("Project brief saved in this browser.");
  };

  const handleDelete = (id: string) => {
    if (!deleteProject(id)) {
      setNotice(null);
      return;
    }

    if (editingId === id) {
      applyNewProject();
    }
    setConfirmingDeleteId(null);
    setNotice("Project brief removed from this browser.");
  };

  const handleReset = () => {
    if (!resetPending) {
      setResetPending(true);
      return;
    }

    const cleared = clearProjectsStorage();
    if (!cleared.ok) {
      setNotice(cleared.error ?? "Local project data could not be reset.");
      setResetPending(false);
      return;
    }

    // Clearing storage emits the same-tab update. Keep anything currently in
    // the editor, but treat it as a new unsaved brief instead of tying it to a
    // project that was just removed.
    setEditingId(null);
    setEditingOriginal(null);
    setStaleOverwriteConfirmed(false);
    setResetPending(false);
    setNotice("Local project data was cleared. Your current draft stays on this page.");
  };

  return (
    <main className="relative min-h-full overflow-hidden bg-[#07090d] text-zinc-300">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-40 [background-image:linear-gradient(rgba(108,240,214,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(108,240,214,0.035)_1px,transparent_1px)] [background-size:48px_48px]"
      />
      <div aria-hidden="true" className="pointer-events-none absolute -left-24 top-20 h-80 w-80 rounded-full bg-cyan-400/10 blur-[120px]" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-32 bottom-0 h-96 w-96 rounded-full bg-blue-500/10 blur-[130px]" />

      <div className="relative mx-auto flex min-h-full max-w-[1440px] flex-col px-4 py-5 sm:px-8 sm:py-8 xl:px-10">
        <header className="flex flex-col gap-5 border-b border-white/8 pb-5 sm:flex-row sm:items-center sm:justify-between">
          <Link href="/agentic-coding" className="group inline-flex w-fit items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200 shadow-[0_0_32px_rgba(88,226,199,0.12)]">
              <Boxes size={19} aria-hidden="true" />
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-tight text-white">Agentic coding</span>
              <span className="block text-xs text-zinc-500">Reusable project context</span>
            </span>
          </Link>

          <nav aria-label="Agentic coding workspace" className="flex items-center gap-1 rounded-xl border border-white/8 bg-white/[0.025] p-1">
            <Link
              href="/agentic-coding"
              aria-current="page"
              className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-2 text-xs font-medium text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              <FolderKanban size={14} aria-hidden="true" /> Projects
            </Link>
            <Link
              href="/agentic-coding/agents"
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-zinc-500 transition hover:bg-white/5 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              Agents <ChevronRight size={13} aria-hidden="true" />
            </Link>
            <Link
              href="/agentic-coding/skills"
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-zinc-500 transition hover:bg-white/5 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              Skills &amp; Tools <ChevronRight size={13} aria-hidden="true" />
            </Link>
          </nav>
        </header>

        <section className="flex flex-col gap-6 py-9 sm:flex-row sm:items-end sm:justify-between sm:py-12">
          <div className="max-w-2xl">
            <p className="mb-3 flex items-center gap-2 text-xs font-medium text-cyan-200/80">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(103,232,213,0.8)]" aria-hidden="true" />
              Local project workspace
            </p>
            <h1 className="text-4xl font-semibold tracking-[-0.04em] text-white sm:text-5xl">Projects</h1>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-zinc-400">
              Save a project brief once, then attach it to an agent or skill request when you need it.
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-start gap-3 sm:items-end">
            <p className="text-xs text-zinc-500">
              {projects.length} {projects.length === 1 ? "brief" : "briefs"} saved here
            </p>
            <button
              type="button"
              onClick={requestNewProject}
              className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2.5 text-sm font-semibold text-[#07100f] shadow-[0_8px_30px_rgba(88,226,199,0.18)] transition hover:bg-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200/80"
            >
              <Plus size={16} aria-hidden="true" /> New project
            </button>
          </div>
        </section>

        {error && (
          <section role="alert" className="mb-6 flex flex-col gap-4 rounded-2xl border border-amber-300/20 bg-amber-300/[0.06] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <CircleAlert size={18} className="mt-0.5 shrink-0 text-amber-200" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium text-amber-100">Project storage needs attention</p>
                <p className="mt-1 max-w-3xl text-xs leading-relaxed text-amber-100/70">{error}</p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2 pl-7 sm:pl-0">
              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200/25 bg-amber-200/10 px-3 py-2 text-xs font-medium text-amber-100 transition hover:bg-amber-200/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200/70"
              >
                <RotateCcw size={13} aria-hidden="true" /> {resetPending ? "Confirm reset" : "Reset local data"}
              </button>
              {resetPending && (
                <button
                  type="button"
                  onClick={() => setResetPending(false)}
                  className="rounded-lg px-2 py-2 text-xs text-zinc-400 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
                >
                  Keep data
                </button>
              )}
            </div>
          </section>
        )}

        {notice && (
          <p role="status" className="mb-6 inline-flex w-fit items-center gap-2 rounded-lg border border-emerald-300/20 bg-emerald-300/[0.06] px-3 py-2 text-xs text-emerald-100">
            <Check size={14} aria-hidden="true" /> {notice}
          </p>
        )}

        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.03] p-4">
          <div><p className="text-sm font-medium text-white">Already have project instructions?</p><p className="mt-1 text-xs text-zinc-400">Review existing instruction files for repeated rules and possible conflicts.</p></div>
          <Link href="/agentic-coding/instructions" className="rounded-lg border border-cyan-300/25 px-3 py-2 text-sm text-cyan-200 hover:bg-cyan-300/10">Review instructions</Link>
        </div>
        <div className="grid gap-6 pb-10 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-start">
          <section aria-labelledby="saved-projects-heading">
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <h2 id="saved-projects-heading" className="text-lg font-semibold tracking-tight text-white">Saved projects</h2>
                <p className="mt-1 text-xs text-zinc-500">A project brief is a reusable description, kept in this browser.</p>
              </div>
              {ready && projects.length > 0 && <span className="text-xs text-zinc-600">{projects.length}/{PROJECT_LIMITS.maxProjects}</span>}
            </div>

            {!ready ? (
              <div className="flex min-h-[285px] items-center justify-center rounded-2xl border border-white/8 bg-white/[0.02] text-sm text-zinc-500" role="status">
                Reading local project briefs...
              </div>
            ) : projects.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-cyan-300/20 bg-cyan-300/[0.035] p-6 sm:p-8">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200">
                  <Sparkles size={19} aria-hidden="true" />
                </div>
                <h3 className="mt-5 text-xl font-semibold tracking-tight text-white">No project briefs yet.</h3>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-zinc-400">
                  Create a brief with a name, goal, and optional constraints. You can fill in the details over time.
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={requestNewProject}
                    className="inline-flex items-center gap-2 rounded-lg bg-white px-3.5 py-2.5 text-xs font-semibold text-zinc-900 transition hover:bg-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70"
                  >
                    <Plus size={14} aria-hidden="true" /> Create your first project
                  </button>
                  <button
                    type="button"
                    onClick={requestStarter}
                    className="rounded-lg border border-white/10 px-3.5 py-2.5 text-xs font-medium text-zinc-300 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
                  >
                    Load a starter brief
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid gap-4 xl:grid-cols-2">
                {projects.map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    confirmingDelete={confirmingDeleteId === project.id}
                    onEdit={requestEdit}
                    onRequestDelete={(id) => setConfirmingDeleteId(id)}
                    onConfirmDelete={handleDelete}
                    onCancelDelete={() => setConfirmingDeleteId(null)}
                  />
                ))}
              </div>
            )}
          </section>

          <aside className="rounded-2xl border border-white/10 bg-[#10141a]/95 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)] sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium text-cyan-200/80">{editingId ? "Editing a saved brief" : "Build a project brief"}</p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight text-white">{editingId ? "Edit project" : "New project"}</h2>
              </div>
              {editingId && (
                <button
                  type="button"
                  onClick={requestNewProject}
                  aria-label="Cancel editing"
                  className="rounded-lg p-2 text-zinc-500 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
                >
                  <X size={16} aria-hidden="true" />
                </button>
              )}
            </div>

            <p className="mt-3 text-xs leading-relaxed text-zinc-500">
              Saved changes stay in this browser. Typing here edits a draft until you choose Save project.
            </p>

            {editingId && (
              <div className="mt-4 rounded-xl border border-white/8 bg-black/10 px-3 py-2.5">
                <p className="text-[11px] text-zinc-600">Project id</p>
                <code className="mt-1 block break-all text-[11px] text-zinc-400">{editingId}</code>
              </div>
            )}

            {draftIsStale && (
              <div role="status" className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/[0.06] px-3 py-2.5 text-xs leading-relaxed text-amber-100/80">
                <p>This saved brief changed in another tab. Your draft stays here until you choose what to do.</p>
                <button
                  type="button"
                  onClick={() => {
                    setStaleOverwriteConfirmed(true);
                    setFormError(null);
                    setNotice("Saving will overwrite the latest saved brief with this draft.");
                  }}
                  disabled={staleOverwriteConfirmed}
                  className="mt-2 rounded-lg border border-amber-200/25 bg-amber-200/10 px-2.5 py-1.5 text-xs font-medium text-amber-100 transition hover:bg-amber-200/20 disabled:cursor-default disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200/70"
                >
                  {staleOverwriteConfirmed ? "Overwrite enabled" : "Overwrite latest brief"}
                </button>
              </div>
            )}

            {pendingDraftAction && (
              <div role="alertdialog" aria-label="Unsaved project draft" className="mt-4 rounded-xl border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-3">
                <p className="text-sm font-medium text-cyan-100">Unsaved draft</p>
                <p className="mt-1 text-xs leading-relaxed text-cyan-100/70">
                  Changing projects will discard the fields you have typed. Save first, or discard this draft to continue.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={discardDraftAndContinue}
                    className="rounded-lg bg-cyan-200 px-2.5 py-1.5 text-xs font-semibold text-[#07100f] transition hover:bg-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200/80"
                  >
                    Discard and continue
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingDraftAction(null)}
                    className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-zinc-300 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
                  >
                    Keep editing
                  </button>
                </div>
              </div>
            )}

            <form onSubmit={handleSave} className="mt-5 flex flex-col gap-5">
              <ProjectField
                id="project-name"
                label="Project name"
                value={draft.name}
                onChange={(value) => updateDraft("name", value)}
                maxLength={PROJECT_LIMITS.name}
                placeholder="e.g. Signal board"
                hint="A short name you will recognize in the generators."
              />
              <ProjectField
                id="project-type"
                label="Project type"
                value={draft.projectType}
                onChange={(value) => updateDraft("projectType", value)}
                maxLength={PROJECT_LIMITS.projectType}
                placeholder="e.g. Web app, CLI, research tool"
                hint="The kind of thing you are shaping."
              />
              <ProjectField
                id="project-stack"
                label="Stack"
                value={draft.stack}
                onChange={(value) => updateDraft("stack", value)}
                maxLength={PROJECT_LIMITS.stack}
                placeholder="e.g. Next.js, TypeScript, SQLite"
                hint="Languages, frameworks, or services that matter to the brief."
              />
              <ProjectField
                id="project-goal"
                label="Goal"
                value={draft.goal}
                onChange={(value) => updateDraft("goal", value)}
                maxLength={PROJECT_LIMITS.goal}
                multiline
                rows={4}
                placeholder="What should this project make possible?"
                hint="State the outcome in your own words."
              />
              <ProjectField
                id="project-rules"
                label="Rules"
                value={draft.rules}
                onChange={(value) => updateDraft("rules", value)}
                maxLength={PROJECT_LIMITS.rules}
                multiline
                rows={4}
                placeholder="Constraints, defaults, or review preferences"
                hint="Optional constraints to carry with the brief."
              />

              {formError && (
                <p role="alert" className="rounded-xl border border-rose-300/20 bg-rose-300/[0.06] px-3 py-2.5 text-xs leading-relaxed text-rose-100/80">
                  {formError}
                </p>
              )}

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/8 pt-4">
                <button
                  type="button"
                  onClick={requestStarter}
                  className="inline-flex items-center gap-1.5 rounded-lg px-2 py-2 text-xs text-zinc-500 transition hover:bg-white/5 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
                >
                  <Sparkles size={13} aria-hidden="true" /> Use starter fields
                </button>
                <div className="flex items-center gap-2">
                  {editingId && (
                    <button
                      type="button"
                      onClick={requestNewProject}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-medium text-zinc-400 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={!ready || (draftIsStale && !staleOverwriteConfirmed)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-300 px-3.5 py-2 text-xs font-semibold text-[#07100f] transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200/80"
                  >
                    <Save size={14} aria-hidden="true" /> {editingId ? "Save changes" : "Save project"}
                  </button>
                </div>
              </div>
            </form>
          </aside>
        </div>

        <footer className="mt-auto border-t border-white/8 pt-4 text-xs text-zinc-600">
          Project briefs are stored in this browser only. This hub does not sync them to a server.
        </footer>
      </div>
    </main>
  );
}
