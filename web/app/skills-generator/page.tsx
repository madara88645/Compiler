"use client";

import { toast } from "sonner";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Zap } from "lucide-react";
import { apiJson, buildGeneratorApiHeaders } from "@/config";
import type { GitHubRepoContextPayload, SkillGeneratorResponse } from "@/lib/api/types";
import { withTimeout } from "@/lib/promise/withTimeout";
import { showError } from "../lib/showError";
import InfoButton from "../components/InfoButton";
import ContextManager from "../components/ContextManager";
import RepoContextPreviewCard from "../components/RepoContextPreviewCard";
import SkillExportPanel from "./components/ExportPanel";
import GeneratorErrorState from "../components/GeneratorErrorState";

const REPO_ANALYSIS_TIMEOUT_MS = 15000;
function isSupportedGitHubRepoRootUrl(value: string): boolean {
  return /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/.test(value.trim());
}

type SkillGenerationView = {
  content: string;
  exampleCodeRequested: boolean;
  exampleCodePresent: boolean;
  exampleCodeWarning: string | null;
};

function toSkillGenerationView(response: SkillGeneratorResponse): SkillGenerationView {
  return {
    content: response.skill_definition,
    exampleCodeRequested: response.example_code_requested,
    exampleCodePresent: response.example_code_present,
    exampleCodeWarning: response.example_code_warning,
  };
}

function getExampleCodeStatusLabel(result: SkillGenerationView): string {
  if (!result.exampleCodeRequested) {
    return "Plain";
  }
  return result.exampleCodePresent ? "With Example Code" : "Example Code Missing";
}

export default function SkillsGenerator() {
  const [description, setDescription] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [repoContext, setRepoContext] = useState<GitHubRepoContextPayload | null>(null);
  const [repoAnalysisLoading, setRepoAnalysisLoading] = useState(false);
  const [repoAnalysisWarning, setRepoAnalysisWarning] = useState<string | null>(null);
  const [repoContextDirty, setRepoContextDirty] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SkillGenerationView | null>(null);
  const [lastError, setLastError] = useState<unknown>(null);
  const [includeExampleCode, setIncludeExampleCode] = useState(false);
  const [history, setHistory] = useState<{ label: string; result: SkillGenerationView }[]>([]);
  const [copied, setCopied] = useState(false);

  const isGeneratingRef = useRef(false);
  const isValidRepoUrl = isSupportedGitHubRepoRootUrl(repoUrl);

  const handleAnalyzeRepo = async () => {
    if (!isValidRepoUrl || repoAnalysisLoading) return;

    setRepoAnalysisLoading(true);
    setRepoAnalysisWarning(null);
    setLastError(null);

    try {
      const data = await withTimeout(
        apiJson<GitHubRepoContextPayload>("/repo-context/github", {
          method: "POST",
          headers: buildGeneratorApiHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ repo_url: repoUrl.trim() }),
        }),
        REPO_ANALYSIS_TIMEOUT_MS,
        "Repository analysis is taking too long. Please try again.",
      );
      setRepoContext(data);
      setRepoContextDirty(false);
    } catch (e: unknown) {
      showError(e);
      setRepoContext(null);
      setRepoContextDirty(false);
      setRepoAnalysisWarning(e instanceof Error ? e.message : "Repository analysis failed");
    } finally {
      setRepoAnalysisLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!description.trim()) return;
    if (isGeneratingRef.current) return;
    isGeneratingRef.current = true;

    setLoading(true);
    setLastError(null);
    setResult(null);

    try {
      const data = await apiJson<SkillGeneratorResponse>("/skills-generator/generate", {
        method: "POST",
        headers: buildGeneratorApiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          description,
          include_example_code: includeExampleCode,
          ...(repoContext && !repoContextDirty ? { repo_context: repoContext } : {}),
        }),
      });

      const nextResult = toSkillGenerationView(data);
      setResult(nextResult);
      setHistory((prev) => [
        {
          label: description.slice(0, 40) + (includeExampleCode ? " [code]" : " [plain]"),
          result: nextResult,
        },
        ...prev,
      ].slice(0, 5));
    } catch (e: unknown) {
      showError(e);
      setLastError(e);
    } finally {
      setLoading(false);
      isGeneratingRef.current = false;
    }
  };

  const copyToClipboard = () => {
    if (result) {
      navigator.clipboard.writeText(result.content);
      toast.success("Copied to clipboard");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-start overflow-x-hidden bg-[#050505] p-3 py-4 sm:p-4 md:h-full md:min-h-0 md:justify-center md:overflow-hidden md:p-8">
      {/* Ambient Background */}
      <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-yellow-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-orange-600/10 blur-[120px] pointer-events-none" />

      {/* Main Container */}
      <div className="glass flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col overflow-hidden rounded-2xl bg-black/40 shadow-2xl ring-1 ring-white/10 backdrop-blur-xl animate-fade-in md:h-full md:max-h-[90vh] md:rounded-3xl">

        {/* Header */}
        <header className="flex flex-col gap-3 border-b border-white/5 bg-black/20 p-4 backdrop-blur-md sm:flex-row sm:items-center sm:justify-between">
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
          {!!lastError && !loading && (
            <button
              type="button"
              onClick={() => void handleGenerate()}
              className="w-full rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-yellow-500/50 sm:w-auto"
            >
              Retry
            </button>
          )}
        </header>

        <div className="flex flex-1 flex-col overflow-visible md:min-h-0 md:flex-row md:overflow-hidden">
          {/* Left Panel: Input */}
          <div className="flex w-full flex-col gap-4 border-b border-white/5 bg-black/10 p-4 sm:p-5 md:min-h-0 md:w-[35%] md:border-b-0 md:border-r md:overflow-y-auto">
            <div className="flex flex-col gap-2">
              <label htmlFor="skill-description" className="text-sm font-medium text-zinc-300">Skill Description</label>
              <p className="text-xs text-zinc-500">
                Describe the skill&apos;s purpose, inputs, and expected behavior.
              </p>
            </div>

            {process.env.NEXT_PUBLIC_REPO_CONTEXT_ENABLED === "true" ? (
              <>
                <div className="flex flex-col gap-2">
                  <label htmlFor="skill-repo-url" className="text-sm font-medium text-zinc-300">GitHub Repo URL</label>
                  <p className="text-xs text-zinc-500">
                    Optional. Analyze a public root repo URL to add a compact, deterministic project brief.
                  </p>
                  <input
                    id="skill-repo-url"
                    aria-label="GitHub Repo URL"
                    className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 font-mono text-sm text-zinc-200 transition-all placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-yellow-500/50"
                    placeholder="https://github.com/owner/repo"
                    value={repoUrl}
                    onChange={(e) => {
                      const nextValue = e.target.value;
                      setRepoUrl(nextValue);
                      setRepoAnalysisWarning(null);
                      if (!repoContext) {
                        return;
                      }
                      const normalizedNext = nextValue.trim().replace(/\/+$/, "");
                      const normalizedCurrent = repoContext.normalized_repo_url.replace(/\/+$/, "");
                      const isDirty = normalizedNext !== normalizedCurrent;
                      setRepoContextDirty(isDirty);
                      if (!isDirty) {
                        setRepoAnalysisWarning(null);
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleAnalyzeRepo}
                    disabled={!isValidRepoUrl || repoAnalysisLoading}
                    className="w-full rounded-xl border border-yellow-500/20 bg-yellow-500/10 px-4 py-2.5 text-sm font-semibold text-yellow-100 transition-all hover:bg-yellow-500/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {repoAnalysisLoading ? "Analyzing Repo..." : "Analyze Repo"}
                  </button>
                </div>

                {repoContext && !repoContextDirty ? (
                  <RepoContextPreviewCard repoContext={repoContext} accent="yellow" />
                ) : null}

                {repoContextDirty ? (
                  <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-3 text-xs text-yellow-200">
                    Repo URL changed. Re-analyze to attach fresh repo context.
                  </div>
                ) : null}

                {repoAnalysisWarning ? (
                  <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-3 text-xs text-yellow-200">
                    {repoAnalysisWarning}
                  </div>
                ) : null}
              </>
            ) : null}

            <div className="relative shrink-0 group">
              <label htmlFor="skill-description" className="sr-only">Skill Description</label>
              <textarea
                id="skill-description"
                aria-label="Skill Description"
                className="min-h-36 w-full resize-none rounded-2xl border border-white/10 bg-black/20 p-5 font-mono text-sm leading-relaxed text-zinc-200 shadow-inner transition-all placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-yellow-500/50 sm:min-h-44 md:min-h-[220px]"
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

            {description && (
              <button
                type="button"
                onClick={() => setDescription("")}
                className="absolute top-2 right-2 text-xs text-zinc-500 hover:text-zinc-300 bg-black/40 hover:bg-black/60 px-2 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-yellow-500/50"
                title="Clear input"
                aria-label="Clear input"
              >
                Clear
              </button>
            )}
            </div>

            <button
              type="button"
              role="switch"
              aria-checked={includeExampleCode}
              aria-label="Include Example Code toggle"
              onClick={() => setIncludeExampleCode((v) => !v)}
              className="flex shrink-0 items-center gap-3 rounded-xl border border-white/5 bg-white/5 p-3 text-left transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <span
                aria-hidden="true"
                className={`flex h-6 w-10 items-center rounded-full p-1 transition-colors ${includeExampleCode ? "bg-blue-500" : "bg-zinc-700"}`}
              >
                <span className={`h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${includeExampleCode ? "translate-x-4" : "translate-x-0"}`} />
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="text-xs font-medium text-zinc-200">Example Code?</span>
                <span className="text-xs text-zinc-500">
                  Yes = include implementation code, No = keep it code-free
                </span>
              </span>
            </button>

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
                      setResult(selected.result);
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
              aria-busy={loading}
              title={!description.trim() ? "Enter a description first to generate" : "Generate Skill"}
              className="w-full px-4 py-3 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-500 hover:to-orange-500 shadow-yellow-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-yellow-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            >
              {loading ? (
                <span className="animate-pulse">Forging Skill...</span>
              ) : (
                <>Generate Skill <span className="transition-transform group-hover:translate-x-0.5">{"->"}</span> <kbd className="ml-2 hidden rounded border border-white/20 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] opacity-50 md:inline-block">Ctrl/Cmd Enter</kbd></>
              )}
            </button>

            {/* Context Manager */}
            <ContextManager
              onInsertContext={(text) => setDescription(prev => prev + "\n\n---\nContext:\n" + text)}
            />
          </div>

          {/* Right Panel: Output */}
          <div className="relative flex min-h-[360px] w-full flex-col bg-black/20 md:min-h-0 md:w-[65%]">
            {loading ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 p-10 text-center">
                <span className="animate-pulse text-sm font-medium text-yellow-300/90">Forging skill definition...</span>
                <p className="max-w-xs text-xs text-zinc-500">This can take a moment when the cloud generator is waking up.</p>
              </div>
            ) : lastError ? (
              <GeneratorErrorState
                error={lastError}
                onRetry={() => void handleGenerate()}
                title="Skill generation failed"
                retryLabel="Retry generation"
              />
            ) : result ? (
              <div className="flex-1 min-h-0 p-0 overflow-hidden relative group bg-black/20 flex flex-col">
                <div className="flex items-center justify-between border-b border-white/5 px-6 py-3">
                  <h2 className="text-sm font-semibold text-zinc-200 tracking-tight">Skill Definition</h2>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                    {getExampleCodeStatusLabel(result)}
                  </span>
                </div>

                <div className="relative flex-1 min-h-0 overflow-hidden">
                  <div className="absolute inset-0 overflow-y-auto p-6 pb-24 prose prose-invert prose-sm max-w-none prose-headings:text-zinc-100 prose-p:text-zinc-300 prose-li:text-zinc-300 prose-code:text-yellow-300 prose-pre:bg-zinc-900">
                    {result.exampleCodeWarning ? (
                      <div className="mb-4 rounded-xl border border-yellow-500/20 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-100 not-prose">
                        {result.exampleCodeWarning}
                      </div>
                    ) : null}
                    <ReactMarkdown>{result.content}</ReactMarkdown>
                    <SkillExportPanel skillDefinition={result.content} />
                  </div>

                  <button
                    type="button"
                    onClick={copyToClipboard}
                    className="absolute bottom-6 right-6 bg-yellow-600 hover:bg-yellow-500 text-white p-3 rounded-xl shadow-lg shadow-yellow-500/20 transition-all hover:scale-105 active:scale-95 z-20 flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-yellow-500"
                    title={copied ? "Copied!" : "Copy to Clipboard"}
                    aria-label={copied ? "Copied" : "Copy Markdown"}
                    aria-live="polite"
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
              <div className="flex flex-1 flex-col items-center justify-center gap-5 p-6 text-center text-zinc-600 opacity-75 sm:gap-6 sm:p-10">
                <div className="relative group">
                  <div className="absolute inset-0 bg-yellow-500/30 blur-[40px] rounded-full group-hover:bg-yellow-500/50 transition-all duration-700" />
                  <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-zinc-800 to-black border border-white/10 flex items-center justify-center shadow-2xl skew-y-3 group-hover:skew-y-0 transition-transform duration-500">
                    <Zap size={40} strokeWidth={1.5} aria-hidden="true" className="text-yellow-400/60" />
                  </div>
                </div>
                <div className="max-w-xs space-y-2">
                  <h3 className="text-zinc-200 font-medium tracking-wide">Skill Forge</h3>
                  <p className="text-sm text-zinc-500 mb-4">
                    Describe the capability on the left, choose whether examples belong in it, then generate and copy the skill.
                  </p>
                  <div className="flex flex-col items-center gap-3 mt-6 w-full">
                    <button
                      type="button"
                      onClick={handleGenerate}
                      disabled={loading || !description.trim()}
                      aria-busy={loading}
                      title={!description.trim() ? "Enter a description first to generate" : "Generate Skill"}
                      className="mx-auto px-6 py-2.5 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-500 hover:to-orange-500 shadow-yellow-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-yellow-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a1a1a]"
                    >
                      Generate Skill
                    </button>
                    {!description.trim() && (
                      <button
                        type="button"
                        onClick={() => {
                          setDescription("A skill that takes a URL, fetches the page content, extracts the main article text, and returns a 3-bullet summary.");
                          setTimeout(() => {
                            const textarea = document.getElementById('skill-description');
                            if (textarea) textarea.focus();
                          }, 0);
                        }}
                        className="text-xs text-yellow-400/80 hover:text-yellow-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-yellow-500 rounded px-2 py-1"
                      >
                        or try an example
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
