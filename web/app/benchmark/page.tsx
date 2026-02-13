"use client";

import { useState, useCallback, useMemo } from "react";
import {
    Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend
} from 'recharts';
import DiffViewer from "../components/DiffViewer";

type BenchmarkPayload = {
    raw_output: string;
    compiled_output: string;
    metrics: {
        safety: { raw: number, compiled: number };
        clarity: { raw: number, compiled: number };
        conciseness: { raw: number, compiled: number };
    };
    processing_ms: number;
    winner: "compiled" | "raw";
    improvement_score: number;
};

export default function BenchmarkPage() {
    const [prompt, setPrompt] = useState("");
    const [loading, setLoading] = useState(false);
    const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkPayload | null>(null);
    const [selectedModel, setSelectedModel] = useState("mock");
    const [status, setStatus] = useState("Ready");

    // Model name mapping for the API (Groq-compatible model IDs)
    const modelApiMap: Record<string, string> = {
        "llama-3.3-70b": "llama-3.3-70b-versatile",
        "llama-3.1-8b": "llama-3.1-8b-instant",
        "llama4-scout": "meta-llama/llama-4-scout-17b-16e-instruct",
        "llama4-maverick": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "gpt-oss-120b": "openai/gpt-oss-120b",
        "gpt-oss-20b": "openai/gpt-oss-20b",
        "mistral-saba": "mistral-saba-24b",
        "compound": "compound-beta",
    };

    const _generateMockResult = useCallback((): BenchmarkPayload => {
        const raw = `Here is a response to: "${prompt.slice(0, 40)}..."\n\nIt's a straightforward answer. The model tries to be helpful but might miss specific constraints or tone requirements. It generally covers the basics but lacks structure.`;
        const compiled = `Here is an OPTIMIZED response to: "${prompt.slice(0, 40)}..."\n\n[Structure]\n1. Direct Answer\n2. Detailed Explanation\n3. Examples\n\n[Content]\nThis response is structured, follows strict constraints, and uses a professional tone. It ensures all safety guidelines are met and clarifies ambiguities before answering.`;
        return {
            raw_output: raw,
            compiled_output: compiled,
            metrics: {
                safety: { raw: +(6 + Math.random() * 2).toFixed(1), compiled: +(9 + Math.random()).toFixed(1) },
                clarity: { raw: +(5 + Math.random() * 2).toFixed(1), compiled: +(8 + Math.random() * 2).toFixed(1) },
                conciseness: { raw: +(4 + Math.random() * 3).toFixed(1), compiled: +(7 + Math.random() * 2).toFixed(1) },
            },
            processing_ms: 850 + Math.floor(Math.random() * 400),
            winner: "compiled",
            improvement_score: 35,
        };
    }, [prompt]);

    const handleBenchmark = useCallback(async () => {
        if (!prompt.trim()) return;
        setLoading(true);
        setStatus(`Benchmarking with ${selectedModel}...`);
        setBenchmarkResult(null);

        try {
            // --- Mock Engine: client-side only ---
            if (selectedModel === "mock") {
                await new Promise((r) => setTimeout(r, 1200));
                setBenchmarkResult(_generateMockResult());
                setStatus("Benchmark Complete (Mock)");
                return;
            }

            // --- Real API call ---
            const apiModel = modelApiMap[selectedModel] || selectedModel;
            const res = await fetch("http://127.0.0.1:8080/benchmark/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: prompt, model: apiModel }),
            });

            if (!res.ok) {
                const detail = await res.text().catch(() => "Unknown error");
                throw new Error(`API ${res.status}: ${detail}`);
            }

            const data = await res.json();
            setBenchmarkResult({
                raw_output: data.raw_output,
                compiled_output: data.compiled_output,
                metrics: data.metrics,
                processing_ms: data.processing_ms,
                winner: data.winner,
                improvement_score: data.improvement_score,
            });
            setStatus(`Benchmark Complete (${data.processing_ms}ms)`);

        } catch (e: any) {
            console.warn("Benchmark API error, falling back to mock:", e.message);
            setBenchmarkResult(_generateMockResult());
            setStatus("Benchmark Complete (Fallback Mock)");
        } finally {
            setLoading(false);
        }
    }, [prompt, selectedModel, _generateMockResult]);

    const chartData = useMemo(() => {
        if (!benchmarkResult) return [];
        return [
            { subject: 'Safety', A: benchmarkResult.metrics.safety.raw, B: benchmarkResult.metrics.safety.compiled, fullMark: 10 },
            { subject: 'Clarity', A: benchmarkResult.metrics.clarity.raw, B: benchmarkResult.metrics.clarity.compiled, fullMark: 10 },
            { subject: 'Conciseness', A: benchmarkResult.metrics.conciseness.raw, B: benchmarkResult.metrics.conciseness.compiled, fullMark: 10 },
        ];
    }, [benchmarkResult]);

    return (
        <main className="flex h-screen flex-col items-center justify-center p-4 md:p-8 relative overflow-hidden bg-[#050505]">
            <div className="absolute top-[-20%] left-[-20%] w-[50vw] h-[50vw] rounded-full bg-amber-600/10 blur-[150px] pointer-events-none" />
            <div className="absolute bottom-[-20%] right-[-20%] w-[50vw] h-[50vw] rounded-full bg-orange-600/10 blur-[150px] pointer-events-none" />

            {/* Container */}
            <div className="glass w-full max-w-7xl h-full max-h-[95vh] rounded-3xl flex flex-col shadow-2xl overflow-hidden ring-1 ring-white/10 z-10">

                {/* Header */}
                <header className="border-b border-white/5 bg-black/40 p-4 flex items-center justify-between backdrop-blur-md shrink-0">
                    <div className="flex items-center gap-4">
                        <div className="h-10 w-10 bg-gradient-to-br from-amber-600 to-orange-600 rounded-xl flex items-center justify-center font-bold text-white shadow-lg shadow-amber-500/20 text-xl">⚡</div>
                        <div>
                            <h1 className="font-bold text-xl tracking-tight text-white/90">Battle Arena</h1>
                            <div className="text-[10px] text-zinc-500 font-mono tracking-wider uppercase">Raw vs Compiled Benchmark</div>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        {/* Model Selector */}
                        <div className="flex items-center gap-2 bg-black/30 rounded-lg p-1 border border-white/5">
                            <span className="text-[10px] font-medium text-zinc-500 uppercase px-2">Model</span>
                            <select
                                value={selectedModel}
                                onChange={(e) => setSelectedModel(e.target.value)}
                                className="text-xs text-zinc-200 rounded px-2 py-1.5 focus:outline-none border-none cursor-pointer transition-colors"
                                style={{ backgroundColor: "#1a1a1a" }}
                            >
                                <option value="mock" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>🧪 Mock Engine</option>
                                <optgroup label="── Meta Llama ──" style={{ backgroundColor: "#1a1a1a", color: "#888" }}>
                                    <option value="llama-3.3-70b" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>🦙 Llama 3.3 70B</option>
                                    <option value="llama-3.1-8b" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>⚡ Llama 3.1 8B (Fast)</option>
                                    <option value="llama4-scout" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>🔭 Llama 4 Scout</option>
                                    <option value="llama4-maverick" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>🚀 Llama 4 Maverick</option>
                                </optgroup>
                                <optgroup label="── OpenAI GPT-OSS ──" style={{ backgroundColor: "#1a1a1a", color: "#888" }}>
                                    <option value="gpt-oss-120b" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>🧠 GPT-OSS 120B</option>
                                    <option value="gpt-oss-20b" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>💡 GPT-OSS 20B</option>
                                </optgroup>
                                <optgroup label="── Other ──" style={{ backgroundColor: "#1a1a1a", color: "#888" }}>
                                    <option value="mistral-saba" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>🌊 Mistral Saba 24B</option>
                                    <option value="compound" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>🔮 Groq Compound</option>
                                </optgroup>
                            </select>
                        </div>

                        <div className="px-3 py-1.5 rounded-full text-xs font-bold border flex items-center gap-2 bg-amber-500/10 border-amber-500/30 text-amber-400">
                            {status}
                        </div>
                    </div>
                </header>

                <div className="flex-1 flex overflow-hidden">
                    {/* Left: Controls & Input */}
                    <div className="w-[350px] flex flex-col border-r border-white/5 bg-black/20 p-5 gap-5 shrink-0 z-20">
                        <div className="flex-1 relative group">
                            <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-orange-500/5 rounded-2xl pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity duration-500" />
                            <textarea
                                className="w-full h-full bg-black/30 p-4 rounded-xl border border-white/10 resize-none focus:outline-none focus:ring-1 focus:ring-amber-500/50 font-mono text-sm leading-relaxed text-zinc-300 placeholder-zinc-600 transition-all shadow-inner"
                                placeholder="Enter a prompt to start the battle...&#10;&#10;e.g. 'Write a python script to scrape data'"
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                            />
                        </div>
                        <button
                            onClick={handleBenchmark}
                            disabled={loading || !prompt.trim()}
                            className="w-full py-4 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 shadow-amber-500/20"
                        >
                            {loading ? <span className="animate-pulse">FIGHTING...</span> : "START BATTLE ⚡"}
                        </button>
                    </div>

                    {/* Right: Visualization */}
                    <div className="flex-1 flex flex-col bg-black/10 relative overflow-hidden">
                        {benchmarkResult ? (
                            <div className="flex-1 flex flex-col h-full overflow-hidden">
                                {/* Top Half: Visuals */}
                                <div className="h-[40%] min-h-[300px] border-b border-white/5 flex">
                                    {/* Metrics Chart */}
                                    <div className="flex-1 p-4 relative flex items-center justify-center">
                                        <h3 className="absolute top-4 left-4 text-xs font-semibold text-zinc-500 uppercase">Performance Radar</h3>
                                        <div className="w-full h-full max-w-[400px]">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <RadarChart outerRadius="70%" data={chartData}>
                                                    <PolarGrid stroke="rgba(255,255,255,0.1)" />
                                                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#71717a', fontSize: 10 }} />
                                                    <PolarRadiusAxis angle={30} domain={[0, 10]} tick={false} axisLine={false} />
                                                    <Radar name="Raw" dataKey="A" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.3} />
                                                    <Radar name="Compiled" dataKey="B" stroke="#10b981" fill="#10b981" fillOpacity={0.4} />
                                                    <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                                                </RadarChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>

                                    {/* Winner Stats */}
                                    <div className="w-[300px] border-l border-white/5 bg-black/10 p-6 flex flex-col items-center justify-center gap-4">
                                        <div className="text-center space-y-1">
                                            <div className="text-xs font-mono text-zinc-500 uppercase">Winner</div>
                                            <div className={`text-2xl font-black tracking-tighter ${benchmarkResult.winner === 'compiled' ? 'text-emerald-400' : 'text-amber-400'}`}>
                                                {benchmarkResult.winner === 'compiled' ? "COMPILED PROMPT" : "RAW PROMPT"}
                                            </div>
                                        </div>

                                        <div className="w-full h-px bg-white/10" />

                                        <div className="text-center space-y-1">
                                            <div className="text-xs font-mono text-zinc-500 uppercase">Improvement</div>
                                            <div className="text-4xl font-black text-emerald-400 drop-shadow-lg">
                                                +{benchmarkResult.improvement_score}%
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Bottom Half: Diff Viewer */}
                                <div className="flex-1 flex flex-col min-h-0 bg-black/20">
                                    <div className="flex-1 overflow-hidden p-4">
                                        <DiffViewer oldText={benchmarkResult.raw_output} newText={benchmarkResult.compiled_output} />
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center text-zinc-600 gap-6 p-10 text-center opacity-40">
                                <div className="text-6xl filter drop-shadow-2xl">⚡</div>
                                <div className="max-w-xs space-y-2">
                                    <h3 className="text-zinc-300 font-medium tracking-wide">Battle Arena Empty</h3>
                                    <p className="text-sm text-zinc-500">Enter a prompt and select a model to see the visual comparison.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </main>
    );
}
