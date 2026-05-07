"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { apiFetch } from "@/config";

type ExportTarget =
  | "claude-agent-sdk"
  | "claude-subagent"
  | "claude-project-pack"
  | "langchain"
  | "langgraph";
type OutputMode = "python" | "typescript" | "markdown" | "files";

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
  "claude-project-pack": [{ id: "files", label: "Files" }],
  langchain: [{ id: "python", label: "Python" }],
  langgraph: [{ id: "python", label: "Python" }],
};

export default function ExportPanel({ systemPrompt, isMultiAgent }: ExportPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [target, setTarget] = useState<ExportTarget>("claude-agent-sdk");
  const [outputMode, setOutputMode] = useState<OutputMode>("python");
  const [cache, setCache] = useState<Record<string, ExportResult>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const prevPromptRef = useRef<string | null>(null);
  const panelId = useId();

  useEffect(() => {
    if (systemPrompt !== prevPromptRef.current) {
      prevPromptRef.current = systemPrompt;
      setCache({});
      setError(null);
      setSelectedFilePath(null);
      setTarget("claude-agent-sdk");
      setOutputMode("python");
    }
  }, [systemPrompt]);

  const activeTarget = TARGETS.find((item) => item.id === target)!;
  const format = resolveFormat(target, outputMode);
  const currentResult = cache[format] ?? null;
  const outputTabs = OUTPUT_OPTIONS[target];

  const currentContent = useMemo(() => {
    if (!currentResult) return null;
    if (outputMode === "python" || outputMode === "typescript") {
      return currentResult.code ?? currentResult.python_code;
    }
    if (outputMode === "markdown") {
      return currentResult.files?.[0]?.content ?? currentResult.code ?? null;
    }
    if (outputMode === "files") {
      const files = currentResult.files ?? [];
      if (!files.length) return null;
      const selected = files.find((file) => file.path === selectedFilePath) ?? files[0];
      return selected.content;
    }
    return null;
  }, [currentResult, outputMode, selectedFilePath]);

  const visibleFiles = currentResult?.files ?? [];

  const fetchExport = async (nextTarget: ExportTarget, nextMode: OutputMode) => {
    if (!systemPrompt) return;
    const nextFormat = resolveFormat(nextTarget, nextMode);
    if (cache[nextFormat]) {
      const files = cache[nextFormat].files ?? [];
      if (files.length && !selectedFilePath) {
        setSelectedFilePath(files[0].path);
      }
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
      const files = data.files ?? [];
      if (files.length) {
        setSelectedFilePath(files[0].path);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    if (next) {
      void fetchExport(target, outputMode);
    }
  };

  const handleTargetClick = (nextTarget: ExportTarget) => {
    const firstMode = OUTPUT_OPTIONS[nextTarget][0].id;
    setTarget(nextTarget);
    setOutputMode(firstMode);
    void fetchExport(nextTarget, firstMode);
  };

  const handleOutputModeClick = (nextMode: OutputMode) => {
    setOutputMode(nextMode);
    void fetchExport(target, nextMode);
  };

  const handleCopy = () => {
    if (!currentContent) return;
    navigator.clipboard.writeText(currentContent).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
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
          <div className="flex gap-1 p-3 border-b border-white/5 flex-wrap">
            {TARGETS.map((item) => (
              <button
                type="button"
                key={item.id}
                onClick={() => handleTargetClick(item.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                  target === item.id ? item.activeColor : item.color
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="flex gap-1 px-3 pt-3 flex-wrap">
            {outputTabs.map((tab) => (
              <button
                type="button"
                key={tab.id}
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

          {visibleFiles.length > 1 && (
            <div className="px-3 pt-3">
              <label htmlFor="agent-export-file" className="sr-only">
                Exported file
              </label>
              <select
                id="agent-export-file"
                value={selectedFilePath ?? visibleFiles[0].path}
                onChange={(event) => setSelectedFilePath(event.target.value)}
                className="w-full bg-black/20 border border-white/10 text-zinc-300 text-xs rounded-xl px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
              >
                {visibleFiles.map((file) => (
                  <option key={file.path} value={file.path}>
                    {file.path}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="relative p-3">
            {loading ? (
              <div className="flex items-center justify-center h-24 text-zinc-500 text-xs animate-pulse">
                Generating {activeTarget.label} export...
              </div>
            ) : error ? (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-300">
                {error}
              </div>
            ) : currentContent ? (
              <div className="relative group/code">
                <pre className="overflow-x-auto overflow-y-auto max-h-72 text-[11px] leading-relaxed font-mono text-zinc-300 bg-black/40 rounded-xl p-4 border border-white/5 whitespace-pre">
                  <code>{currentContent}</code>
                </pre>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="absolute top-3 right-3 opacity-0 group-hover/code:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 transition-opacity bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-2.5 py-1.5 rounded-lg text-[10px] font-medium flex items-center gap-1.5 border border-white/10"
                  aria-label="Copy code"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
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
