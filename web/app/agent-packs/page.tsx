"use client";

import { toast } from "sonner";

import { useEffect, useMemo, useState } from "react";
import { Bot, Copy, Download, FileCode2, FolderArchive, Loader2, ShieldCheck, Sparkles, X } from "lucide-react";

import { apiJson, buildGeneratorApiHeaders, describeRequestError } from "@/config";
import InfoButton from "../components/InfoButton";
import { showError } from "../lib/showError";
import FileTree from "./components/FileTree";
import InstallChecklist from "./components/InstallChecklist";
import { buildInstallChecklist } from "./installChecklist";
import { buildPackZip } from "./lib/packZip";
import { agentPackProviders } from "./providerRegistry";
import type {
  AgentPackFile,
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

function bundleFiles(files: AgentPackFile[]): string {
  return files
    .map((file) => `# ${file.path}\n\n${file.content.trim()}`)
    .join("\n\n" + "=".repeat(80) + "\n\n");
}

export default function AgentPacksPage() {
  const provider = agentPackProviders[0];
  const [request, setRequest] = useState<AgentPackRequest>(() => {
    if (typeof window === "undefined") {
      return DEFAULT_REQUEST;
    }
    const handoffGoal = window.localStorage.getItem("promptc_agent_pack_goal");
    return handoffGoal ? { ...DEFAULT_REQUEST, goal: handoffGoal } : DEFAULT_REQUEST;
  });
  const [manifest, setManifest] = useState<AgentPackManifest | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedState, setCopiedState] = useState<"single" | "all" | null>(null);
  const [downloaded, setDownloaded] = useState(false);
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());

  // Clear the handoff key once we've read it so a stale value doesn't leak
  // into a later, unrelated visit to this page.
  useEffect(() => {
    window.localStorage.removeItem("promptc_agent_pack_goal");
  }, []);

  const requestHeaders = useMemo(
    () => buildGeneratorApiHeaders({ "Content-Type": "application/json" }),
    [],
  );

  const currentFile = useMemo(() => {
    if (!manifest) return null;
    return manifest.files.find((file) => file.path === selectedPath) ?? manifest.files[0] ?? null;
  }, [manifest, selectedPath]);

  const installChecklist = useMemo(() => {
    if (!manifest) return [];
    return buildInstallChecklist(manifest, { downloaded });
  }, [manifest, downloaded]);

  const handleFieldChange = <K extends keyof AgentPackRequest>(key: K, value: AgentPackRequest[K]) => {
    setRequest((prev) => ({ ...prev, [key]: value }));
  };

  const toggleChecklistItem = (id: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleGenerate = async () => {
    if (!request.goal.trim()) return;

    setLoading(true);
    setError(null);
    setManifest(null);
    setSelectedPath(null);
    setDownloaded(false);
    setCheckedIds(new Set());

    try {
      const data = await apiJson<AgentPackManifest>("/agent-packs/claude", {
        method: "POST",
        headers: requestHeaders,
        body: JSON.stringify(request),
      });
      setManifest(data);
      setSelectedPath(data.files[0]?.path ?? null);
    } catch (err: unknown) {
      showError(err);
      setError(describeRequestError(err, { fallback: "Failed to generate agent pack." }));
    } finally {
      setLoading(false);
    }
  };

  const handleCopyCurrent = async () => {
    if (!currentFile) return;
    await navigator.clipboard.writeText(currentFile.content);
    toast.success("Copied to clipboard");
    setCopiedState("single");
    setTimeout(() => setCopiedState(null), 1800);
  };

  const handleCopyAll = async () => {
    if (!manifest) return;
    await navigator.clipboard.writeText(bundleFiles(manifest.files));
    toast.success("Copied to clipboard");
    setCopiedState("all");
    setTimeout(() => setCopiedState(null), 1800);
  };

  const handleClosePreview = () => {
    setManifest(null);
    setSelectedPath(null);
    setCopiedState(null);
    setDownloaded(false);
    setCheckedIds(new Set());
  };

  const handleDownloadFile = (file: AgentPackFile) => {
    const blob = new Blob([file.content], { type: "text/plain" });
    const href = URL.createObjectURL(blob);
    const basename = file.path.split("/").pop() || "file";
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = basename;
    anchor.rel = "noopener";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(href), 0);
  };

  const handleDownload = () => {
    if (!manifest || manifest.files.length === 0) return;

    setDownloading(true);
    setError(null);
    try {
      const blob = buildPackZip(manifest.files);
      const href = URL.createObjectURL(blob);
      const filename = `${manifest.download_name || "agent-pack"}.zip`;
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = filename;
      anchor.rel = "noopener";
      anchor.style.display = "none";
      // The anchor must be in the document for the synthetic click to trigger a
      // download in Firefox, and the object URL must outlive the click — revoking
      // it synchronously cancels the download in Chromium-based browsers.
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(href), 0);
      setDownloaded(true);
    } catch (err: unknown) {
      showError(err);
      setError(describeRequestError(err, { fallback: "Failed to download agent pack." }));
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
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold tracking-tight text-white">Agent Packs</h1>
                <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-200">
                  Beta
                </span>
              </div>
              <div className="font-mono text-xs uppercase tracking-wider text-zinc-400 opacity-70">
                One-Click Repo Assets
              </div>
            </div>
            <InfoButton
              title="Agent Packs"
              description="Turn one short brief into runnable, repo-ready assets. This beta focuses on Claude first, and every generated file should be reviewed before production use."
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
                  <h2 className="text-xl font-semibold text-white">Generate agent assets for your repo</h2>
                </div>
                <div className={`h-12 w-12 rounded-2xl ${provider.glowClass} flex items-center justify-center`}>
                  <Bot size={22} className="text-cyan-200" aria-hidden="true" />
                </div>
              </div>
              <p className="text-sm leading-relaxed text-zinc-400">{provider.summary}</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="agent-pack-project-type" className="text-sm font-medium text-zinc-300">
                  Project Type
                </label>
                <p id="agent-pack-project-type-hint" className="text-xs leading-relaxed text-zinc-500">
                  The kind of app you&apos;re building — this shapes the tone and sensible defaults of the generated files.
                </p>
                <input
                  id="agent-pack-project-type"
                  aria-describedby="agent-pack-project-type-hint"
                  value={request.project_type}
                  onChange={(event) => handleFieldChange("project_type", event.target.value)}
                  className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-zinc-200 outline-none transition focus:ring-1 focus:ring-cyan-500/50"
                  placeholder="SaaS, CLI, internal tool..."
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="agent-pack-stack" className="text-sm font-medium text-zinc-300">
                  Stack
                </label>
                <p id="agent-pack-stack-hint" className="text-xs leading-relaxed text-zinc-500">
                  Your main languages or frameworks, so the generated files match your setup.
                </p>
                <input
                  id="agent-pack-stack"
                  aria-describedby="agent-pack-stack-hint"
                  value={request.stack}
                  onChange={(event) => handleFieldChange("stack", event.target.value)}
                  className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-zinc-200 outline-none transition focus:ring-1 focus:ring-cyan-500/50"
                  placeholder="React, FastAPI, Node..."
                />
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="agent-pack-goal" className="text-sm font-medium text-zinc-300">
                What should Claude do?
              </label>
              <div className="relative group">
              <textarea
                id="agent-pack-goal"
                aria-label="Agent Pack Goal"
                value={request.goal}
                onChange={(event) => handleFieldChange("goal", event.target.value)}
                className="min-h-36 rounded-2xl border border-white/10 bg-black/20 p-4 font-mono text-sm leading-relaxed text-zinc-200 shadow-inner transition placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
                placeholder="e.g. Review PRs for prompt leakage, unsafe settings, and missing regression tests."
              />

            {request.goal && (
              <button
                type="button"
                onClick={() => handleFieldChange("goal", "")}
                className="absolute top-2 right-2 text-xs text-zinc-500 hover:text-zinc-300 bg-black/40 hover:bg-black/60 px-2 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500/50"
                title="Clear input"
                aria-label="Clear input"
              >
                Clear
              </button>
            )}
            </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium text-zinc-300">Pack Type</span>
              <div className="grid gap-2" role="radiogroup" aria-label="Pack Type">
                {PACK_OPTIONS.map((option) => {
                  const active = request.pack_type === option.id;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => handleFieldChange("pack_type", option.id)}
                      className={`rounded-2xl border px-4 py-3 text-left transition-all ${
                        active
                          ? "border-cyan-400/50 bg-cyan-500/10 text-white shadow-lg shadow-cyan-500/10"
                          : "border-white/10 bg-white/[0.05] text-zinc-300 hover:border-white/20 hover:bg-white/[0.08]"
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
              <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Risk Mode">
                {RISK_OPTIONS.map((option) => {
                  const active = request.risk_mode === option.id;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      role="radio"
                      aria-checked={active}
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
              aria-busy={loading}
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
            {loading ? (
              <div
                className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center"
                role="status"
                aria-live="polite"
              >
                <div className="relative">
                  <div className="absolute inset-0 rounded-full bg-cyan-500/30 blur-[45px]" />
                  <div className="relative flex h-24 w-24 items-center justify-center rounded-[28px] border border-white/10 bg-gradient-to-br from-zinc-900 to-black shadow-2xl">
                    <Loader2 size={40} className="animate-spin text-cyan-300/80" aria-hidden="true" />
                  </div>
                </div>
                <div className="max-w-sm space-y-2">
                  <h3 className="text-lg font-medium text-zinc-200">Generating your agent pack…</h3>
                  <p className="text-sm leading-relaxed text-zinc-500">
                    Claude is drafting and assembling your repo-ready files. This usually takes around
                    20–30 seconds — keep this tab open while it finishes.
                  </p>
                </div>
              </div>
            ) : manifest ? (
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
                      className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-200 transition hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
                    >
                      <span className="sr-only" aria-live="polite">{copiedState === "single" ? "Copied to clipboard" : ""}</span>
                      <Copy size={14} aria-hidden="true" />
                      {copiedState === "single" ? "Copied" : "Copy"}
                    </button>
                    <button
                      type="button"
                      onClick={handleCopyAll}
                      className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-200 transition hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
                    >
                      <span className="sr-only" aria-live="polite">{copiedState === "all" ? "Copied All to clipboard" : ""}</span>
                      <FileCode2 size={14} aria-hidden="true" />
                      {copiedState === "all" ? "Copied All" : "Copy All"}
                    </button>
                    <button
                      type="button"
                      onClick={handleDownload}
                      disabled={downloading}
                      aria-busy={downloading}
                      className="inline-flex items-center gap-2 rounded-xl border border-cyan-400/20 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
                    >
                      <Download size={14} aria-hidden="true" />
                      {downloading ? "Preparing..." : "Download Pack"}
                    </button>
                    <button
                      type="button"
                      onClick={handleClosePreview}
                      aria-label="Close pack preview"
                      className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-300 transition hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
                    >
                      <X size={14} aria-hidden="true" />
                      Close
                    </button>
                  </div>
                </div>

                <InstallChecklist
                  sections={installChecklist}
                  checkedIds={checkedIds}
                  onToggle={toggleChecklistItem}
                  downloaded={downloaded}
                />

                <div className="border-b border-white/5 px-4 py-3 sm:px-6">
                  <div className="mb-2 text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500">
                    Files
                  </div>
                  <FileTree
                    files={manifest.files}
                    selectedPath={currentFile?.path ?? null}
                    onSelect={setSelectedPath}
                    onDownloadFile={handleDownloadFile}
                  />
                </div>

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
                  <div className="flex flex-col items-center gap-3 mt-6 w-full">
                    <button
                      type="button"
                      onClick={handleGenerate}
                      disabled={loading || !request.goal.trim()}
                      aria-busy={loading}
                      title={!request.goal.trim() ? "Enter a goal first to generate" : provider.ctaLabel}
                      className={`mx-auto flex items-center justify-center gap-2 rounded-2xl px-6 py-2.5 text-sm font-bold text-white shadow-lg transition-all active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a1a1a] ${provider.buttonClass}`}
                    >
                      {provider.ctaLabel}
                    </button>
                    {!request.goal.trim() && (
                      <button
                        type="button"
                        onClick={() => {
                          handleFieldChange("goal", "Review PRs for prompt leakage, unsafe settings, and missing regression tests.");
                          setTimeout(() => {
                            const textarea = document.getElementById('agent-pack-goal');
                            if (textarea) textarea.focus();
                          }, 0);
                        }}
                        className="text-xs text-cyan-400/80 hover:text-cyan-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 rounded px-2 py-1"
                      >
                        or try an example
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
