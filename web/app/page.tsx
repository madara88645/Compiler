"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import ContextManager from "./components/ContextManager";
import QualityCoach from "./components/QualityCoach";
import SecurityAlert from "./components/SecurityAlert";

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
  const [activeTab, setActiveTab] = useState<"system" | "user" | "plan" | "expanded" | "json" | "quality">("system");
  const [liveMode, setLiveMode] = useState(true);
  const [diagnostics, setDiagnostics] = useState(true);
  const [status, setStatus] = useState("Ready");
  const [debouncedPrompt, setDebouncedPrompt] = useState("");

  // Security Alert State
  const [securityFindings, setSecurityFindings] = useState<any[]>([]);
  const [redactedText, setRedactedText] = useState("");
  const [pendingText, setPendingText] = useState(""); // Text waiting to be sent to V2

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
      // 2. Perform Request based on Mode
      let data = null;

      // Step A: offline/hybrid check (always needed for security/diagnostics)
      // Even in Live Mode, we might want to check IR via V1 or V2 before showing result

      const checkSecurity = (data: any, isV1: boolean) => {
        // V1 returns the IR object directly. V2 returns { ir: ... } wrapper.
        // We need to inspect the correct location for metadata.
        const ir = isV1 ? data : data.ir;

        if (ir?.metadata?.security && !ir.metadata.security.is_safe) {
          setSecurityFindings(ir.metadata.security.findings);
          setRedactedText(ir.metadata.security.redacted_text);
          setPendingText(textToCompile);
          setLoading(false);
          setStatus("Security Alert Detected");
          return true;
        }
        return false;
      };

      if (!liveMode) {
        // OFFLINE MODE
        const resV1 = await fetch("http://127.0.0.1:8080/compile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: textToCompile, diagnostics, v2: false, render_v2_prompts: true }),
        });

        if (resV1.ok) {
          data = await resV1.json();
          // V1 response is CompileResponse (same as V2)
          if (checkSecurity(data, false)) return; // treat as structured response (isV1=false effectively)

          setResult(data);
          setStatus("Reasoning with Advanced AI...");
        }
      } else {
        // LIVE MODE (Default)
        setStatus("AI Thinking...");

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 190000);

        try {
          const resV2 = await fetch("http://127.0.0.1:8080/compile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: textToCompile, diagnostics, v2: true, render_v2_prompts: true }),
            signal: controller.signal,
          });
          clearTimeout(timeoutId);

          if (!resV2.ok) throw new Error(`API Error: ${resV2.status}`);

          data = await resV2.json();
          // V2 response is { ir: ..., system_prompt: ... }
          if (checkSecurity(data, false)) return;

          setResult(data);
          setStatus(`Done in ${data.processing_ms}ms`);
        } catch (e: any) {
          if (e.name === 'AbortError') throw new Error("Timeout: AI Model took too long.");
          throw e;
        }
      }

    } catch (e: any) {
      console.error(e);
      setStatus(`Error: ${e.message || "Connection Failed"}`);
    } finally {
      // Only unset loading if we didn't trigger security alert (which handles its own loading state)
      // Actually checkSecurity sets loading=false if blocked.
      // We can safely set loading=false here if we are NOT blocked, but how to know?
      // Simple fix: checkSecurity logic handles the 'return', so if we are here, we are either done or errored.
      // But if we returned early, finally block still runs? Yes.
      // So we need to be careful not to hide the modal.
      // Let's rely on setStatus/Alert state.
      if (status !== "Security Alert Detected") {
        setLoading(false);
      }
    }
  }, [prompt, diagnostics, liveMode]);

  const handleSecurityDecision = async (useRedacted: boolean) => {
    setSecurityFindings([]); // Close modal
    const textToUse = useRedacted ? redactedText : pendingText;

    // Resume Step B (V2 Request)
    setLoading(true);
    setStatus("Resuming with " + (useRedacted ? "Safe" : "Unsafe") + " text...");

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 190000);

      const resV2 = await fetch("http://127.0.0.1:8080/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textToUse, diagnostics, v2: true, render_v2_prompts: true }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!resV2.ok) throw new Error(`API Error: ${resV2.status}`);

      const dataV2 = await resV2.json();
      setResult(dataV2);
      setStatus(`Done in ${dataV2.processing_ms}ms`);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex h-screen flex-col items-center justify-center p-4 md:p-8 relative overflow-hidden">

      {/* Security Alert Modal */}
      {securityFindings.length > 0 && (
        <SecurityAlert
          findings={securityFindings}
          redactedText={redactedText}
          onProceedRedacted={() => handleSecurityDecision(true)}
          onProceedOriginal={() => handleSecurityDecision(false)}
          onCancel={() => {
            setSecurityFindings([]);
            setLoading(false);
            setStatus("Cancelled");
          }}
        />
      )}
      {/* Ambient Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-blue-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-purple-600/10 blur-[120px] pointer-events-none" />

      {/* Floating Main Container */}
      <div className="glass w-full max-w-7xl h-full max-h-[90vh] rounded-3xl flex flex-col shadow-2xl overflow-hidden animate-fade-in ring-1 ring-white/10">

        {/* Header */}
        <header className="border-b border-white/5 bg-black/20 p-4 flex items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">P</div>
            <div>
              <h1 className="font-semibold text-lg tracking-tight text-white">Prompt Compiler</h1>
              <div className="text-[10px] text-zinc-400 font-mono tracking-wider uppercase opacity-70">AI Optimized</div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className={`px-3 py-1.5 rounded-full text-xs font-medium border flex items-center gap-2 transition-all duration-300 ${liveMode ? 'bg-green-500/10 border-green-500/30 text-green-400' : 'bg-zinc-800/50 border-zinc-700 text-zinc-400'}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${liveMode ? 'bg-green-400 animate-pulse' : 'bg-zinc-500'}`} />
              {liveMode ? 'LIVE SYNC' : 'OFFLINE'}
            </div>

            <div className="text-xs font-mono text-zinc-500 bg-black/30 px-3 py-1.5 rounded-lg border border-white/5 min-w-[100px] text-center">
              {status}
            </div>
          </div>
        </header>

        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          {/* Left Panel: Input */}
          <div className="w-full md:w-[35%] p-5 flex flex-col gap-5 border-r border-white/5 bg-black/10">

            <div className="flex-1 flex flex-col relative group">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 rounded-2xl pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity duration-500" />
              <textarea
                className="flex-1 w-full bg-black/20 p-5 rounded-2xl border border-white/10 resize-none focus:outline-none focus:ring-1 focus:ring-blue-500/50 font-mono text-sm leading-relaxed text-zinc-200 placeholder-zinc-600 transition-all shadow-inner"
                placeholder="Describe your prompt idea here... e.g. 'Act as a senior python dev teaching FastAPI'"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-4">
              <button
                onClick={() => handleGenerate()}
                disabled={loading}
                className="w-full px-4 py-3 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-blue-500/20"
              >
                {loading ? (
                  <span className="animate-pulse">Thinking...</span>
                ) : (
                  <>Generate <span className="group-hover:translate-x-0.5 transition-transform">→</span></>
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
          <div className="w-full md:w-[65%] flex flex-col bg-black/20 relative">

            {/* ── Compiler Output View ── */}
            {result ? (
              <>
                {/* Tabs */}
                <div className="flex border-b border-white/5 px-4 pt-4 gap-2 overflow-x-auto no-scrollbar">
                  {(["system", "user", "plan", "expanded", "json", "quality"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`px-4 py-2 text-[13px] font-medium rounded-t-lg transition-all relative whitespace-nowrap ${activeTab === tab
                        ? "text-white bg-white/5 border-t border-x border-white/5"
                        : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"
                        }`}
                    >
                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                  ))}
                </div>

                {/* Content */}
                <div className="flex-1 p-0 overflow-hidden relative group bg-black/20">
                  {activeTab !== "quality" && activeTab !== "json" && (
                    <>
                      <div className="absolute top-4 right-6 z-10 opacity-50 hover:opacity-100 transition-opacity">
                        {result.system_prompt_v2 ? (
                          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-500/10 border border-blue-500/20">
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_5px_rgba(96,165,250,0.8)]" />
                            <span className="text-[10px] text-blue-200 font-medium">Reasoning Model</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-zinc-800/50 border border-zinc-700/50">
                            <div className="w-1.5 h-1.5 rounded-full bg-zinc-400" />
                            <span className="text-[10px] text-zinc-400 font-medium">Standard</span>
                          </div>
                        )}
                      </div>

                      <textarea
                        className="w-full h-full bg-transparent p-6 font-mono text-sm text-zinc-300 resize-none focus:outline-none leading-relaxed selection:bg-blue-500/30"
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
                        className="absolute bottom-6 right-6 bg-blue-600 hover:bg-blue-500 text-white p-3 rounded-xl shadow-lg shadow-blue-500/20 transition-all hover:scale-105 active:scale-95 z-20"
                        title="Copy to Clipboard"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                      </button>
                    </>
                  )}

                  {/* JSON Structured View */}
                  {activeTab === "json" && (
                    <div className="absolute inset-0 bg-transparent z-20 overflow-auto p-6">
                      <pre className="bg-black/30 p-4 rounded-xl border border-white/5 text-xs font-mono text-zinc-300 overflow-auto h-full shadow-inner">
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Quality Coach Overlay/View */}
                  {activeTab === "quality" && (
                    <div className="absolute inset-0 bg-transparent z-20">
                      <QualityCoach prompt={prompt} onUpdatePrompt={setPrompt} />
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-zinc-600 gap-6 p-10 text-center opacity-60">
                <div className="relative group">
                  <div className="absolute inset-0 bg-blue-500/30 blur-[40px] rounded-full group-hover:bg-blue-500/50 transition-all duration-700" />
                  <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-zinc-800 to-black border border-white/10 flex items-center justify-center shadow-2xl skew-y-3 group-hover:skew-y-0 transition-transform duration-500">
                    <span className="text-4xl filter drop-shadow-[0_0_10px_rgba(255,255,255,0.3)]">💠</span>
                  </div>
                </div>
                <div className="max-w-xs space-y-2">
                  <h3 className="text-zinc-200 font-medium tracking-wide">Ready to Compile</h3>
                  <p className="text-sm text-zinc-500">Enter a prompt to generate optimized system instructions, planning, and structured reasoning.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
