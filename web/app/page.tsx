"use client";

import { useEffect, useState } from "react";
import { Code2 } from "lucide-react";
import ContextManager from "./components/ContextManager";
import InfoButton from "./components/InfoButton";
import QualityCoach from "./components/QualityCoach";
import SecurityAlert from "./components/SecurityAlert";
import IntentPolicyPanel from "./components/IntentPolicyPanel";
import OutputSkeleton from "./components/OutputSkeleton";
import { useCompiler } from "./hooks/useCompiler";
import { describeRequestError } from "../config";
import type { CompileMode, CompileResponse } from "../lib/api/types";

type OutputTab = "intent" | "system" | "user" | "plan" | "expanded" | "json" | "quality";

function getTabContent(result: CompileResponse, activeTab: OutputTab): string {
  if (activeTab === "system") {
    return result.system_prompt_v2 || result.system_prompt;
  }

  if (activeTab === "user") {
    return result.user_prompt_v2 || result.user_prompt;
  }

  if (activeTab === "plan") {
    return result.plan_v2 || result.plan;
  }

  return result.expanded_prompt_v2 || result.expanded_prompt;
}

function getResultKey(result: CompileResponse | null): string {
  if (!result) {
    return "empty";
  }

  return [result.processing_ms, result.system_prompt_v2 || result.system_prompt, result.expanded_prompt_v2 || result.expanded_prompt].join("::");
}

function CompilerErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-1 items-center justify-center p-10 text-center" role="alert">
      <div className="max-w-md rounded-lg border border-red-500/20 bg-red-500/10 p-6 shadow-xl shadow-red-950/10">
        <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-red-400/30 bg-red-400/10 text-lg font-semibold text-red-200">
          !
        </div>
        <h3 className="text-base font-semibold text-white">Compile failed</h3>
        <p className="mt-2 text-sm leading-relaxed text-red-100/80">{describeRequestError(error)}</p>
        <p className="mt-3 text-xs leading-relaxed text-zinc-500">
          Your prompt is still in the editor. Retry after checking the backend or API URL.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 rounded-lg border border-red-400/30 bg-red-500/20 px-4 py-2 text-sm font-medium text-red-50 transition-colors hover:bg-red-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
        >
          Retry compile
        </button>
      </div>
    </div>
  );
}

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [tabState, setTabState] = useState<{ resultKey: string | null; tab: OutputTab }>({
    resultKey: null,
    tab: "intent",
  });
  const [copiedForResultKey, setCopiedForResultKey] = useState<string | null>(null);
  const [conservativeMode, setConservativeMode] = useState(() => {
    if (typeof window === "undefined") {
      return true;
    }

    return window.localStorage.getItem("promptc_conservative_mode") !== "false";
  });

  const {
    loading,
    result,
    status,
    lastError,
    securityFindings,
    redactedText,
    runCompile,
    retry,
    resolveSecurityDecision,
    cancelSecurityReview,
  } = useCompiler();

  useEffect(() => {
    window.localStorage.setItem("promptc_conservative_mode", String(conservativeMode));
  }, [conservativeMode]);

  const activeMode: CompileMode = conservativeMode ? "conservative" : "default";
  const resultKey = getResultKey(result);
  const activeTab: OutputTab = result && tabState.resultKey === resultKey ? tabState.tab : "intent";
  const copied = copiedForResultKey === resultKey;

  const handleGenerate = async () => {
    await runCompile(prompt, activeMode);
  };

  const handleSecurityDecision = async (useRedacted: boolean) => {
    await resolveSecurityDecision(useRedacted, activeMode);
  };

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-start overflow-x-hidden p-3 py-4 sm:p-4 md:h-screen md:justify-center md:overflow-hidden md:p-8">
      {securityFindings.length > 0 && (
        <SecurityAlert
          findings={securityFindings}
          redactedText={redactedText}
          onProceedRedacted={() => handleSecurityDecision(true)}
          onProceedOriginal={() => handleSecurityDecision(false)}
          onCancel={cancelSecurityReview}
        />
      )}

      <div className="pointer-events-none absolute left-[-10%] top-[-10%] h-[40vw] w-[40vw] rounded-full bg-blue-600/10 blur-[120px]" />
      <div className="pointer-events-none absolute bottom-[-10%] right-[-10%] h-[40vw] w-[40vw] rounded-full bg-purple-600/10 blur-[120px]" />

      <div className="glass animate-fade-in flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col overflow-hidden rounded-2xl shadow-2xl ring-1 ring-white/10 md:h-full md:max-h-[90vh] md:rounded-3xl">
        <header className="flex flex-col gap-3 border-b border-white/5 bg-black/20 p-4 backdrop-blur-md sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20">
                <Code2 size={18} aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-lg font-semibold tracking-tight text-white">Prompt Compiler</h1>
                <div className="font-mono text-[10px] uppercase tracking-wider text-zinc-400 opacity-70">
                  Vague Request To Prompt, Plan, And Policy
                </div>
              </div>
            </div>
            <InfoButton
              title="Prompt Compiler"
              description="Turns vague requests into structured prompts, execution plans, and policy-checked workflows so you can go from rough intent to safe, usable AI output in seconds."
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <button
              type="button"
              onClick={() => setConservativeMode((prev) => !prev)}
              role="switch"
              aria-checked={conservativeMode}
              aria-label={conservativeMode ? "Conservative mode ON" : "Conservative mode OFF"}
              title={conservativeMode ? "Conservative mode ON" : "Conservative mode OFF"}
              className={`group inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
                conservativeMode
                  ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-100 shadow-lg shadow-cyan-900/20"
                  : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
            >
              <span
                className={`h-2.5 w-2.5 rounded-full transition-all ${
                  conservativeMode ? "bg-emerald-400 shadow-[0_0_10px_rgba(74,222,128,0.7)]" : "bg-zinc-500"
                }`}
              />
              <span className="flex flex-col items-start leading-none">
                <span>Conservative</span>
                <span className="mt-1 text-[10px] font-normal opacity-75">
                  {conservativeMode ? "No hallucinations" : "Aggressive optimize"}
                </span>
              </span>
            </button>

            <div className="flex items-center gap-2 rounded-full border border-green-500/30 bg-green-500/10 px-3 py-1.5 text-xs font-medium text-green-400 transition-all duration-300">
              <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-400" />
              AI MODE
            </div>

            <div className="flex items-center gap-2">
              <div className="min-w-[88px] rounded-lg border border-white/5 bg-black/30 px-3 py-1.5 text-center font-mono text-xs text-zinc-500">
                {status}
              </div>
              {!!lastError && !loading && (
                <button
                  type="button"
                  onClick={() => void retry()}
                  className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
                >
                  Retry
                </button>
              )}
            </div>
          </div>
        </header>

        <div className="flex flex-1 flex-col overflow-visible md:min-h-0 md:flex-row md:overflow-hidden">
          <div className="flex w-full flex-col gap-4 border-b border-white/5 bg-black/10 p-4 sm:p-5 md:min-h-0 md:w-[35%] md:border-b-0 md:border-r md:overflow-y-auto">
            <div className="group relative flex flex-1 flex-col">
              <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-500/5 to-purple-500/5 opacity-0 transition-opacity duration-500 group-focus-within:opacity-100" />
              <textarea
                aria-label="Describe what you want compiled"
                className="min-h-36 w-full flex-1 resize-none rounded-2xl border border-white/10 bg-black/20 p-5 font-mono text-sm leading-relaxed text-zinc-200 shadow-inner transition-all placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50 sm:min-h-44 md:min-h-0"
                placeholder="Paste a vague task, bug report, spec, or workflow request... e.g. 'Turn this GitHub issue into a safe implementation brief'"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                    e.preventDefault();
                    if (!loading && prompt.trim()) {
                      void handleGenerate();
                    }
                  }
                }}
              />
            </div>

            <div className="flex flex-col gap-4">
              <button
                type="button"
                onClick={() => handleGenerate()}
                disabled={loading || !prompt.trim()}
                title={!prompt.trim() ? "Enter a prompt first to compile" : "Compile Prompt"}
                className="group flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-blue-500/20 transition-all hover:from-blue-500 hover:to-indigo-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
              >
                {loading ? (
                  <span className="animate-pulse">Thinking...</span>
                ) : (
                  <>
                    Generate <span className="transition-transform group-hover:translate-x-0.5">{"->"}</span>{" "}
                    <kbd className="ml-2 hidden rounded border border-white/20 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] opacity-50 md:inline-block">
                      Ctrl/Cmd Enter
                    </kbd>
                  </>
                )}
              </button>
            </div>

            <ContextManager
              onInsertContext={(text) => setPrompt((prev) => prev + "\n\n---\nContext:\n" + text)}
              suggestions={result?.ir?.metadata?.context_suggestions}
            />
          </div>

          <div className="relative flex min-h-[360px] w-full flex-col bg-black/20 md:min-h-0 md:w-[65%]">
            {!!lastError && !loading ? (
              <CompilerErrorState error={lastError} onRetry={() => void retry()} />
            ) : result ? (
              <>
                <div
                  role="tablist"
                  aria-label="Output views"
                  className="flex gap-1 overflow-x-auto scroll-smooth border-b border-white/5 px-4 pb-1 pt-4"
                  style={{ maskImage: "linear-gradient(to right, black, black calc(100% - 24px), transparent)" }}
                >
                  {(["intent", "system", "user", "plan", "expanded", "json", "quality"] as const).map((tab) => (
                    <button
                      type="button"
                      key={tab}
                      role="tab"
                      aria-selected={activeTab === tab}
                      aria-controls={`tabpanel-${tab}`}
                      id={`tab-${tab}`}
                      onClick={() => setTabState({ resultKey, tab })}
                      className={`relative whitespace-nowrap rounded-t-lg px-3 py-2 text-[13px] font-medium transition-all focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 sm:px-4 ${
                        activeTab === tab
                          ? "border-x border-t border-white/5 bg-white/5 text-white"
                          : "text-zinc-500 hover:bg-white/5 hover:text-zinc-300"
                      }`}
                    >
                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                  ))}
                </div>

                <div
                  role="tabpanel"
                  id="tabpanel-intent"
                  aria-labelledby="tab-intent"
                  hidden={activeTab !== "intent"}
                  className="group relative flex-1 min-h-0 overflow-hidden bg-black/20 p-0"
                >
                  {activeTab === "intent" && (
                    <div className="absolute inset-0 z-20 bg-transparent">
                      <IntentPolicyPanel result={result} />
                    </div>
                  )}
                </div>

                {(["system", "user", "plan", "expanded"] as const).map((tab) => (
                  <div
                    key={tab}
                    role="tabpanel"
                    id={`tabpanel-${tab}`}
                    aria-labelledby={`tab-${tab}`}
                    hidden={activeTab !== tab}
                    className="group relative flex-1 min-h-0 overflow-hidden bg-black/20 p-0"
                  >
                    {activeTab === tab && (
                      <>
                        <div className="absolute right-6 top-4 z-10 flex gap-2">
                          {result.ir?.metadata?.context_snippets && result.ir.metadata.context_snippets.length > 0 && (
                            <div
                              className="flex items-center gap-1.5 rounded-md border border-indigo-500/20 bg-indigo-500/10 px-2 py-1 backdrop-blur-md"
                              title="Context Strategist Active"
                            >
                              <div className="text-[10px] font-semibold">CTX</div>
                              <span className="text-[10px] font-medium text-indigo-200">
                                {result.ir.metadata.context_snippets.length} Sources
                              </span>
                            </div>
                          )}

                          {result.critique && (
                            <div
                              tabIndex={0}
                              className={`group/critic relative flex cursor-help items-center gap-1.5 rounded-md border px-2 py-1 backdrop-blur-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                                result.critique.verdict === "REJECT"
                                  ? "border-red-500/30 bg-red-500/10"
                                  : "border-green-500/30 bg-green-500/10"
                              }`}
                            >
                              <div
                                className={`h-1.5 w-1.5 rounded-full ${
                                  result.critique.verdict === "REJECT" ? "bg-red-400" : "bg-green-400"
                                }`}
                              />
                              <span
                                className={`text-[10px] font-medium ${
                                  result.critique.verdict === "REJECT" ? "text-red-200" : "text-green-200"
                                }`}
                              >
                                Critic: {result.critique.score}/100
                              </span>

                              <div className="invisible absolute right-0 top-8 z-50 w-64 rounded-xl border border-white/10 bg-zinc-900 p-3 opacity-0 shadow-2xl transition-all group-hover/critic:visible group-hover/critic:opacity-100 group-focus-visible/critic:visible group-focus-visible/critic:opacity-100">
                                <div className="mb-2 flex items-center justify-between">
                                  <span className="text-xs font-bold text-zinc-300">Agent 7 Verdict</span>
                                  <span
                                    className={`rounded px-1.5 py-0.5 text-[10px] ${
                                      result.critique.verdict === "REJECT"
                                        ? "bg-red-900 text-red-300"
                                        : "bg-green-900 text-green-300"
                                    }`}
                                  >
                                    {result.critique.verdict}
                                  </span>
                                </div>
                                <p className="mb-2 text-[10px] leading-relaxed text-zinc-400">
                                  {result.critique.feedback}
                                </p>
                                {result.critique.issues.length > 0 && (
                                  <div className="space-y-1">
                                    {result.critique.issues.map((issue, index) => (
                                      <div
                                        key={index}
                                        className="rounded border border-white/5 bg-black/20 p-1.5 text-[9px] text-zinc-400"
                                      >
                                        <span className="font-semibold text-red-400">[{issue.type}]</span>{" "}
                                        {issue.description}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {result.system_prompt_v2 ? (
                            <div className="flex items-center gap-1.5 rounded-md border border-blue-500/20 bg-blue-500/10 px-2 py-1 backdrop-blur-md">
                              <div className="h-1.5 w-1.5 rounded-full bg-blue-400 shadow-[0_0_5px_rgba(96,165,250,0.8)]" />
                              <span className="text-[10px] font-medium text-blue-200">Reasoning Model</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 rounded-md border border-zinc-700/50 bg-zinc-800/50 px-2 py-1 backdrop-blur-md">
                              <div className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
                              <span className="text-[10px] font-medium text-zinc-400">Standard</span>
                            </div>
                          )}
                        </div>

                        <textarea
                          id="compiled-output"
                          aria-label="Compiled prompt output"
                          className="h-full w-full resize-none overflow-y-auto bg-transparent p-6 pb-24 font-mono text-sm leading-relaxed text-zinc-300 selection:bg-blue-500/30 focus:outline-none"
                          readOnly
                          value={getTabContent(result, tab)}
                        />

                        <button
                          type="button"
                          onClick={() => {
                            navigator.clipboard.writeText(getTabContent(result, tab));
                            setCopiedForResultKey(resultKey);
                            setTimeout(() => setCopiedForResultKey((current) => (current === resultKey ? null : current)), 2000);
                          }}
                          className="absolute bottom-6 right-6 z-20 rounded-xl bg-blue-600 p-3 text-white shadow-lg shadow-blue-500/20 transition-all hover:scale-105 hover:bg-blue-500 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                          title={copied ? "Copied!" : "Copy to Clipboard"}
                          aria-label={copied ? "Copied" : "Copy to Clipboard"}
                        >
                          {copied ? (
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="18"
                              height="18"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                          ) : (
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="18"
                              height="18"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
                              <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
                            </svg>
                          )}
                        </button>
                      </>
                    )}
                  </div>
                ))}

                <div
                  role="tabpanel"
                  id="tabpanel-json"
                  aria-labelledby="tab-json"
                  hidden={activeTab !== "json"}
                  className="group relative flex-1 min-h-0 overflow-hidden bg-black/20 p-0"
                >
                  {activeTab === "json" && (
                    <div className="absolute inset-0 z-20 overflow-auto bg-transparent p-6">
                      <pre className="h-full overflow-auto rounded-xl border border-white/5 bg-black/30 p-4 font-mono text-xs text-zinc-300 shadow-inner">
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                <div
                  role="tabpanel"
                  id="tabpanel-quality"
                  aria-labelledby="tab-quality"
                  hidden={activeTab !== "quality"}
                  className="group relative flex-1 min-h-0 overflow-hidden bg-black/20 p-0"
                >
                  {activeTab === "quality" && (
                    <div className="absolute inset-0 z-20 bg-transparent">
                      <QualityCoach prompt={prompt} onUpdatePrompt={setPrompt} />
                    </div>
                  )}
                </div>
              </>
            ) : loading ? (
              <OutputSkeleton />
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-5 p-6 text-center sm:gap-6 sm:p-10">
                <div className="group relative">
                  <div className="absolute inset-0 rounded-full bg-blue-500/30 blur-[40px] transition-all duration-700 group-hover:bg-blue-500/50" />
                  <div className="relative flex h-24 w-24 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br from-zinc-800 to-black shadow-2xl">
                    <Code2
                      size={40}
                      strokeWidth={1.5}
                      aria-hidden="true"
                      className="text-blue-400/60 drop-shadow-[0_0_10px_rgba(255,255,255,0.3)]"
                    />
                  </div>
                </div>
                <div className="max-w-sm space-y-2">
                  <h3 className="text-base font-semibold tracking-tight text-zinc-100">
                    Start with any rough request
                  </h3>
                  <p className="text-sm leading-relaxed text-zinc-400">
                    Paste a task, question, bug report, or workflow on the left, then press{" "}
                    <kbd className="rounded border border-white/20 bg-white/5 px-1 py-0.5 font-mono text-[11px]">
                      Ctrl/Cmd Enter
                    </kbd>
                    . You&apos;ll get structured prompts, an execution plan, and policy checks you can inspect before
                    using the result downstream.
                  </p>
                  <p className="text-xs leading-relaxed text-zinc-500">
                    Good first inputs: GitHub issue to implementation brief, PR description to review checklist, or a
                    spec to implementation plan.
                  </p>
                  <p className="mt-4 font-mono text-[10px] text-zinc-500">v0.1.1</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
