"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import ContextManager from "./components/ContextManager";
import QualityCoach from "./components/QualityCoach";

type CompileResponse = {
  system_prompt: string;
  user_prompt: string;
  plan: string;
  expanded_prompt: string;
  system_prompt_v2?: string;
  user_prompt_v2?: string;
  plan_v2?: string;
  expanded_prompt_v2?: string;
  ir: any;
  processing_ms: number;
};

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CompileResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"system" | "user" | "plan" | "expanded" | "quality">("system");
  const [liveMode, setLiveMode] = useState(false);
  const [diagnostics, setDiagnostics] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [debouncedPrompt, setDebouncedPrompt] = useState("");

  // Sync debounced prompt
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedPrompt(prompt), 600);
    return () => clearTimeout(timer);
  }, [prompt]);

  // Trigger generation on debounced prompt change (if Live Mode is on)
  useEffect(() => {
    if (liveMode && debouncedPrompt.trim()) {
      handleGenerate(debouncedPrompt);
    }
  }, [debouncedPrompt]); // Removed liveMode dependency to prevent trigger on toggle

  const handleGenerate = useCallback(async (textOverride?: string) => {
    const textToCompile = typeof textOverride === 'string' ? textOverride : prompt;
    if (!textToCompile.trim()) return;

    setLoading(true);
    // 1. Instant Heuristic Feedback (Optimistic UI)
    setStatus(liveMode ? "Live Compiling..." : "Generating (Fast)...");

    try {
      // Step A: Fast V1 Request (Skip in Live Mode if user wants pure DeepSeek)
      if (!liveMode) {
        const resV1 = await fetch("http://127.0.0.1:8080/compile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: textToCompile, diagnostics, v2: false }),
        });

        if (resV1.ok) {
          const dataV1 = await resV1.json();
          setResult(dataV1);
          setStatus("Reasoning with DeepSeek...");
        }
      } else {
        setStatus("DeepSeek Thinking...");
      }

      // Step B: Slow V2 Request (DeepSeek)
      // Step B: Slow V2 Request (DeepSeek)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 190000); // 190s timeout

      try {
        const resV2 = await fetch("http://127.0.0.1:8080/compile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: textToCompile, diagnostics, v2: true, render_v2_prompts: true }),
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (!resV2.ok) throw new Error(`API Error: ${resV2.status}`);

        const dataV2 = await resV2.json();
        setResult(dataV2);
        setStatus(`Done in ${dataV2.processing_ms}ms`);
      } catch (e: any) {
        if (e.name === 'AbortError') {
          throw new Error("Timeout: DeepSeek took too long to respond.");
        }
        throw e;
      }

    } catch (e: any) {
      console.error(e);
      setStatus(`Error: ${e.message || "Connection Failed"}`);
    } finally {
      setLoading(false);
    }
  }, [prompt, diagnostics, liveMode]);

  const handleOptimize = async () => {
    if (!prompt.trim()) return;
    setStatus("Optimizing...");
    try {
      const res = await fetch("http://127.0.0.1:8080/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: prompt }),
      });
      const data = await res.json();
      setPrompt(data.text);
      setStatus(`Optimized! (-${data.before_tokens - data.after_tokens} tokens)`);
    } catch (e) {
      setStatus("Optimization error");
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-zinc-900 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-950 p-4 flex items-center gap-3">
        <div className="h-8 w-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold">P</div>
        <h1 className="font-semibold text-lg">Prompt Compiler <span className="text-zinc-500 text-sm font-normal ml-2">v2.1</span></h1>

        <div className="ml-6 px-3 py-1 bg-blue-900/30 border border-blue-800 rounded-full text-xs text-blue-300 flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
          </span>
          DeepSeek V3
        </div>

        <div className="ml-auto text-xs text-zinc-500 font-mono">{status}</div>
      </header>

      <div className="flex-1 flex flex-col md:flex-row h-full overflow-hidden">
        {/* Left Panel: Input */}
        <div className="w-full md:w-1/3 p-4 flex flex-col gap-4 border-r border-zinc-800 bg-zinc-900/50">
          <div className="flex-1 flex flex-col">
            <textarea
              className="flex-1 w-full bg-zinc-800 p-4 rounded-xl border border-zinc-700 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm leading-relaxed"
              placeholder="Describe your prompt idea here... e.g. 'Act as a senior python dev teaching FastAPI'"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

          <div className="flex flex-wrap gap-2 items-center justify-between">
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer hover:text-zinc-200 select-none">
                <input type="checkbox" checked={liveMode} onChange={e => setLiveMode(e.target.checked)} className="rounded bg-zinc-700 border-zinc-600 text-blue-600 focus:ring-0" />
                <span className={liveMode ? "text-green-400 font-bold" : ""}>LIVE Mode</span>
              </label>
              <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer hover:text-zinc-200 select-none">
                <input type="checkbox" checked={diagnostics} onChange={e => setDiagnostics(e.target.checked)} className="rounded bg-zinc-700 border-zinc-600" />
                Diagnostics
              </label>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleOptimize}
                className="px-4 py-2 text-xs font-medium bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors text-zinc-300"
                disabled={loading}
              >
                magic optimize
              </button>
              <button
                onClick={() => handleGenerate()}
                disabled={loading}
                className="px-6 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg shadow-lg shadow-blue-500/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {loading ? "Thinking..." : "Generate ⚡"}
              </button>
            </div>
          </div>

          {/* Context Manager */}
          <ContextManager onInsertContext={(text) => setPrompt(prev => prev + "\n\n---\nContext:\n" + text)} />
        </div>

        {/* Right Panel: Output */}
        <div className="w-full md:w-2/3 flex flex-col bg-zinc-950 relative">
          {result ? (
            <>
              {/* Tabs */}
              <div className="flex border-b border-zinc-800 px-2 pt-2 gap-1 bg-zinc-900/30">
                {(["system", "user", "plan", "expanded", "quality"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors relative ${activeTab === tab
                      ? "text-blue-400 bg-zinc-900 border-t border-x border-zinc-800"
                      : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50"
                      }`}
                  >
                    {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    {activeTab === tab && <div className="absolute top-0 left-0 w-full h-0.5 bg-blue-500 rounded-t-lg"></div>}
                  </button>
                ))}
              </div>

              {/* Content */}
              <div className="flex-1 p-0 overflow-hidden relative group flex flex-col">
                {activeTab !== "quality" && (
                  <>
                    <div className="absolute top-2 right-14 z-10">
                      {result.system_prompt_v2 ? (
                        <span className="bg-blue-900/50 text-blue-300 text-[10px] px-2 py-1 rounded border border-blue-800 backdrop-blur-sm">
                          Generated by DeepSeek V3
                        </span>
                      ) : (
                        <span className="bg-zinc-800/50 text-zinc-400 text-[10px] px-2 py-1 rounded border border-zinc-700 backdrop-blur-sm">
                          Offline Fallback
                        </span>
                      )}
                    </div>
                    <textarea
                      className="w-full h-full bg-zinc-950 p-6 font-mono text-sm text-zinc-300 resize-none focus:outline-none leading-relaxed"
                      readOnly
                      value={
                        activeTab === "system" ? (result.system_prompt_v2 || result.system_prompt) :
                          activeTab === "user" ? (result.user_prompt_v2 || result.user_prompt) :
                            activeTab === "plan" ? (result.plan_v2 || result.plan) :
                              (result.expanded_prompt_v2 || result.expanded_prompt)
                      }
                    />

                    <button
                      onClick={() => navigator.clipboard.writeText(
                        activeTab === "system" ? (result.system_prompt_v2 || result.system_prompt) :
                          activeTab === "user" ? (result.user_prompt_v2 || result.user_prompt) :
                            activeTab === "plan" ? (result.plan_v2 || result.plan) :
                              (result.expanded_prompt_v2 || result.expanded_prompt)
                      )}
                      className="absolute top-4 right-4 bg-zinc-800/80 hover:bg-white hover:text-black hover:scale-110 active:scale-95 text-zinc-400 p-2 rounded-lg transition-all backdrop-blur opacity-0 group-hover:opacity-100 border border-zinc-700"
                      title="Copy to Clipboard"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                    </button>
                  </>
                )}

                {/* Quality Coach Overlay/View */}
                {activeTab === "quality" && (
                  <div className="absolute inset-0 bg-zinc-950 z-20">
                    <QualityCoach prompt={prompt} onUpdatePrompt={setPrompt} />
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-zinc-700 gap-4">
              <div className="w-16 h-16 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
                <span className="text-2xl">✨</span>
              </div>
              <p>Ready to compile your ideas.</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
