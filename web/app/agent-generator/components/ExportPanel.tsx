"use client";

import { ArrowRight, Download, FolderArchive } from "lucide-react";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, describeRequestError } from "@/config";
import { buildPackZip } from "../../lib/packZip";
import { copyToClipboard } from "../../lib/copyToClipboard";

const AGENT_PACKS_HANDOFF_KEY = "promptc_agent_pack_goal";

type ExportTarget =
  | "claude-agent-sdk"
  | "claude-subagent"
  | "claude-project-pack"
  | "langchain"
  | "langgraph";
type OutputMode = "python" | "typescript" | "markdown";

interface ExportFile {
  path: string;
  content: string;
}

interface ExportResult {
  python_code: string | null;
  yaml_config: string | null;
  code?: string | null;
  files?: ExportFile[];
}

interface ExportPanelProps {
  systemPrompt: string | null;
  isMultiAgent: boolean;
}

const TARGETS: {
  id: ExportTarget;
  label: string;
  color: string;
  activeColor: string;
}[] = [
  {
    id: "claude-agent-sdk",
    label: "Claude Agent SDK",
    color: "text-zinc-400 border-transparent hover:border-orange-500/40 hover:text-orange-300",
    activeColor: "text-orange-300 border-orange-500/60 bg-orange-500/10",
  },
  {
    id: "claude-subagent",
    label: "Claude Subagent",
    color: "text-zinc-400 border-transparent hover:border-amber-500/40 hover:text-amber-300",
    activeColor: "text-amber-300 border-amber-500/60 bg-amber-500/10",
  },
  // Hands off to Agent Packs — the single home for repo-ready file bundles — instead of
  // duplicating file-bundle generation inline (see isAgentPacksHandoff below).
  {
    id: "claude-project-pack",
    label: "Claude Project Pack",
    color: "text-zinc-400 border-transparent hover:border-blue-500/40 hover:text-blue-300",
    activeColor: "text-blue-300 border-blue-500/60 bg-blue-500/10",
  },
  {
    id: "langchain",
    label: "LangChain",
    color: "text-zinc-400 border-transparent hover:border-green-500/40 hover:text-green-300",
    activeColor: "text-green-300 border-green-500/60 bg-green-500/10",
  },
  {
    id: "langgraph",
    label: "LangGraph",
    color: "text-zinc-400 border-transparent hover:border-cyan-500/40 hover:text-cyan-300",
    activeColor: "text-cyan-300 border-cyan-500/60 bg-cyan-500/10",
  },
];

const OUTPUT_OPTIONS: Record<ExportTarget, { id: OutputMode; label: string }[]> = {
  "claude-agent-sdk": [
    { id: "python", label: "Python" },
    { id: "typescript", label: "TypeScript" },
  ],
  "claude-subagent": [{ id: "markdown", label: "Markdown" }],
  "claude-project-pack": [],
  langchain: [{ id: "python", label: "Python" }],
  langgraph: [{ id: "python", label: "Python" }],
};

export default function ExportPanel({ systemPrompt, isMultiAgent }: ExportPanelProps) {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [target, setTarget] = useState<ExportTarget>("claude-agent-sdk");
  const [outputMode, setOutputMode] = useState<OutputMode>("python");
  const [cache, setCache] = useState<Record<string, ExportResult>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const prevPromptRef = useRef<string | null>(null);
  const panelId = useId();

  useEffect(() => {
    if (systemPrompt !== prevPromptRef.current) {
      prevPromptRef.current = systemPrompt;
      setCache({});
      setError(null);
      setTarget("claude-agent-sdk");
      setOutputMode("python");
    }
  }, [systemPrompt]);

  const activeTarget = TARGETS.find((item) => item.id === target)!;
  const isAgentPacksHandoff = target === "claude-project-pack";
  const format = resolveFormat(target, outputMode);
  const currentResult = cache[format] ?? null;
  const outputTabs = OUTPUT_OPTIONS[target];
  const visibleFiles = currentResult?.files ?? [];
  const currentFilePath = visibleFiles.length === 1 ? visibleFiles[0].path : null;

  const currentContent = useMemo(() => {
    if (!currentResult) return null;
    if (outputMode === "python" || outputMode === "typescript") {
      return currentResult.code ?? currentResult.python_code;
    }
    if (outputMode === "markdown") {
      return currentResult.files?.[0]?.content ?? currentResult.code ?? null;
    }
    return null;
  }, [currentResult, outputMode]);

  const currentFiles = currentResult?.files ?? [];

  // Named after the currently selected file's path when the export produced
  // one (e.g. the Claude Subagent markdown file); otherwise a sensible
  // extension is derived from the output mode so raw code exports still
  // download with a runnable filename.
  const downloadFilename = useMemo(() => {
    if (!currentContent) return null;
    const selectedPath = currentFiles[0]?.path;
    if (selectedPath) return selectedPath.split("/").pop() || selectedPath;
    const extension = outputMode === "typescript" ? "ts" : outputMode === "markdown" ? "md" : "py";
    return `${format}.${extension}`;
  }, [currentContent, currentFiles, outputMode, format]);

  const fetchExport = async (nextTarget: ExportTarget, nextMode: OutputMode) => {
    if (!systemPrompt) return;
    const nextFormat = resolveFormat(nextTarget, nextMode);
    if (cache[nextFormat]) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/agent-generator/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          system_prompt: systemPrompt,
          format: nextFormat,
          output_type: nextMode,
          is_multi_agent: isMultiAgent,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail ?? `Export failed (${res.status})`);
      }

      const data: ExportResult = await res.json();
      setCache((prev) => ({ ...prev, [nextFormat]: data }));
    } catch (e: unknown) {
      setError(describeRequestError(e, { fallback: "Export failed." }));
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    if (next && !isAgentPacksHandoff) {
      void fetchExport(target, outputMode);
    }
  };

  const handleTargetClick = (nextTarget: ExportTarget) => {
    setTarget(nextTarget);
    if (nextTarget === "claude-project-pack") {
      // Agent Packs is the single home for file bundles — no export call here.
      return;
    }
    const firstMode = OUTPUT_OPTIONS[nextTarget][0].id;
    setOutputMode(firstMode);
    void fetchExport(nextTarget, firstMode);
  };

  const handleOutputModeClick = (nextMode: OutputMode) => {
    setOutputMode(nextMode);
    void fetchExport(target, nextMode);
  };

  const handleCopy = async () => {
    if (!currentContent) return;
    const success = await copyToClipboard(currentContent);
    if (!success) return;
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleAgentPacksHandoff = () => {
    if (!systemPrompt) return;
    window.localStorage.setItem(AGENT_PACKS_HANDOFF_KEY, systemPrompt);
    router.push("/agent-packs");
  };

  const handleDownloadFile = () => {
    if (!currentContent || !downloadFilename) return;
    downloadBlob(new Blob([currentContent], { type: "text/plain" }), downloadFilename);
  };

  const handleDownloadZip = () => {
    if (currentFiles.length < 2) return;
    downloadBlob(buildPackZip(currentFiles), `${format}-export.zip`);
  };

  if (!systemPrompt) return null;

  return (
    <div className="mt-6 border-t border-white/5 pt-4">
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="w-full flex items-center justify-between px-2 py-1 group"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-widest group-hover:text-zinc-200 transition-colors">
            Export
          </span>
          <span className="text-[10px] text-zinc-600 font-mono">
            -&gt; executable agent target
          </span>
        </div>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`text-zinc-500 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {isOpen && (
        <div id={panelId} className="mt-3 rounded-2xl border border-white/8 bg-black/30 overflow-hidden">
          <div className="flex gap-1 p-3 border-b border-white/5 flex-wrap" role="radiogroup" aria-label="Export Target">
            {TARGETS.map((item) => (
              <button
                type="button"
                key={item.id}
                role="radio"
                aria-checked={target === item.id}
                onClick={() => handleTargetClick(item.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                  target === item.id ? item.activeColor : item.color
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {outputTabs.length > 0 && (
            <div className="flex gap-1 px-3 pt-3 flex-wrap" role="radiogroup" aria-label="Output Format">
              {outputTabs.map((tab) => (
                <button
                  type="button"
                  key={tab.id}
                  role="radio"
                  aria-checked={outputMode === tab.id}
                  onClick={() => handleOutputModeClick(tab.id)}
                  className={`px-3 py-1 text-[11px] font-mono rounded-md transition-all ${
                    outputMode === tab.id
                      ? "bg-white/10 text-zinc-100"
                      : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          <div className="relative p-3">
            {isAgentPacksHandoff ? (
              <div className="flex flex-col items-center gap-3 py-6 px-4 text-center">
                <p className="text-xs leading-relaxed text-zinc-400 max-w-sm">
                  Agent Packs is the single home for repo-ready Claude file bundles — CLAUDE.md,
                  settings, subagents, and workflow assets, generated and reviewed together. Continue
                  there with this agent description carried over.
                </p>
                <button
                  type="button"
                  onClick={handleAgentPacksHandoff}
                  className="inline-flex items-center gap-2 rounded-xl border border-blue-400/30 bg-blue-500/10 px-4 py-2 text-xs font-semibold text-blue-200 transition hover:bg-blue-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                >
                  Continue in Agent Packs
                  <ArrowRight size={13} aria-hidden="true" />
                </button>
              </div>
            ) : loading ? (
              <div className="flex items-center justify-center h-24 text-zinc-500 text-xs animate-pulse">
                Generating {activeTarget.label} export...
              </div>
            ) : error ? (
              <div
                className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-300 flex flex-col items-start gap-2"
                role="alert"
              >
                <p>{error}</p>
                <button
                  type="button"
                  onClick={() => void fetchExport(target, outputMode)}
                  className="rounded-lg border border-red-400/30 bg-red-500/20 px-3 py-1.5 text-[11px] font-medium text-red-100 transition-colors hover:bg-red-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
                >
                  Retry export
                </button>
              </div>
            ) : currentContent ? (
              <div className="relative group/code">
                {currentFilePath && (
                  <div className="mb-2 text-[10px] font-mono text-zinc-500 truncate" title={currentFilePath}>
                    {currentFilePath}
                  </div>
                )}
                <pre className="overflow-x-auto overflow-y-auto max-h-72 text-[11px] leading-relaxed font-mono text-zinc-300 bg-black/40 rounded-xl p-4 border border-white/5 whitespace-pre">
                  <code>{currentContent}</code>
                </pre>
                <div className="absolute top-3 right-3 flex items-center gap-1.5 opacity-0 group-hover/code:opacity-100 focus-within:opacity-100 transition-opacity">
                  {currentFiles.length > 1 && (
                    <button
                      type="button"
                      onClick={handleDownloadZip}
                      className="focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-2.5 py-1.5 rounded-lg text-[10px] font-medium flex items-center gap-1.5 border border-white/10"
                      aria-label="Download .zip"
                      title="Download all exported files as a .zip"
                    >
                      <FolderArchive size={12} aria-hidden="true" />
                      .zip
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleDownloadFile}
                    disabled={!downloadFilename}
                    className="focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-2.5 py-1.5 rounded-lg text-[10px] font-medium flex items-center gap-1.5 border border-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label="Download file"
                    title={downloadFilename ? `Download ${downloadFilename}` : "Download file"}
                  >
                    <Download size={12} aria-hidden="true" />
                    Download
                  </button>
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-2.5 py-1.5 rounded-lg text-[10px] font-medium flex items-center gap-1.5 border border-white/10"
                    aria-label={copied ? "Copied to clipboard" : "Copy code"}
                  >
                    <span className="sr-only" aria-live="polite">
                      {copied ? "Copied to clipboard" : ""}
                    </span>
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-16 text-zinc-600 text-xs">
                Select a target above to generate export code
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function resolveFormat(target: ExportTarget, outputMode: OutputMode): string {
  if (target === "claude-agent-sdk") {
    return outputMode === "typescript" ? "claude-agent-sdk-ts" : "claude-agent-sdk-py";
  }
  if (target === "claude-subagent") return "claude-subagent";
  if (target === "claude-project-pack") return "claude-project-pack";
  if (target === "langgraph") return "langgraph";
  return "langchain";
}

/** Trigger a browser download for the given blob, then release the object URL. */
function downloadBlob(blob: Blob, filename: string) {
  const href = URL.createObjectURL(blob);
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
}
