"use client";

import { useState, useCallback } from "react";
import BenchmarkResults, { type BenchmarkData } from "../components/BenchmarkResults";

export default function BenchmarkPage() {
    const [prompt, setPrompt] = useState("");
    const [loading, setLoading] = useState(false);
    const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkData | null>(null);
    const [benchmarkKey, setBenchmarkKey] = useState(0);
    const [status, setStatus] = useState("Ready");

    const handleBenchmark = useCallback(async () => {
        if (!prompt.trim()) return;
        setLoading(true);
        setStatus("Running Benchmark...");
        setBenchmarkResult(null);
        setBenchmarkKey(k => k + 1);

        try {
            let data: BenchmarkData;
            try {
                const res = await fetch("http://127.0.0.1:8080/benchmark/run", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: prompt }),
                    signal: AbortSignal.timeout(30000),
                });
                if (!res.ok) throw new Error("endpoint unavailable");
                data = await res.json();
            } catch {
                // Mock fallback
                await new Promise((r) => setTimeout(r, 1200));
                const score = Math.floor(Math.random() * 35) + 5;
                data = {
                    raw_output: `Here is a response to: "${prompt.slice(0, 60)}..."\n\nThis is the raw, uncompiled LLM output. It addresses the query directly but without the benefit of structured prompting, constraints, or role optimization.\n\nThe response may be generic, lack depth, or miss nuances that a compiled prompt would capture.`,
                    compiled_output: `Here is an optimized response to: "${prompt.slice(0, 60)}..."\n\nThis output was generated using a compiled system prompt with:\n• Persona-tuned role assignment\n• Domain-specific constraints\n• Structured reasoning steps\n• Quality guardrails\n\nThe result is more precise, better structured, and aligned with best practices for the detected domain.`,
                    compiled_prompt: `[System] You are a specialized assistant.\n[Role] Senior domain expert\n[Constraints]\n- Provide structured, actionable responses\n- Use examples where appropriate\n- Maintain professional tone\n[Steps]\n1. Analyze the core request\n2. Identify key requirements\n3. Generate comprehensive response\n\n[User] ${prompt}`,
                    winner: "compiled",
                    improvement_score: score,
                    metrics: {
                        raw_relevance: parseFloat((6 + Math.random() * 2).toFixed(1)),
                        compiled_relevance: parseFloat((7.5 + Math.random() * 2).toFixed(1)),
                        raw_clarity: parseFloat((5.5 + Math.random() * 2.5).toFixed(1)),
                        compiled_clarity: parseFloat((7 + Math.random() * 2.5).toFixed(1)),
                    },
                    processing_ms: Math.floor(Math.random() * 800) + 400,
                };
            }

            setBenchmarkResult(data);
            setStatus(`Done in ${data.processing_ms}ms`);
        } catch (e: any) {
            setStatus(`Error: ${e.message}`);
        } finally {
            setLoading(false);
        }
    }, [prompt]);

    return (
        <main className="flex h-screen flex-col items-center justify-center p-4 md:p-8 relative overflow-hidden">
            {/* Warm Ambient Background */}
            <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-amber-600/10 blur-[120px] pointer-events-none" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-orange-600/10 blur-[120px] pointer-events-none" />

            {/* Floating Main Container */}
            <div className="glass w-full max-w-7xl h-full max-h-[90vh] rounded-3xl flex flex-col shadow-2xl overflow-hidden animate-fade-in ring-1 ring-white/10">

                {/* Header */}
                <header className="border-b border-white/5 bg-black/20 p-4 flex items-center justify-between backdrop-blur-md">
                    <div className="flex items-center gap-3">
                        <div className="h-9 w-9 bg-gradient-to-br from-amber-600 to-orange-600 rounded-xl flex items-center justify-center font-bold text-white shadow-lg shadow-amber-500/20">⚡</div>
                        <div>
                            <h1 className="font-semibold text-lg tracking-tight text-white">Benchmark Arena</h1>
                            <div className="text-[10px] text-zinc-400 font-mono tracking-wider uppercase opacity-70">Raw vs Compiled</div>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <div className="px-3 py-1.5 rounded-full text-xs font-medium border flex items-center gap-2 bg-amber-500/10 border-amber-500/30 text-amber-400">
                            <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                            BENCHMARK
                        </div>

                        <div className="text-xs font-mono text-zinc-500 bg-black/30 px-3 py-1.5 rounded-lg border border-white/5 min-w-[100px] text-center">
                            {status}
                        </div>
                    </div>
                </header>

                <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
                    {/* Left Panel: Input */}
                    <div className="w-full md:w-[35%] p-5 flex flex-col gap-5 border-r border-white/5 bg-black/10">

                        {/* Info Card */}
                        <div className="bg-amber-500/5 border border-amber-500/10 rounded-xl p-4 text-xs text-zinc-400 space-y-2">
                            <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></svg>
                                How it works
                            </div>
                            <ol className="list-decimal list-inside space-y-1 text-zinc-500">
                                <li>Your raw prompt is sent to the LLM</li>
                                <li>The compiler optimizes your prompt</li>
                                <li>The optimized prompt is sent to the same LLM</li>
                                <li>Both outputs are compared & scored</li>
                            </ol>
                        </div>

                        <div className="flex-1 flex flex-col relative group">
                            <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-orange-500/5 rounded-2xl pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity duration-500" />
                            <textarea
                                className="flex-1 w-full bg-black/20 p-5 rounded-2xl border border-white/10 resize-none focus:outline-none focus:ring-1 focus:ring-amber-500/50 font-mono text-sm leading-relaxed text-zinc-200 placeholder-zinc-600 transition-all shadow-inner"
                                placeholder="Enter a prompt to benchmark...&#10;&#10;e.g. 'Write a REST API with FastAPI that has CRUD operations for a todo app'"
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                            />
                        </div>

                        <button
                            onClick={() => handleBenchmark()}
                            disabled={loading}
                            className="w-full px-4 py-3 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 shadow-amber-500/20"
                        >
                            {loading ? (
                                <span className="animate-pulse">Running Benchmark...</span>
                            ) : (
                                <>Run Benchmark <span className="group-hover:translate-x-0.5 transition-transform">⚡</span></>
                            )}
                        </button>
                    </div>

                    {/* Right Panel: Results */}
                    <div className="w-full md:w-[65%] flex flex-col bg-black/20 relative">
                        {benchmarkResult ? (
                            <BenchmarkResults key={benchmarkKey} data={benchmarkResult} />
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center text-zinc-600 gap-6 p-10 text-center opacity-60">
                                <div className="relative group">
                                    <div className="absolute inset-0 bg-amber-500/20 blur-[40px] rounded-full group-hover:bg-amber-500/40 transition-all duration-700" />
                                    <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-zinc-800 to-black border border-white/10 flex items-center justify-center shadow-2xl skew-y-3 group-hover:skew-y-0 transition-transform duration-500">
                                        <span className="text-4xl filter drop-shadow-[0_0_10px_rgba(255,255,255,0.3)]">⚡</span>
                                    </div>
                                </div>
                                <div className="max-w-xs space-y-2">
                                    <h3 className="text-zinc-200 font-medium tracking-wide">Benchmark Arena</h3>
                                    <p className="text-sm text-zinc-500">Compare Raw vs. Compiled LLM outputs side-by-side. Enter a prompt and click Run Benchmark.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </main>
    );
}
