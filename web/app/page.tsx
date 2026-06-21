"use client";

import { useEffect, useId, useState } from "react";
import ContextManager from "./components/ContextManager";
import InfoButton from "./components/InfoButton";
import QualityCoach from "./components/QualityCoach";
import SecurityAlert from "./components/SecurityAlert";
import IntentPolicyPanel from "./components/IntentPolicyPanel";
import OutputSkeleton from "./components/OutputSkeleton";
import PolicyBadge from "./components/PolicyBadge";
import CopyButton from "./components/CopyButton";
import { useCompiler } from "./hooks/useCompiler";
import { useContextManager } from "./hooks/useContextManager";

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

function TabButton({
  tabKey,
  label,
  hint,
  isActive,
  primary,
  onSelect,
}: {
  tabKey: OutputTab;
  label: string;
  hint: string;
  isActive: boolean;
  primary: boolean;
  onSelect: (key: OutputTab) => void;
}) {
  const [showTip, setShowTip] = useState(false);
  const tipId = useId();

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        role="tab"
        aria-selected={isActive}
        aria-controls={`tabpanel-${tabKey}`}
        aria-describedby={showTip ? tipId : undefined}
        id={`tab-${tabKey}`}
        onClick={() => onSelect(tabKey)}
        onMouseEnter={() => setShowTip(true)}
        onMouseLeave={() => setShowTip(false)}
        onFocus={() => setShowTip(true)}
        onBlur={() => setShowTip(false)}
        className={`relative whitespace-nowrap rounded-t-lg px-3 py-2 text-[13px] font-medium transition-all focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 sm:px-4 ${isActive
          ? "text-white bg-white/10 border-t border-x border-white/10"
          : "text-zinc-400 hover:text-zinc-200 hover:bg-white/5"
          }`}
      >
        <span>{label}</span>
        {primary && (
          <span className="ml-2 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-1.5 py-0.5 align-middle text-[9px] font-mono uppercase tracking-wider text-emerald-300">
            Use this
          </span>
        )}
      </button>
      {showTip && (
        <span
          id={tipId}
          role="tooltip"
          className="pointer-events-none absolute left-1/2 top-full z-50 mt-1 w-64 -translate-x-1/2 rounded-md border border-neutral-700 bg-neutral-900 p-2.5 text-left text-xs font-normal leading-snug text-neutral-300 shadow-xl animate-fade-in"
        >
          {hint}
        </span>
      )}
    </span>
  );
}

function CompilerErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <div className="flex-1 flex items-center justify-center p-10 text-center" role="alert">
      <div className="max-w-md rounded-lg border border-red-500/20 bg-red-500/10 p-6 shadow-xl shadow-red-950/10">
        <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-red-400/30 bg-red-400/10 text-lg font-semibold text-red-200">
          !
        </div>
        <h3 className="text-base font-semibold text-white">Compile failed</h3>
        <p className="mt-2 text-sm leading-relaxed text-red-100/80">{describeRequestError(error)}</p>
        <p className="mt-3 text-xs leading-relaxed text-zinc-400">
          Your prompt is safe in the editor. Try again — if it keeps failing, your connection or the compiler service may be down.
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
  const [prompt, setPrompt] = useState(() => {
    if (typeof window === "undefined") {
      return "";
    }
    return window.localStorage.getItem("promptc_compiler_prompt") || "";
  });
  const [activeTab, setActiveTab] = useState<OutputTab>("user");
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

  const { indexStats } = useContextManager();

  useEffect(() => {
    window.localStorage.setItem("promptc_compiler_prompt", prompt);
  }, [prompt]);

  useEffect(() => {
    window.localStorage.setItem("promptc_conservative_mode", String(conservativeMode));
  }, [conservativeMode]);

  const activeMode: CompileMode = conservativeMode ? "conservative" : "default";

  const handleGenerate = async () => {
    await runCompile(prompt, activeMode);
  };

  const handleSecurityDecision = async (useRedacted: boolean) => {
    await resolveSecurityDecision(useRedacted, activeMode);
  };

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-start overflow-x-hidden p-3 py-4 sm:p-4 md:h-screen md:justify-center md:overflow-hidden md:p-8">

      {/* Security Alert Modal */}
      {securityFindings.length > 0 && (
        <SecurityAlert
          findings={securityFindings}
          redactedText={redactedText}
          onProceedRedacted={() => handleSecurityDecision(true)}
          onProceedOriginal={() => handleSecurityDecision(false)}
          onCancel={cancelSecurityReview}
        />
      )}
      {/* Ambient Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-blue-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-purple-600/10 blur-[120px] pointer-events-none" />

      {/* Floating Main Container */}
      <div className="glass flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col overflow-hidden rounded-2xl shadow-2xl ring-1 ring-white/10 animate-fade-in md:h-full md:max-h-[90vh] md:rounded-3xl">

        {/* Header */}
        <header className="flex flex-col gap-3 border-b border-white/5 bg-black/20 p-4 backdrop-blur-md sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center text-lg text-white shadow-lg shadow-blue-500/20">💠</div>
              <div>
                <h1 className="font-semibold text-lg tracking-tight text-white">Prompt Compiler</h1>
                <div className="text-[10px] text-zinc-400 font-mono tracking-wider uppercase opacity-70">Vague Request To Prompt, Plan, And Policy</div>
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

            <div className="px-3 py-1.5 rounded-full text-xs font-medium border flex items-center gap-2 transition-all duration-300 bg-green-500/10 border-green-500/30 text-green-400">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              AI MODE
            </div>

            <div className="flex items-center gap-2">
              <div className="min-w-0 rounded-lg border border-white/5 bg-black/30 px-3 py-1.5 text-center font-mono text-xs text-zinc-300 sm:min-w-[88px]">
                {status}
              </div>
              {!!lastError && !loading && (
                <button
                  type="button"
                  onClick={() => void retry()}
                  className="text-xs font-medium text-red-300 bg-red-500/10 border border-red-500/20 px-3 py-1.5 rounded-lg hover:bg-red-500/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
                >
                  Retry
                </button>
              )}
            </div>
          </div>
        </header>

        <div className="flex flex-1 flex-col overflow-visible md:min-h-0 md:flex-row md:overflow-hidden">
          {/* Left Panel: Input */}
          <div className="flex w-full flex-col gap-4 border-b border-white/5 bg-black/10 p-4 sm:p-5 md:min-h-0 md:w-[35%] md:border-b-0 md:border-r md:overflow-y-auto">

            <div className="flex-1 flex flex-col relative group">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 rounded-2xl pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity duration-500" />
              <div className="relative flex-1 flex flex-col">
                <label htmlFor="prompt-input" className="sr-only">Describe what you want compiled</label>
                <textarea
                  id="prompt-input"
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
                {prompt && (
                  <button
                    type="button"
                    onClick={() => setPrompt("")}
                    className="absolute top-2 right-2 text-xs text-zinc-500 hover:text-zinc-300 bg-black/40 hover:bg-black/60 px-2 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500/50"
                    title="Clear prompt"
                    aria-label="Clear prompt"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-4">
              {indexStats && indexStats.docs > 0 && (
                <div className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 animate-fade-in shadow-lg shadow-emerald-950/20">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    <span className="font-semibold tracking-wide uppercase text-[10px]">RAG Context Active</span>
                  </div>
                  <span className="font-mono text-[10px] bg-emerald-500/20 px-2 py-0.5 rounded-md text-emerald-200">
                    {indexStats.docs} {indexStats.docs === 1 ? 'doc' : 'docs'} attached
                  </span>
                </div>
              )}
              <button
                type="button"
                onClick={() => handleGenerate()}
                disabled={loading || !prompt.trim()}
                aria-busy={loading}
                title={!prompt.trim() ? "Enter a prompt first to compile" : "Compile Prompt"}
                className="w-full px-4 py-3 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-blue-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
              >
                {loading ? (
                  <span className="animate-pulse">Thinking...</span>
                ) : (
                  <>Generate <span className="transition-transform group-hover:translate-x-0.5">{"->"}</span> <kbd className="ml-2 hidden rounded border border-white/20 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] opacity-50 md:inline-block">Ctrl/Cmd Enter</kbd></>
                )}
              </button>
            </div>

            {/* Context Manager */}
            <ContextManager
              onInsertContext={(text) => setPrompt(prev => prev + "\n\n---\nContext:\n" + text)}
              suggestions={result?.ir?.metadata?.context_suggestions}
            />
          </div>

          {/* Right Panel: Output */}
          <div className="relative flex min-h-[360px] w-full flex-col bg-black/20 md:min-h-0 md:w-[65%]">

            {/* ── Compiler Output View ── */}
            {!!lastError && !loading ? (
              <CompilerErrorState error={lastError} onRetry={() => void retry()} />
            ) : loading ? (
              <OutputSkeleton />
            ) : result ? (
              <>
                {/* Tabs + policy verdict */}
                <div className="flex items-center gap-3 border-b border-white/5 px-4 pt-4 pb-1">
                  <div className="relative flex min-w-0 flex-1">
                    <div role="tablist" aria-label="Output views" className="custom-scrollbar flex min-w-0 flex-1 gap-1 overflow-x-auto scroll-smooth sm:pr-6 lg:pr-0">
                    {(
                      [
                        { key: "user", label: "User Prompt", hint: "The prompt to copy and send to your model. Most users want this tab.", primary: true },
                        { key: "system", label: "System Prompt", hint: "Role and behavior rules for the model — paste this into a system message.", primary: false },
                        { key: "plan", label: "Execution Plan", hint: "Step-by-step plan the compiler suggests for carrying out the request.", primary: false },
                        { key: "expanded", label: "Long-form", hint: "Verbose, fully expanded version of the prompt with all context inlined.", primary: false },
                        { key: "intent", label: "Intent", hint: "Detected intent and safety policy for this request.", primary: false },
                        { key: "json", label: "JSON", hint: "Raw machine-readable compile output — useful for piping into other tools.", primary: false },
                        { key: "quality", label: "Quality Scores", hint: "Quality, clarity, and safety scores the compiler assigned to the result.", primary: false },
                      ] satisfies ReadonlyArray<{ key: OutputTab; label: string; hint: string; primary: boolean }>
                    ).map(({ key, label, hint, primary }) => (
                      <TabButton
                        key={key}
                        tabKey={key}
                        label={label}
                        hint={hint}
                        isActive={activeTab === key}
                        primary={primary}
                        onSelect={setActiveTab}
                      />
                    ))}
                    </div>
                    <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-0 hidden items-center pr-1 sm:flex lg:hidden">
                      <div className="h-full w-8 bg-gradient-to-l from-black/60 to-transparent" />
                      <span className="ml-[-14px] rounded-full border border-white/10 bg-black/60 px-1.5 text-[11px] leading-none text-zinc-300 backdrop-blur-sm">›</span>
                    </div>
                  </div>
                  <PolicyBadge result={result} />
                </div>

                {/* Content — one stable tabpanel per tab, hidden when inactive */}

                {/* intent panel */}
                <div
                  role="tabpanel"
                  id="tabpanel-intent"
                  aria-labelledby="tab-intent"
                  hidden={activeTab !== "intent"}
                  className="flex-1 min-h-0 p-0 overflow-hidden relative group bg-black/20"
                >
                  {activeTab === "intent" && (
                    <div className="absolute inset-0 bg-transparent z-20">
                      <IntentPolicyPanel result={result} />
                    </div>
                  )}
                </div>

                {/* text-content panels: system, user, plan, expanded */}
                {(["system", "user", "plan", "expanded"] as const).map((tab) => (
                  <div
                    key={tab}
                    role="tabpanel"
                    id={`tabpanel-${tab}`}
                    aria-labelledby={`tab-${tab}`}
                    hidden={activeTab !== tab}
                    className="flex-1 min-h-0 p-0 overflow-hidden relative group bg-black/20"
                  >
                    {activeTab === tab && (
                      <>
                        {/* CRITIC & STRATEGIST UI OVERLAY (Top Right) */}
                        <div className="absolute top-4 right-6 z-10 flex gap-2">
                          {/* Agent 6 Badge */}
                          {result.ir?.metadata?.context_snippets && result.ir.metadata.context_snippets.length > 0 && (
                            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-indigo-500/10 border border-indigo-500/20 backdrop-blur-md" title="Context Strategist Active">
                              <div className="text-[10px]">🕵️</div>
                              <span className="text-[10px] text-indigo-200 font-medium">
                                {result.ir.metadata.context_snippets.length} Sources
                              </span>
                            </div>
                          )}

                          {/* Agent 7 Badge */}
                          {result.critique && (
                            <div tabIndex={0} className={`flex items-center gap-1.5 px-2 py-1 rounded-md border backdrop-blur-md cursor-help group/critic relative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${result.critique.verdict === "REJECT"
                              ? "bg-red-500/10 border-red-500/30"
                              : "bg-green-500/10 border-green-500/30"
                              }`}>
                              <div className={`w-1.5 h-1.5 rounded-full ${result.critique.verdict === "REJECT" ? "bg-red-400" : "bg-green-400"}`} />
                              <span className={`text-[10px] font-medium ${result.critique.verdict === "REJECT" ? "text-red-200" : "text-green-200"}`}>
                                Critic: {result.critique.score}/100
                              </span>

                              {/* Hover Popup */}
                              <div className="absolute top-8 right-0 w-64 bg-zinc-900 border border-white/10 rounded-xl p-3 shadow-2xl opacity-0 invisible group-hover/critic:opacity-100 group-hover/critic:visible group-focus-visible/critic:opacity-100 group-focus-visible/critic:visible transition-all z-50">
                                <div className="flex justify-between items-center mb-2">
                                  <span className="text-xs font-bold text-zinc-300">Agent 7 Verdict</span>
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${result.critique.verdict === "REJECT" ? "bg-red-900 text-red-300" : "bg-green-900 text-green-300"}`}>{result.critique.verdict}</span>
                                </div>
                                <p className="text-[10px] text-zinc-400 mb-2 leading-relaxed">{result.critique.feedback}</p>
                                {result.critique.issues.length > 0 && (
                                  <div className="space-y-1">
                                    {result.critique.issues.map((issue, i) => (
                                      <div key={i} className="text-[9px] bg-black/20 p-1.5 rounded border border-white/5 text-zinc-400">
                                        <span className="text-red-400 font-semibold">[{issue.type}]</span> {issue.description}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>

                        <label htmlFor="compiled-output" className="sr-only">Compiled prompt output</label>
                        <textarea
                          id="compiled-output"
                          aria-label="Compiled prompt output"
                          className="w-full h-full overflow-y-auto bg-transparent p-6 pb-24 font-mono text-sm text-zinc-300 resize-none focus:outline-none leading-relaxed selection:bg-blue-500/30"
                          readOnly
                          value={getTabContent(result, tab)}
                        />

                        <CopyButton
                          text={getTabContent(result, tab)}
                          className="absolute bottom-6 right-6"
                        />
                      </>
                    )}
                  </div>
                ))}

                {/* json panel */}
                <div
                  role="tabpanel"
                  id="tabpanel-json"
                  aria-labelledby="tab-json"
                  hidden={activeTab !== "json"}
                  className="flex-1 min-h-0 p-0 overflow-hidden relative group bg-black/20"
                >
                  {activeTab === "json" && (
                    <>
                      <div className="absolute inset-0 bg-transparent z-20 overflow-auto p-6">
                        <pre className="bg-black/30 p-4 rounded-xl border border-white/5 text-xs font-mono text-zinc-300 overflow-auto h-full shadow-inner">
                          {JSON.stringify(result, null, 2)}
                        </pre>
                      </div>
                      <CopyButton
                        text={JSON.stringify(result, null, 2)}
                        className="absolute bottom-6 right-6"
                      />
                    </>
                  )}
                </div>

                {/* quality panel */}
                <div
                  role="tabpanel"
                  id="tabpanel-quality"
                  aria-labelledby="tab-quality"
                  hidden={activeTab !== "quality"}
                  className="flex-1 min-h-0 p-0 overflow-hidden relative group bg-black/20"
                >
                  {activeTab === "quality" && (
                    <div className="absolute inset-0 bg-transparent z-20">
                      <QualityCoach prompt={prompt} onUpdatePrompt={setPrompt} />
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-5 p-6 text-center sm:gap-6 sm:p-10">
                <div className="relative group">
                  <div className="absolute inset-0 bg-blue-500/30 blur-[40px] rounded-full group-hover:bg-blue-500/50 transition-all duration-700" />
                  <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-zinc-800 to-black border border-white/10 flex items-center justify-center shadow-2xl">
                    <span className="text-4xl filter drop-shadow-[0_0_10px_rgba(255,255,255,0.3)]">💠</span>
                  </div>
                </div>
                <div className="max-w-sm space-y-2">
                  <h3 className="text-zinc-100 font-semibold tracking-tight text-lg">Start with any rough request</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed mb-4">
                    Paste a task, question, bug report, or workflow into the editor{" "}
                    <span className="hidden md:inline">on the left, then press <kbd className="rounded border border-white/20 bg-white/5 px-1 py-0.5 font-mono text-[11px]">Ctrl/Cmd Enter</kbd></span>
                    <span className="md:hidden">above, then tap <span className="font-semibold text-zinc-200">Compile Prompt</span> below</span>.
                    You&apos;ll get structured prompts, an execution plan, and policy checks you can inspect before using the result downstream.
                  </p>
                  <div className="flex flex-col items-center gap-3 mt-2 w-full">
                    <button
                      type="button"
                      onClick={() => handleGenerate()}
                      disabled={loading || !prompt.trim()}
                      aria-busy={loading}
                      title={!prompt.trim() ? "Enter a prompt first to compile" : "Compile Prompt"}
                      className="mx-auto px-6 py-2.5 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-blue-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
                    >
                      Compile Prompt
                    </button>
                    {!prompt.trim() && (
                      <button
                        type="button"
                        onClick={() => {
                          setPrompt("Write a Python script that analyzes an nginx access.log file, counts requests by IP, and flags IPs with more than 100 requests in a minute.");
                          setTimeout(() => {
                            const textarea = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="Describe what you want compiled"]');
                            if (textarea) textarea.focus();
                          }, 0);
                        }}
                        className="text-xs text-blue-400/80 hover:text-blue-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500 rounded px-2 py-1"
                      >
                        or try an example
                      </button>
                    )}
                  </div>
                  <p className="text-xs italic text-zinc-500 leading-relaxed mt-4">
                    Good first inputs: GitHub issue to implementation brief, PR description to review checklist, or a spec to implementation plan.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div >
    </main >
  );
}
