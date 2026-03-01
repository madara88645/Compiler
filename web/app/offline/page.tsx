"use client";

import { useState, useEffect, useCallback } from "react";
import ContextManager from "../components/ContextManager";
import QualityCoach from "../components/QualityCoach";
import { API_BASE } from "@/config";

import InfoButton from "../components/InfoButton";

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

export default function OfflinePage() {
    const [prompt, setPrompt] = useState("");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<CompileResponse | null>(null);
    const [activeTab, setActiveTab] = useState<"system" | "user" | "plan" | "expanded" | "json" | "quality">("system");
    // FORCE OFFLINE MODE
    const liveMode = false;
    // Diagnostics ON by default
    const diagnostics = true;

    const [status, setStatus] = useState("Ready");

    const handleGenerate = useCallback(async (textOverride?: string) => {
        const textToCompile = typeof textOverride === 'string' ? textOverride : prompt;
        if (!textToCompile.trim()) return;

        setLoading(true);
        setStatus("Compiling (Offline)...");

        try {
            // Step A: Fast V1 Request Only (Heuristics) -> Now V2
            const resV1 = await fetch(`${API_BASE}/compile`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: textToCompile, diagnostics, v2: false, render_v2_prompts: true }),
            });

            if (resV1.ok) {
                const dataV1 = await resV1.json();
                setResult(dataV1);
                setStatus(`Done in ${dataV1.processing_ms}ms`);
            } else {
                setStatus("Error: Offline Compilation Failed");
            }

        } catch (e: any) {
            console.error(e);
            setStatus(`Error: ${e.message || "Connection Failed"}`);
        } finally {
            setLoading(false);
        }
    }, [prompt]);

    return (
        <main className="flex h-screen flex-col items-center justify-center p-4 md:p-8 relative overflow-hidden">
            {/* Darker Ambient Background for Offline Feel */}
            <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-zinc-600/10 blur-[120px] pointer-events-none" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-slate-600/10 blur-[120px] pointer-events-none" />

            {/* Floating Main Container */}
            <div className="glass w-full max-w-7xl h-full max-h-[90vh] rounded-3xl flex flex-col shadow-2xl overflow-hidden animate-fade-in ring-1 ring-white/10">

                {/* Header */}
                <header className="border-b border-white/5 bg-black/40 p-4 flex items-center justify-between backdrop-blur-md">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-3">
                            <div className="h-9 w-9 bg-zinc-700 rounded-xl flex items-center justify-center font-bold text-white shadow-lg">🔌</div>
                            <div>
                                <h1 className="font-semibold text-lg tracking-tight text-white">Offline Compiler</h1>
                                <div className="text-[10px] text-zinc-500 font-mono tracking-wider uppercase opacity-70">Heuristic Engine V2</div>
                            </div>
                        </div>
                        <InfoButton
                            title="Offline Compiler"
                            description="A fast, local-only version of the Prompt Compiler that uses deterministic heuristics instead of an LLM. It's secure, instant, and requires no API keys."
                        />
                    </div>

                    <div className="flex items-center gap-4">
                        {/* Forced Offline Badge */}
                        <div className="px-3 py-1.5 rounded-full text-xs font-medium border flex items-center gap-2 bg-zinc-800/50 border-zinc-700 text-zinc-400">
                            <div className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
                            OFFLINE MODE
                        </div>

                        <div className="text-xs font-mono text-zinc-500 bg-black/30 px-3 py-1.5 rounded-lg border border-white/5 min-w-[100px] text-center">
                            {status}
                        </div>
                    </div>
                </header>

                <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
                    {/* Left Panel: Input */}
                    <div className="w-full md:w-[35%] p-5 flex flex-col gap-5 border-r border-white/5 bg-black/20">

                        <div className="flex-1 flex flex-col relative group">
                            <textarea
                                className="flex-1 w-full bg-black/20 p-5 rounded-2xl border border-white/10 resize-none focus:outline-none focus:ring-1 focus:ring-zinc-500/50 font-mono text-sm leading-relaxed text-zinc-200 placeholder-zinc-600 transition-all shadow-inner"
                                placeholder="Enter prompt (offline heuristics active)..."
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                            />
                        </div>

                        <div className="flex flex-col gap-4">
                            {/* No Toggles - Just Generate */}
                            <div className="grid grid-cols-1 gap-3">
                                <button
                                    onClick={() => handleGenerate()}
                                    disabled={loading}
                                    className="px-4 py-3 text-sm font-bold bg-zinc-800 hover:bg-zinc-700 text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group border border-white/5"
                                >
                                    {loading ? (
                                        <span className="animate-pulse">Processing...</span>
                                    ) : (
                                        <>Run Heuristics <span className="group-hover:translate-x-0.5 transition-transform">→</span></>
                                    )}
                                </button>
                            </div>
                        </div>

                        <ContextManager onInsertContext={(text) => setPrompt(prev => prev + "\n\n---\nContext:\n" + text)} />
                    </div>

                    {/* Right Panel: Output */}
                    <div className="w-full md:w-[65%] flex flex-col bg-black/30 relative">
                        {result ? (
                            <>
                                <div className="flex border-b border-white/5 px-4 pt-4 gap-2 overflow-x-auto no-scrollbar">
                                    {(["system", "user", "plan", "expanded", "json"] as const).map((tab) => (
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

                                <div className="flex-1 p-0 overflow-hidden relative group bg-black/20">
                                    {/* Badge */}
                                    <div className="absolute top-4 right-6 z-10 opacity-50 hover:opacity-100 transition-opacity">
                                        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-zinc-800/50 border border-zinc-700/50">
                                            <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                                            <span className="text-[10px] text-zinc-400 font-medium">Reasoning V2</span>
                                        </div>
                                    </div>

                                    {activeTab !== "quality" && activeTab !== "json" && (
                                        <>
                                            <textarea
                                                className="w-full h-full bg-transparent p-6 font-mono text-sm text-zinc-300 resize-none focus:outline-none leading-relaxed selection:bg-orange-500/30"
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
                                                    activeTab === "system" ? result.system_prompt :
                                                        activeTab === "user" ? result.user_prompt :
                                                            activeTab === "plan" ? result.plan :
                                                                result.expanded_prompt
                                                )}
                                                className="absolute bottom-6 right-6 bg-zinc-700 hover:bg-zinc-600 text-white p-3 rounded-xl shadow-lg transition-all hover:scale-105 active:scale-95 z-20"
                                                title="Copy"
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                                            </button>
                                        </>
                                    )}

                                    {activeTab === "json" && (
                                        <div className="absolute inset-0 bg-transparent z-20 overflow-auto p-6">
                                            <pre className="bg-black/30 p-4 rounded-xl border border-white/5 text-xs font-mono text-zinc-300 overflow-auto h-full shadow-inner">
                                                {JSON.stringify(result, null, 2)}
                                            </pre>
                                        </div>
                                    )}
                                </div>
                            </>
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center text-zinc-600 gap-6 p-10 text-center opacity-60">
                                <div className="text-6xl grayscale opacity-50">🔌</div>
                                <div className="max-w-xs space-y-2">
                                    <h3 className="text-zinc-200 font-medium tracking-wide">Offline Mode</h3>
                                    <p className="text-sm text-zinc-500">Fast, local heuristic compilation without LLM calls.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </main>
    );
}
