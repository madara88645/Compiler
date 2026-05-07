"use client";

import { useMemo, useState } from "react";
import { Bot, Copy, Download, FileCode2, FolderArchive, ShieldCheck, Sparkles } from "lucide-react";

import { apiFetch, apiJson, buildGeneratorApiHeaders } from "@/config";
import InfoButton from "../components/InfoButton";
import { showError } from "../lib/showError";
import { agentPackProviders } from "./providerRegistry";
import type {
  AgentPackFile,
  AgentPackFileKind,
  AgentPackManifest,
  AgentPackRequest,
  AgentPackRiskMode,
  AgentPackType,
} from "./types";

const PACK_OPTIONS: { id: AgentPackType; label: string; detail: string }[] = [
  {
    id: "project-pack",
    label: "Project Pack",
    detail: "Full repo memory, settings, agents, workflow, and MCP snippet.",
  },
  {
    id: "subagent",
    label: "Subagent",
    detail: "A focused Claude subagent bundle you can drop into a repo.",
  },
  {
    id: "pr-reviewer",
    label: "PR Reviewer",
    detail: "A review-focused pack for code review, safety checks, and regressions.",
  },
  {
    id: "mcp-tool-stub",
    label: "MCP Tool Stub",
    detail: "A starter MCP tool skeleton with README notes for Claude workflows.",
  },
];

const PREVIEW_LABELS: Record<AgentPackFileKind, string> = {
  claude_md: "CLAUDE.md",
  settings: "settings.json",
  agents: "agents",
  workflow: "workflow",
  mcp: "mcp",
  readme: "README",
  files: "files",
};

const RISK_OPTIONS: { id: AgentPackRiskMode; label: string; detail: string }[] = [
  { id: "balanced", label: "Balanced", detail: "Practical defaults with guardrails." },
  { id: "strict", label: "Strict", detail: "Tighter permissions and more defensive posture." },
];

const DEFAULT_REQUEST: AgentPackRequest = {
  project_type: "SaaS",
  stack: "FastAPI + Next.js",
  goal: "",
  pack_type: "project-pack",
  risk_mode: "balanced",
};

function getDownloadFilename(response: Response, fallback: string): string {
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename=\"?([^"]+)\"?/i);
  return match?.[1] || fallback;
}

function bundleFiles(files: AgentPackFile[]): string {
  return files
    .map((file) => `# ${file.path}\n\n${file.content.trim()}`)
    .join("\n\n" + "=".repeat(80) + "\n\n");
}

export default function AgentPacksPage() {
  const provider = agentPackProviders[0];
  const [request, setRequest] = useState<AgentPackRequest>(DEFAULT_REQUEST);
  const [manifest, setManifest] = useState<AgentPackManifest | null>(null);
  const [activeKind, setActiveKind] = useState<AgentPackFileKind | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedState, setCopiedState] = useState<"single" | "all" | null>(null);

  const previewGroups = useMemo(() => {
    if (!manifest) return [];
    return manifest.preview_order
      .map((kind) => ({
        kind,
        label: PREVIEW_LABELS[kind] ?? kind,
        files: manifest.files.filter((file) => file.kind === kind),
      }))
      .filter((group) => group.files.length > 0);
  }, [manifest]);

  const activeGroup = previewGroups.find((group) => group.kind === activeKind) ?? previewGroups[0] ?? null;
  const currentFile =
    activeGroup?.files.find((file) => file.path === selectedPath) ??
    activeGroup?.files[0] ??
    null;

  const handleFieldChange = <K extends keyof AgentPackRequest>(key: K, value: AgentPackRequest[K]) => {
    setRequest((prev) => ({ ...prev, [key]: value }));
  };

  const handleGenerate = async () => {
    if (!request.goal.trim()) return;

    setLoading(true);
    setError(null);
    setManifest(null);
    setActiveKind(null);
    setSelectedPath(null);

    try {
      const data = await apiJson<AgentPackManifest>("/agent-packs/claude", {
        method: "POST",
        headers: buildGeneratorApiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(request),
      });
      setManifest(data);
      setActiveKind(data.preview_order[0] ?? null);
      setSelectedPath(data.files[0]?.path ?? null);
    } catch (err: unknown) {
      showError(err);
      setError(err instanceof Error ? err.message : "Failed to generate agent pack.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyCurrent = async () => {
    if (!currentFile) return;
    await navigator.clipboard.writeText(currentFile.content);
    setCopiedState("single");
    setTimeout(() => setCopiedState(null), 1800);
  };

  const handleCopyAll = async () => {
    if (!manifest) return;
    await navigator.clipboard.writeText(bundleFiles(manifest.files));
    setCopiedState("all");
    setTimeout(() => setCopiedState(null), 1800);
  };

  const handleDownload = async () => {
    if (!request.goal.trim()) return;

    setDownloading(true);
    setError(null);
    try {
      const response = await apiFetch("/agent-packs/claude/download", {
        method: "POST",
        headers: buildGeneratorApiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(payload.detail ?? "Download failed.");
      }

      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const filename = getDownloadFilename(response, `${manifest?.download_name || "agent-pack"}.zip`);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(href);
    } catch (err: unknown) {
      showError(err);
      setError(err instanceof Error ? err.message : "Failed to download agent pack.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-start overflow-x-hidden bg-[#050505] p-3 py-4 sm:p-4 md:h-full md:min-h-0 md:justify-center md:overflow-hidden md:p-8">
      <div className="absolute left-[-5%] top-[-8%] h-[36vw] w-[36vw] rounded-full bg-cyan-500/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-12%] right-[-5%] h-[36vw] w-[36vw] rounded-full bg-blue-600/10 blur-[140px] pointer-events-none" />

      <div className="glass flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col overflow-hidden rounded-2xl bg-black/40 shadow-2xl ring-1 ring-white/10 backdrop-blur-xl animate-fade-in md:h-full md:max-h-[90vh] md:rounded-3xl">
        <header className="flex flex-col gap-3 border-b border-white/5 bg-black/20 p-4 backdrop-blur-md sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${provider.accentClass} text-white shadow-lg shadow-cyan-500/20`}>
              <FolderArchive size={18} aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-white">Agent Packs</h1>
              <div className="font-mono text-xs uppercase tracking-wider text-zinc-400 opacity-70">
                One-Click Repo Assets
              </div>
            </div>
            <InfoButton
              title="Agent Packs"
              description="Turn one short brief into runnable repo-ready assets. V1 focuses on Claude, while the architecture stays open for future providers."
            />
          </div>

          <div className="flex items-center gap-2 self-start rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-200 sm:self-auto">
            <Sparkles size={14} aria-hidden="true" />
            {provider.name} {provider.badge}
          </div>
        </header>

        <div className="flex flex-1 flex-col overflow-visible md:min-h-0 md:flex-row md:overflow-hidden">
          <section className="flex w-full flex-col gap-4 border-b border-white/5 bg-black/10 p-4 sm:p-5 md:min-h-0 md:w-[38%] md:border-b-0 md:border-r md:overflow-y-auto">
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <div className="mb-1 text-[11px] font-mono uppercase tracking-[0.25em] text-cyan-300/80">
                    {provider.name}
                  </div>
                  <h2 className="text-xl font-semibold text-white">Generate runnable agent assets for your repo</h2>
                </div>
                <div className={`h-12 w-12 rounded-2xl ${provider.glowClass} flex items-center justify-center`}>
                  <Bot size={22} className="text-cyan-200" aria-hidden="true" />
                </div>
              </div>
              <p className="text-sm leading-relaxed text-zinc-400">{provider.summary}</p>
            </div>

            <button
              type="button"
              className={`group flex items-center justify-between rounded-2xl border border-white/10 p-4 text-left transition-all hover:border-cyan-400/30 hover:bg-white/[0.05] ${manifest ? "bg-white/[0.05]" : "bg-white/[0.02]"}`}
              aria-label="Claude provider card"
            >
              <div>
                <div className="mb-1 text-sm font-semibold text-white">{provider.name}</div>
                <div className="text-xs text-zinc-500">V1 provider. More ecosystems can slot into this registry later.</div>
              </div>
              <div className={`rounded-xl bg-gradient-to-br ${provider.accentClass} px-3 py-2 text-xs font-semibold text-white shadow-lg shadow-cyan-500/10`}>
                Ready
              </div>
            </button>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-2">
                <span className="text-sm font-medium text-zinc-300">Project Type</span>
                <input
                  value={request.project_type}
                  onChange={(event) => handleFieldChange("project_type", event.target.value)}
                  className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-zinc-200 outline-none transition focus:ring-1 focus:ring-cyan-500/50"
                  placeholder="SaaS, CLI, internal tool..."
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-sm font-medium text-zinc-300">Stack</span>
                <input
                  value={request.stack}
                  onChange={(event) => handleFieldChange("stack", event.target.value)}
                  className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-zinc-200 outline-none transition focus:ring-1 focus:ring-cyan-500/50"
                  placeholder="React, FastAPI, Node..."
                />
              </label>
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="agent-pack-goal" className="text-sm font-medium text-zinc-300">
                What should Claude do?
              </label>
              <textarea
                id="agent-pack-goal"
                value={request.goal}
                onChange={(event) => handleFieldChange("goal", event.target.value)}
                className="min-h-36 rounded-2xl border border-white/10 bg-black/20 p-4 font-mono text-sm leading-relaxed text-zinc-200 shadow-inner transition placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
                placeholder="e.g. Review PRs for prompt leakage, unsafe settings, and missing regression tests."
              />
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium text-zinc-300">Pack Type</span>
              <div className="grid gap-2">
                {PACK_OPTIONS.map((option) => {
                  const active = request.pack_type === option.id;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => handleFieldChange("pack_type", option.id)}
                      className={`rounded-2xl border px-4 py-3 text-left transition-all ${
                        active
                          ? "border-cyan-400/50 bg-cyan-500/10 text-white shadow-lg shadow-cyan-500/10"
                          : "border-white/8 bg-white/[0.02] text-zinc-400 hover:border-white/15 hover:bg-white/[0.04]"
                      }`}
                    >
                      <div className="mb-1 text-sm font-semibold">{option.label}</div>
                      <div className="text-xs leading-relaxed text-inherit/80">{option.detail}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium text-zinc-300">Risk Mode</span>
              <div className="grid gap-2 sm:grid-cols-2">
                {RISK_OPTIONS.map((option) => {
                  const active = request.risk_mode === option.id;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => handleFieldChange("risk_mode", option.id)}
                      className={`rounded-xl border px-4 py-3 text-left transition-all ${
                        active
                          ? "border-cyan-400/40 bg-cyan-500/10 text-white"
                          : "border-white/8 bg-white/[0.02] text-zinc-400 hover:border-white/15"
                      }`}
                    >
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        {option.id === "strict" ? <ShieldCheck size={15} aria-hidden="true" /> : <Sparkles size={15} aria-hidden="true" />}
                        {option.label}
                      </div>
                      <div className="mt-1 text-xs text-inherit/80">{option.detail}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            <button
              type="button"
              onClick={handleGenerate}
              disabled={loading || !request.goal.trim()}
              className={`mt-1 flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-bold text-white shadow-lg transition-all active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 ${provider.buttonClass}`}
            >
              {loading ? "Generating..." : provider.ctaLabel}
            </button>

            {error && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
                {error}
              </div>
            )}
          </section>

          <section className="relative flex min-h-[380px] w-full flex-col bg-black/20 md:min-h-0 md:w-[62%]">
            {manifest ? (
              <div className="flex min-h-0 flex-1 flex-col">
                <div className="flex flex-col gap-3 border-b border-white/5 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                  <div>
                    <h2 className="text-sm font-semibold tracking-tight text-zinc-100">Pack Preview</h2>
                    <p className="mt-1 text-xs text-zinc-500">
                      {manifest.files.length} files grouped for quick review, copy, or download.
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={handleCopyCurrent}
                      className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-200 transition hover:bg-white/[0.08]"
                    >
                      <Copy size={14} aria-hidden="true" />
                      {copiedState === "single" ? "Copied" : "Copy"}
                    </button>
                    <button
                      type="button"
                      onClick={handleCopyAll}
                      className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-200 transition hover:bg-white/[0.08]"
                    >
                      <FileCode2 size={14} aria-hidden="true" />
                      {copiedState === "all" ? "Copied All" : "Copy All"}
                    </button>
                    <button
                      type="button"
                      onClick={handleDownload}
                      disabled={downloading}
                      className="inline-flex items-center gap-2 rounded-xl border border-cyan-400/20 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:opacity-60"
                    >
                      <Download size={14} aria-hidden="true" />
                      {downloading ? "Preparing..." : "Download Pack"}
                    </button>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 border-b border-white/5 px-4 py-3 sm:px-6">
                  {previewGroups.map((group) => (
                    <button
                      key={group.kind}
                      type="button"
                      onClick={() => {
                        setActiveKind(group.kind);
                        setSelectedPath(group.files[0]?.path ?? null);
                      }}
                      className={`rounded-full border px-3 py-1.5 text-[11px] font-mono uppercase tracking-wide transition-all ${
                        activeGroup?.kind === group.kind
                          ? "border-cyan-400/40 bg-cyan-500/10 text-cyan-100"
                          : "border-transparent bg-white/[0.03] text-zinc-500 hover:bg-white/[0.07] hover:text-zinc-300"
                      }`}
                    >
                      {group.label}
                    </button>
                  ))}
                </div>

                {activeGroup && activeGroup.files.length > 1 && (
                  <div className="px-4 pt-4 sm:px-6">
                    <label htmlFor="agent-pack-file-select" className="sr-only">
                      Preview file
                    </label>
                    <select
                      id="agent-pack-file-select"
                      value={currentFile?.path ?? activeGroup.files[0].path}
                      onChange={(event) => setSelectedPath(event.target.value)}
                      className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
                    >
                      {activeGroup.files.map((file) => (
                        <option key={file.path} value={file.path}>
                          {file.path}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="flex-1 overflow-hidden p-4 sm:p-6">
                  <div className="relative h-full overflow-hidden rounded-2xl border border-white/8 bg-black/35">
                    <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
                      <div className="text-xs font-medium text-zinc-300">{currentFile?.path || "Generated file"}</div>
                      <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">{manifest.provider}</div>
                    </div>
                    <pre className="custom-scrollbar h-full overflow-auto p-4 pb-12 font-mono text-[11px] leading-relaxed text-zinc-300 whitespace-pre">
                      <code>{currentFile?.content || "Choose a generated file to preview it here."}</code>
                    </pre>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center text-zinc-600 opacity-80">
                <div className="relative">
                  <div className="absolute inset-0 rounded-full bg-cyan-500/30 blur-[45px]" />
                  <div className="relative flex h-24 w-24 items-center justify-center rounded-[28px] border border-white/10 bg-gradient-to-br from-zinc-900 to-black shadow-2xl">
                    <FolderArchive size={40} className="text-cyan-300/70" aria-hidden="true" />
                  </div>
                </div>
                <div className="max-w-sm space-y-2">
                  <h3 className="text-lg font-medium text-zinc-200">Single-click pack generation</h3>
                  <p className="text-sm leading-relaxed text-zinc-500">
                    Pick a pack type, describe what Claude should do, then generate a ready-to-review asset bundle on the right.
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
