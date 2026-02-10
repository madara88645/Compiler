"use client";

import { useState } from "react";

export type BenchmarkData = {
    raw_output: string;
    compiled_output: string;
    compiled_prompt: string;
    winner: "compiled" | "raw" | "tie";
    improvement_score: number; // e.g. 20 means +20%
    metrics: {
        raw_relevance: number;
        compiled_relevance: number;
        raw_clarity: number;
        compiled_clarity: number;
    };
    processing_ms: number;
};

interface BenchmarkResultsProps {
    data: BenchmarkData;
}

export default function BenchmarkResults({ data }: BenchmarkResultsProps) {
    const [promptOpen, setPromptOpen] = useState(false);

    const sign = data.improvement_score >= 0 ? "+" : "";
    const isCompiledWinner = data.winner === "compiled";
    const isTie = data.winner === "tie";

    return (
        <div className="flex flex-col h-full overflow-hidden animate-fade-in">

            {/* Winner Banner */}
            <div className="px-5 py-4 border-b border-white/5 bg-black/20 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="text-sm font-medium text-zinc-400">Result</div>

                    {isTie ? (
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-700/40 border border-zinc-600/30 animate-slide-in">
                            <span className="text-sm">🤝</span>
                            <span className="text-xs font-bold text-zinc-300 tracking-wide">TIE</span>
                        </div>
                    ) : (
                        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full animate-slide-in ${isCompiledWinner
                                ? "bg-emerald-500/15 border border-emerald-500/30"
                                : "bg-amber-500/15 border border-amber-500/30"
                            }`}>
                            <span className="text-sm">{isCompiledWinner ? "🏆" : "⚡"}</span>
                            <span className={`text-xs font-bold tracking-wide ${isCompiledWinner ? "text-emerald-400" : "text-amber-400"
                                }`}>
                                {isCompiledWinner ? "COMPILED WINS" : "RAW WINS"}
                            </span>
                        </div>
                    )}

                    {/* Improvement Score Badge */}
                    {!isTie && (
                        <div className={`px-3 py-1 rounded-lg text-sm font-bold tracking-tight animate-slide-in ${data.improvement_score >= 0
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : "bg-red-500/10 text-red-400 border border-red-500/20"
                            }`}>
                            {sign}{data.improvement_score}%
                        </div>
                    )}
                </div>

                <div className="text-[11px] font-mono text-zinc-500">
                    {data.processing_ms}ms
                </div>
            </div>

            {/* Metrics Bar */}
            <div className="px-5 py-3 border-b border-white/5 bg-black/10 flex gap-6">
                <MetricPill label="Relevance" raw={data.metrics.raw_relevance} compiled={data.metrics.compiled_relevance} />
                <MetricPill label="Clarity" raw={data.metrics.raw_clarity} compiled={data.metrics.compiled_clarity} />
            </div>

            {/* Collapsible Compiled Prompt */}
            <div className="border-b border-white/5">
                <button
                    onClick={() => setPromptOpen(!promptOpen)}
                    className="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors group"
                >
                    <div className="flex items-center gap-2">
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="14" height="14"
                            viewBox="0 0 24 24"
                            fill="none" stroke="currentColor"
                            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                            className={`text-zinc-500 transition-transform duration-200 ${promptOpen ? "rotate-90" : ""}`}
                        >
                            <path d="m9 18 6-6-6-6" />
                        </svg>
                        <span className="text-xs font-medium text-zinc-400 group-hover:text-zinc-300 transition-colors">
                            Compiled Prompt (Intermediate)
                        </span>
                    </div>
                    <div className="px-2 py-0.5 rounded text-[10px] font-mono text-zinc-600 bg-black/20 border border-white/5">
                        {data.compiled_prompt.length} chars
                    </div>
                </button>

                {promptOpen && (
                    <div className="px-5 pb-4 animate-fade-in">
                        <pre className="bg-black/30 p-4 rounded-xl border border-white/5 text-xs font-mono text-zinc-400 overflow-auto max-h-48 shadow-inner leading-relaxed whitespace-pre-wrap">
                            {data.compiled_prompt}
                        </pre>
                    </div>
                )}
            </div>

            {/* Two-Column Output */}
            <div className="flex-1 flex overflow-hidden min-h-0">
                {/* Raw Output */}
                <div className="flex-1 flex flex-col border-r border-white/5 min-w-0">
                    <div className="px-4 py-2.5 border-b border-white/5 bg-black/20 flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${data.winner === "raw" ? "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.6)]" : "bg-zinc-600"}`} />
                            <span className="text-xs font-semibold text-zinc-300 tracking-wide">Raw LLM Output</span>
                        </div>
                        <button
                            onClick={() => navigator.clipboard.writeText(data.raw_output)}
                            className="text-zinc-600 hover:text-zinc-400 transition-colors p-1"
                            title="Copy raw output"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                        </button>
                    </div>
                    <div className="flex-1 overflow-auto p-4">
                        <pre className="text-sm font-mono text-zinc-400 whitespace-pre-wrap leading-relaxed">{data.raw_output}</pre>
                    </div>
                </div>

                {/* Compiled Output */}
                <div className="flex-1 flex flex-col min-w-0">
                    <div className="px-4 py-2.5 border-b border-white/5 bg-black/20 flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${data.winner === "compiled" ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" : "bg-zinc-600"}`} />
                            <span className="text-xs font-semibold text-zinc-300 tracking-wide">Compiled LLM Output</span>
                        </div>
                        <button
                            onClick={() => navigator.clipboard.writeText(data.compiled_output)}
                            className="text-zinc-600 hover:text-zinc-400 transition-colors p-1"
                            title="Copy compiled output"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                        </button>
                    </div>
                    <div className="flex-1 overflow-auto p-4">
                        <pre className="text-sm font-mono text-zinc-300 whitespace-pre-wrap leading-relaxed">{data.compiled_output}</pre>
                    </div>
                </div>
            </div>
        </div>
    );
}


/* ─── Small helper ───────────────────────────────────── */

function MetricPill({ label, raw, compiled }: { label: string; raw: number; compiled: number }) {
    const diff = compiled - raw;
    const better = diff > 0;
    return (
        <div className="flex items-center gap-2 text-[11px]">
            <span className="text-zinc-500 font-medium">{label}</span>
            <span className="font-mono text-zinc-600">{raw.toFixed(1)}</span>
            <span className="text-zinc-700">→</span>
            <span className={`font-mono font-semibold ${better ? "text-emerald-400" : diff < 0 ? "text-red-400" : "text-zinc-400"}`}>
                {compiled.toFixed(1)}
            </span>
            {diff !== 0 && (
                <span className={`text-[10px] font-bold ${better ? "text-emerald-500/70" : "text-red-500/70"}`}>
                    ({diff > 0 ? "+" : ""}{diff.toFixed(1)})
                </span>
            )}
        </div>
    );
}
