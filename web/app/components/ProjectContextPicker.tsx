"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useId, useState } from "react";
import { useProjects } from "../hooks/useProjects";
import { formatProjectContext, type ProjectBrief } from "@/lib/projects";

export function withProjectContext(description: string, project: ProjectBrief | null): string {
  if (!project) return description;
  const combined = `${description}\n\nProject context (background for this task):\n${formatProjectContext(project)}`;
  if (Array.from(combined).length > 8000) {
    throw new Error("The task and project context exceed 8,000 characters. Shorten the task or project brief, or detach the project.");
  }
  return combined;
}

type PickerProps = {
  onChange: (project: ProjectBrief | null) => void;
  disabled?: boolean;
};

export default function ProjectContextPicker(props: PickerProps) {
  return <Suspense fallback={<p className="text-xs text-zinc-400">Loading project context…</p>}>
    <ProjectContextPickerContent {...props} />
  </Suspense>;
}

function ProjectContextPickerContent({ onChange, disabled = false }: PickerProps) {
  const { projects, ready, error } = useProjects();
  const searchParams = useSearchParams();
  const [manualSelection, setSelectedId] = useState<string | null>(null);
  const selectedId = manualSelection ?? searchParams?.get("project") ?? "";
  const [attached, setAttached] = useState<ProjectBrief | null>(null);
  const selectId = useId();
  const candidate = projects.find((project) => project.id === selectedId);
  const savedAttachment = projects.find((project) => project.id === attached?.id);
  const attachmentChanged = attached && ready && (
    !savedAttachment || formatProjectContext(savedAttachment) !== formatProjectContext(attached)
  );
  const missing = ready && Boolean(selectedId) && !candidate;

  return (
    <section aria-label="Project context" className="rounded-xl border border-cyan-400/15 bg-cyan-400/[0.03] p-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={selectId} className="font-medium text-zinc-200">Project context</label>
        <Link href="/agentic-coding" className="text-xs text-cyan-300 hover:underline">Manage projects</Link>
      </div>
      <p className="mt-1 text-xs text-zinc-400">Optional. Attach a saved brief while keeping your task below.</p>
      {error && <p role="alert" className="mt-2 text-xs text-amber-300">{error}</p>}
      {missing && <p role="status" className="mt-2 text-xs text-amber-300">This project is unavailable in this browser. Choose another project or continue without one.</p>}
      <select id={selectId} value={candidate ? selectedId : ""} disabled={!ready || disabled}
        onChange={(event) => setSelectedId(event.target.value)}
        className="mt-2 w-full rounded-lg border border-white/15 bg-zinc-950 p-2 text-zinc-200">
        <option value="">Choose a project</option>
        {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
      </select>
      {candidate && <details className="mt-2 text-xs text-zinc-400">
        <summary className="cursor-pointer text-zinc-300">Preview selected project</summary>
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words font-sans">{formatProjectContext(candidate)}</pre>
      </details>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button type="button" disabled={!candidate || disabled} onClick={() => {
          if (!candidate) return;
          const snapshot = { ...candidate };
          setAttached(snapshot);
          onChange(snapshot);
        }} className="rounded-lg bg-cyan-400/10 px-3 py-2 text-xs font-medium text-cyan-200 disabled:opacity-40">
          {attached ? "Replace attached context" : "Attach project context"}
        </button>
        {attached && <button type="button" disabled={disabled} onClick={() => {
          setAttached(null);
          onChange(null);
        }} className="rounded-lg border border-white/15 px-3 py-2 text-xs text-zinc-300">Detach project</button>}
      </div>
      <p role="status" className="mt-2 text-xs text-zinc-400">
        {attached ? `Attached: ${attached.name}. Saved edits apply only when you attach again.` : "No project attached. This tool works on its own."}
      </p>
      {attached && <details className="mt-2 text-xs text-zinc-400">
        <summary className="cursor-pointer text-zinc-300">Preview attached context</summary>
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words font-sans">{formatProjectContext(attached)}</pre>
      </details>}
      {attachmentChanged && <p role="status" className="mt-2 text-xs text-amber-300">The saved project changed or was removed. This form still uses the attached snapshot; attach again to update it, or detach it.</p>}
    </section>
  );
}
