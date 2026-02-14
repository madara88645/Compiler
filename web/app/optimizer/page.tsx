"use client";

import { useState } from "react";
import { API_BASE } from "@/config";

export default function OptimizerPage() {
    const [input, setInput] = useState("");
    const [output, setOutput] = useState("");
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [maxTokens, setMaxTokens] = useState<number>(1000);
    const [maxChars, setMaxChars] = useState<string>("");

    const handleOptimize = async () => {
        if (!input.trim()) return;
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/optimize`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: input,
                    max_tokens: maxTokens,
                    max_chars: maxChars ? parseInt(maxChars) : undefined,
                }),
            });
            const data = await res.json();
            setOutput(data.text);
            setStats({
                before_tokens: data.before_tokens,
                after_tokens: data.after_tokens,
                saved_percent: ((data.before_tokens - data.after_tokens) / data.before_tokens * 100).toFixed(1)
            });
        } catch (e) {
            console.error(e);
            setOutput("Error optimization failed.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="h-full flex flex-col p-6 max-w-6xl mx-auto gap-6 animate-fade-in">
            <header className="flex items-center justify-between border-b border-white/5 pb-4">
                <div>
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                        Token Optimizer
                    </h1>
                    <p className="text-sm text-zinc-500">Reduce LLM costs without losing meaning.</p>
                </div>

                {/* Controls */}
                <div className="flex items-center gap-4 bg-zinc-900/50 p-2 rounded-xl border border-white/5">
                    <div className="flex flex-col gap-1 px-2">
                        <label className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">Max Tokens</label>
                        <input
                            type="range" min="100" max="4096" step="100"
                            value={maxTokens}
                            onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                            className="w-32 h-1 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                        />
                        <span className="text-xs text-emerald-400 font-mono text-right">{maxTokens}</span>
                    </div>

                    <button
                        onClick={handleOptimize}
                        disabled={loading}
                        className="px-6 py-2 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-bold rounded-lg shadow-lg shadow-emerald-500/20 transition-all active:scale-95 disabled:opacity-50"
                    >
                        {loading ? "Compressing..." : "⚡ Compress"}
                    </button>
                </div>
            </header>

            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6 min-h-0">
                {/* Input */}
                <div className="flex flex-col gap-2">
                    <span className="text-xs text-zinc-500 uppercase font-bold tracking-wider ml-1">Original Prompt</span>
                    <div className="flex-1 bg-zinc-900/30 rounded-2xl border border-white/5 p-4 focus-within:ring-1 focus-within:ring-emerald-500/50 transition-all">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Paste your verbose prompt here..."
                            className="w-full h-full bg-transparent resize-none outline-none text-zinc-300 font-mono text-sm placeholder:text-zinc-700"
                        />
                    </div>
                    {stats && (
                        <div className="text-xs text-zinc-500 text-right font-mono">
                            Tokens: {stats.before_tokens}
                        </div>
                    )}
                </div>

                {/* Output */}
                <div className="flex flex-col gap-2">
                    <span className="text-xs text-zinc-500 uppercase font-bold tracking-wider ml-1">Optimized Result</span>
                    <div className="flex-1 bg-zinc-900/50 rounded-2xl border border-emerald-500/20 p-4 relative group">
                        {output ? (
                            <textarea
                                readOnly
                                value={output}
                                className="w-full h-full bg-transparent resize-none outline-none text-emerald-100 font-mono text-sm selection:bg-emerald-500/30"
                            />
                        ) : (
                            <div className="h-full flex items-center justify-center text-zinc-700 text-sm italic">
                                Ready to optimize...
                            </div>
                        )}
                    </div>

                    {/* Stats Badge */}
                    {stats && (
                        <div className="flex justify-end gap-3 items-center animate-slide-up">
                            <div className="text-xs font-mono text-zinc-400">
                                {stats.after_tokens} tokens
                            </div>
                            <div className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-xs font-bold text-emerald-400">
                                Saved {stats.saved_percent}%
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
