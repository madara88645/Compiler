"use client";

import { useState, useEffect, useRef } from "react";
import { API_BASE } from "@/config";

type Framework = "claude-sdk" | "langchain" | "langgraph";
type OutputTab = "python" | "yaml";

interface ExportResult {
  python_code: string | null;
  yaml_config: string | null;
}

interface ExportPanelProps {
  systemPrompt: string | null;
  isMultiAgent: boolean;
}

const FRAMEWORKS: { id: Framework; label: string; color: string; activeColor: string }[] = [
  {
    id: "claude-sdk",
    label: "Claude SDK",
    color: "text-zinc-400 border-transparent hover:border-orange-500/40 hover:text-orange-300",
    activeColor: "text-orange-300 border-orange-500/60 bg-orange-500/10",
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
    color: "text-zinc-400 border-transparent hover:border-blue-500/40 hover:text-blue-300",
    activeColor: "text-blue-300 border-blue-500/60 bg-blue-500/10",
  },
];

export default function ExportPanel({ systemPrompt, isMultiAgent }: ExportPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [framework, setFramework] = useState<Framework>("claude-sdk");
  const [outputTab, setOutputTab] = useState<OutputTab>("python");
  const [cache, setCache] = useState<Partial<Record<Framework, ExportResult>>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const prevPromptRef = useRef<string | null>(null);

  // Reset cache when systemPrompt changes
  useEffect(() => {
    if (systemPrompt !== prevPromptRef.current) {
      prevPromptRef.current = systemPrompt;
      setCache({});
      setError(null);
    }
  }, [systemPrompt]);

  const currentResult = cache[framework] ?? null;

  const fetchExport = async (fw: Framework) => {
    if (!systemPrompt) return;
    if (cache[fw]) return; // already fetched

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/agent-generator/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          system_prompt: systemPrompt,
          format: fw,
          output_type: "both",
          is_multi_agent: isMultiAgent,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail ?? `Export failed (${res.status})`);
      }

      const data: ExportResult = await res.json();
      setCache((prev) => ({ ...prev, [fw]: data }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setLoading(false);
    }
  };

  const handleFrameworkClick = (fw: Framework) => {
    setFramework(fw);
    fetchExport(fw);
  };

  const handleToggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    if (next && !cache[framework]) {
      fetchExport(framework);
    }
  };

  const handleCopy = () => {
    const text =
      outputTab === "python" ? currentResult?.python_code : currentResult?.yaml_config;
    if (text) {
      navigator.clipboard.writeText(text).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  const activeFramework = FRAMEWORKS.find((f) => f.id === framework)!;
  const codeContent =
    outputTab === "python" ? currentResult?.python_code : currentResult?.yaml_config;

  if (!systemPrompt) return null;

  return (
    <div className="mt-6 border-t border-white/5 pt-4">
      {/* Toggle header */}
      <button
        onClick={handleToggle}
        className="w-full flex items-center justify-between px-2 py-1 group"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-widest group-hover:text-zinc-200 transition-colors">
            Export
          </span>
          <span className="text-[10px] text-zinc-600 font-mono">
            → framework code
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
        <div className="mt-3 rounded-2xl border border-white/8 bg-black/30 overflow-hidden">
          {/* Framework tabs */}
          <div className="flex gap-1 p-3 border-b border-white/5">
            {FRAMEWORKS.map((fw) => (
              <button
                key={fw.id}
                onClick={() => handleFrameworkClick(fw.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                  framework === fw.id ? fw.activeColor : fw.color
                }`}
              >
                {fw.label}
              </button>
            ))}
          </div>

          {/* Output type tabs */}
          <div className="flex gap-1 px-3 pt-3">
            {(["python", "yaml"] as OutputTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setOutputTab(tab)}
                className={`px-3 py-1 text-[11px] font-mono rounded-md transition-all ${
                  outputTab === tab
                    ? "bg-white/10 text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {tab === "python" ? "Python Code" : "YAML Config"}
              </button>
            ))}
          </div>

          {/* Code area */}
          <div className="relative p-3">
            {loading ? (
              <div className="flex items-center justify-center h-24 text-zinc-500 text-xs animate-pulse">
                Generating {activeFramework.label} export...
              </div>
            ) : error ? (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-300">
                {error}
              </div>
            ) : codeContent ? (
              <div className="relative group/code">
                <pre className="overflow-x-auto overflow-y-auto max-h-72 text-[11px] leading-relaxed font-mono text-zinc-300 bg-black/40 rounded-xl p-4 border border-white/5 whitespace-pre">
                  <code>{codeContent}</code>
                </pre>
                <button
                  onClick={handleCopy}
                  className="absolute top-3 right-3 opacity-0 group-hover/code:opacity-100 focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-blue-500 transition-opacity bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-2.5 py-1.5 rounded-lg text-[10px] font-medium flex items-center gap-1.5 border border-white/10"
                  aria-label="Copy code"
                >
                  {copied ? (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                      Copied!
                    </>
                  ) : (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                      Copy
                    </>
                  )}
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-center h-16 text-zinc-600 text-xs">
                Select a framework above to generate export code
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
