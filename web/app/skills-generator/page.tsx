"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Zap } from "lucide-react";
import { apiJson, buildGeneratorApiHeaders } from "@/config";
import { showError } from "../lib/showError";
import InfoButton from "../components/InfoButton";
import ContextManager from "../components/ContextManager";
import SkillExportPanel from "./components/ExportPanel";

export default function SkillsGenerator() {
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeExampleCode, setIncludeExampleCode] = useState(false);
  const [history, setHistory] = useState<{ label: string; skill: string }[]>([]);
  const [copied, setCopied] = useState(false);

  const isGeneratingRef = useRef(false);

  const handleGenerate = async () => {
    if (!description.trim()) return;
    if (isGeneratingRef.current) return;
    isGeneratingRef.current = true;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await apiJson<{ skill_definition: string }>("/skills-generator/generate", {
        method: "POST",
        headers: buildGeneratorApiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          description,
          include_example_code: includeExampleCode,
        }),
      });

      setResult(data.skill_definition);
      setHistory((prev) => [
        {
          label: description.slice(0, 40) + (includeExampleCode ? " [code]" : " [plain]"),
          skill: data.skill_definition,
        },
        ...prev,
      ].slice(0, 5));
    } catch (e: unknown) {
      showError(e);
      setError(e instanceof Error ? e.message : "Failed to generate skill");
    } finally {
      setLoading(false);
      isGeneratingRef.current = false;
    }
  };

  const copyToClipboard = () => {
    if (result) {
      navigator.clipboard.writeText(result);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <main className="flex h-full min-h-0 flex-col items-center justify-center p-4 md:p-8 relative overflow-hidden bg-[#050505]">
      {/* Ambient Background */}
      <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-yellow-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-orange-600/10 blur-[120px] pointer-events-none" />

      {/* Main Container */}
      <div className="glass w-full max-w-7xl h-full max-h-[90vh] rounded-3xl flex flex-col shadow-2xl overflow-hidden animate-fade-in ring-1 ring-white/10 bg-black/40 backdrop-blur-xl">

        {/* Header */}
        <header className="border-b border-white/5 bg-black/20 p-4 flex items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 bg-gradient-to-br from-yellow-600 to-orange-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-yellow-500/20">
                <Zap size={18} aria-hidden="true" />
              </div>
              <div>
                <h1 className="font-semibold text-lg tracking-tight text-white">Skills Generator</h1>
                <div className="text-xs text-zinc-400 font-mono tracking-wider uppercase opacity-70">
                  Capability Architect
                </div>
              </div>
            </div>
            <InfoButton
              title="Skill Generator"
              description="Describe a capability, and this tool will generate a structured Tool/Skill definition (with input/output schemas) that can be integrated into your AI agents."
            />
          </div>
        </header>

        <div className="flex-1 min-h-0 flex flex-col md:flex-row overflow-hidden">
          {/* Left Panel: Input */}
          <div className="w-full md:w-[35%] min-h-0 p-5 flex flex-col gap-5 border-r border-white/5 bg-black/10 overflow-hidden">
            <div className="flex flex-col gap-2">
              <label htmlFor="skill-description" className="text-sm font-medium text-zinc-300">Skill Description</label>
              <p className="text-xs text-zinc-500">
                Describe the skill&apos;s purpose, inputs, and expected behavior.
              </p>
            </div>

            <div className="flex-1 min-h-0 flex flex-col relative group">
              <textarea
                id="skill-description"
                aria-label="Skill Description"
                className="flex-1 min-h-[240px] md:min-h-0 w-full bg-black/20 p-5 rounded-2xl border border-white/10 resize-none focus:outline-none focus:ring-1 focus:ring-yellow-500/50 font-mono text-sm leading-relaxed text-zinc-200 placeholder-zinc-600 transition-all shadow-inner"
                placeholder="e.g., 'A skill that parses JSON and validates schemas' or 'Fetch and summarize web pages'"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onKeyDown={(e) => {
                  if (e.repeat) return;
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                    e.preventDefault();
                    if (!loading && description.trim()) {
                      void handleGenerate();
                    }
                  }
                }}
              />
            </div>

            <div className="flex items-center gap-3 bg-white/5 p-3 rounded-xl border border-white/5">
              <button
                type="button"
                role="switch"
                aria-checked={includeExampleCode}
                aria-label="Include Example Code toggle"
                onClick={() => setIncludeExampleCode((v) => !v)}
                className={`w-10 h-6 rounded-full flex items-center p-1 cursor-pointer transition-colors ${includeExampleCode ? "bg-blue-500" : "bg-zinc-700"} focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none`}
              >
                <div className={`w-4 h-4 bg-white rounded-full shadow-sm transform transition-transform ${includeExampleCode ? "translate-x-4" : "translate-x-0"}`} />
              </button>
              <div className="flex flex-col">
                <span className="text-xs font-medium text-zinc-200">Example Code?</span>
                <span className="text-xs text-zinc-500">
                  Yes = include implementation code, No = keep it code-free
                </span>
              </div>
            </div>

            {history.length > 0 && (
              <div className="flex flex-col gap-2">
                <label htmlFor="skill-history" className="text-xs font-medium text-zinc-300">Previous results</label>
                <select
                  id="skill-history"
                  className="w-full bg-black/20 border border-white/10 text-zinc-300 text-xs rounded-xl px-3 py-2 focus:outline-none focus:ring-1 focus:ring-yellow-500/50"
                  defaultValue=""
                  onChange={(e) => {
                    const selected = history[Number(e.target.value)];
                    if (selected) {
                      setResult(selected.skill);
                    }
                  }}
                >
                  <option value="" disabled>
                    -- Restore previous result --
                  </option>
                  {history.map((entry, index) => (
                    <option key={`${entry.label}-${index}`} value={index}>
                      {entry.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <button
              type="button"
              onClick={handleGenerate}
              disabled={loading || !description.trim()}
              title={!description.trim() ? "Enter a description first to generate" : "Generate Skill"}
              className="w-full px-4 py-3 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-500 hover:to-orange-500 shadow-yellow-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-yellow-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            >
              {loading ? (
                <span className="animate-pulse">Forging Skill...</span>
              ) : (
                <>Generate Skill <span className="group-hover:translate-x-0.5 transition-transform">→</span> <kbd className="hidden md:inline-block ml-2 text-[10px] font-mono opacity-50 border border-white/20 rounded px-1.5 py-0.5 bg-white/5">Ctrl/⌘ Enter</kbd></>
              )}
            </button>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-300">
                {error}
              </div>
            )}

            {/* Context Manager */}
            <ContextManager
              onInsertContext={(text) => setDescription(prev => prev + "\n\n---\nContext:\n" + text)}
            />
          </div>

          {/* Right Panel: Output */}
          <div className="w-full md:w-[65%] min-h-0 flex flex-col bg-black/20 relative">
            {result ? (
              <div className="flex-1 min-h-0 p-0 overflow-hidden relative group bg-black/20 flex flex-col">
                <div className="flex items-center justify-between border-b border-white/5 px-6 py-3">
                  <h2 className="text-sm font-semibold text-zinc-200 tracking-tight">Skill Definition</h2>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                    {includeExampleCode ? "With Example Code" : "Plain"}
                  </span>
                </div>

                <div className="relative flex-1 min-h-0 overflow-hidden">
                  <div className="absolute inset-0 overflow-y-auto p-6 pb-24 prose prose-invert prose-sm max-w-none prose-headings:text-zinc-100 prose-p:text-zinc-300 prose-li:text-zinc-300 prose-code:text-yellow-300 prose-pre:bg-zinc-900">
                    <ReactMarkdown>{result}</ReactMarkdown>
                    <SkillExportPanel skillDefinition={result} />
                  </div>

                  <button
                    type="button"
                    onClick={copyToClipboard}
                    className="absolute bottom-6 right-6 bg-yellow-600 hover:bg-yellow-500 text-white p-3 rounded-xl shadow-lg shadow-yellow-500/20 transition-all hover:scale-105 active:scale-95 z-20 flex items-center gap-2"
                    title={copied ? "Copied!" : "Copy to Clipboard"}
                    aria-label={copied ? "Copied" : "Copy Markdown"}
                  >
                    <span className="text-xs font-bold">{copied ? "Copied!" : "Copy Markdown"}</span>
                    {copied ? (
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-zinc-600 gap-6 p-10 text-center opacity-60">
                <div className="relative group">
                  <div className="absolute inset-0 bg-yellow-500/30 blur-[40px] rounded-full group-hover:bg-yellow-500/50 transition-all duration-700" />
                  <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-zinc-800 to-black border border-white/10 flex items-center justify-center shadow-2xl skew-y-3 group-hover:skew-y-0 transition-transform duration-500">
                    <Zap size={40} strokeWidth={1.5} aria-hidden="true" className="text-yellow-400/60" />
                  </div>
                </div>
                <div className="max-w-xs space-y-2">
                  <h3 className="text-zinc-200 font-medium tracking-wide">Skill Forge</h3>
                  <p className="text-sm text-zinc-500 mb-4">
                    Define a capability to generate a robust, modular skill definition for your AI agents.
                  </p>
                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={loading || !description.trim()}
                    title={!description.trim() ? "Enter a description first to generate" : "Generate Skill"}
                    className="mt-6 mx-auto px-6 py-2.5 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-500 hover:to-orange-500 shadow-yellow-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-yellow-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a1a1a]"
                  >
                    Generate Skill
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
