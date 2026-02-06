"use client";

import { useState } from "react";

type ValidationResponse = {
    score: number;
    category_scores: Record<string, number>;
    strengths: string[];
    weaknesses: string[];
    suggestions: string[];
    summary: string;
};

type AutoFixResponse = {
    fixed_text: string;
    explanation: string;
    changes: string[];
};

type QualityCoachProps = {
    prompt: string;
    onUpdatePrompt: (newPrompt: string) => void;
};

export default function QualityCoach({ prompt, onUpdatePrompt }: QualityCoachProps) {
    const [analyzing, setAnalyzing] = useState(false);
    const [fixing, setFixing] = useState(false);
    const [report, setReport] = useState<ValidationResponse | null>(null);
    const [fixResult, setFixResult] = useState<AutoFixResponse | null>(null);

    const handleAnalyze = async () => {
        if (!prompt.trim()) return;
        setAnalyzing(true);
        setFixResult(null); // Clear previous fixes
        try {
            const res = await fetch("http://127.0.0.1:8080/validate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: prompt }),
            });
            const data = await res.json();
            setReport(data);
        } catch (e) {
            console.error(e);
        } finally {
            setAnalyzing(false);
        }
    };

    const handleAutoFix = async () => {
        if (!prompt.trim()) return;
        setFixing(true);
        try {
            const res = await fetch("http://127.0.0.1:8080/fix", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: prompt, target_score: 90 }),
            });
            const data = await res.json();
            setFixResult(data);
        } catch (e) {
            console.error(e);
        } finally {
            setFixing(false);
        }
    };

    const applyFix = () => {
        if (fixResult) {
            onUpdatePrompt(fixResult.fixed_text);
            setFixResult(null);
            handleAnalyze(); // Re-analyze the new prompt
        }
    };

    return (
        <div className="flex flex-col h-full bg-transparent p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-8 sticky top-0 bg-black/60 backdrop-blur-md p-4 -m-4 border-b border-white/5 z-10">
                <h2 className="text-xl font-bold text-white flex items-center gap-3">
                    <span className="text-2xl">🛡️</span>
                    <div>
                        <div>Quality Coach</div>
                        {report && (
                            <div className="text-[10px] font-mono text-zinc-400 font-normal">
                                Score: <span className={report.score >= 80 ? 'text-green-400' : 'text-yellow-400'}>{report.score}/100</span>
                            </div>
                        )}
                    </div>
                </h2>
                <div className="flex gap-2">
                    <button
                        onClick={handleAnalyze}
                        disabled={analyzing}
                        className="px-4 py-2 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-xl hover:bg-blue-500/20 text-xs font-semibold uppercase tracking-wider disabled:opacity-50 transition-all"
                    >
                        {analyzing ? <span className="animate-pulse">Analyzing...</span> : "Run Analysis"}
                    </button>
                    <button
                        onClick={handleAutoFix}
                        disabled={fixing || !prompt.trim()}
                        className="px-4 py-2 bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded-xl hover:bg-purple-500/20 text-xs font-semibold uppercase tracking-wider disabled:opacity-50 transition-all shadow-[0_0_15px_rgba(168,85,247,0.1)] hover:shadow-[0_0_20px_rgba(168,85,247,0.2)]"
                    >
                        {fixing ? <span className="animate-pulse">Fixing...</span> : "✨ Auto-Fix"}
                    </button>
                </div>
            </div>

            {!report && !fixResult && (
                <div className="flex-1 flex flex-col items-center justify-center text-zinc-500 gap-4 opacity-70">
                    <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center text-3xl mb-2">
                        🛡️
                    </div>
                    <p className="max-w-[200px] text-center text-sm">Run analysis to detect issues or Auto-Fix to improve instantly.</p>
                </div>
            )}

            {/* Fix Result Preview */}
            {fixResult && (
                <div className="mb-8 p-1 bg-gradient-to-br from-purple-500/20 to-blue-500/20 rounded-2xl animate-fade-in shadow-2xl shadow-purple-900/20">
                    <div className="bg-black/80 rounded-xl p-5 backdrop-blur-xl">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-purple-300 font-bold flex items-center gap-2">
                                <span className="text-xl">✨</span> Proposed Improvement
                            </h3>
                            <button onClick={() => setFixResult(null)} className="text-zinc-500 hover:text-white transition-colors">✕</button>
                        </div>

                        <div className="space-y-5">
                            <div className="space-y-2">
                                <div className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Revised Prompt</div>
                                <div className="bg-white/5 p-4 rounded-xl border border-white/5 font-mono text-sm text-zinc-200 max-h-40 overflow-y-auto w-full whitespace-pre-wrap leading-relaxed shadow-inner">
                                    {fixResult.fixed_text}
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <h4 className="text-[10px] font-bold text-purple-400/80 uppercase tracking-widest">Why this fix?</h4>
                                    <p className="text-xs text-zinc-400 leading-relaxed bg-purple-500/5 p-3 rounded-lg border border-purple-500/10 h-full">{fixResult.explanation}</p>
                                </div>
                                <div className="space-y-1">
                                    <h4 className="text-[10px] font-bold text-blue-400/80 uppercase tracking-widest">Key Changes</h4>
                                    <ul className="list-none space-y-1 text-xs text-zinc-400 bg-blue-500/5 p-3 rounded-lg border border-blue-500/10 h-full">
                                        {fixResult.changes.map((change, i) => (
                                            <li key={i} className="flex gap-2">
                                                <span className="text-blue-500">•</span>
                                                {change}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>

                            <button
                                onClick={applyFix}
                                className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-bold text-sm shadow-lg hover:shadow-purple-500/25 active:scale-[0.98] transition-all"
                            >
                                Apply Changes & Re-Analyze
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Analysis Report */}
            {report && (
                <div className="space-y-8 animate-fade-in pb-10">
                    {/* Category Scores */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        {Object.entries(report.score).map(([cat, score]) => (
                            <div key={cat} className="glass-panel p-4 rounded-xl relative overflow-hidden group hover:bg-white/5 transition-colors">
                                <div className="text-[10px] text-zinc-500 uppercase tracking-widest mb-2 font-semibold">{cat}</div>
                                <div className="flex items-end gap-2 mb-3">
                                    <div className="text-2xl font-bold text-white tracking-tight">
                                        {typeof score === 'number' ? score.toFixed(0) : score}
                                    </div>
                                    <div className="text-xs text-zinc-600 mb-1 font-mono">/100</div>
                                </div>

                                {typeof score === 'number' && (
                                    <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full rounded-full transition-all duration-1000 ease-out ${score > 80 ? 'bg-gradient-to-r from-green-500 to-emerald-400' : score > 50 ? 'bg-gradient-to-r from-yellow-500 to-amber-400' : 'bg-gradient-to-r from-red-500 to-rose-400'}`}
                                            style={{ width: `${score}%`, boxShadow: '0 0 10px rgba(255,255,255,0.2)' }}
                                        />
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Issues List (Weaknesses) */}
                    <div>
                        <h3 className="text-zinc-500 font-bold mb-4 uppercase text-xs tracking-widest flex items-center gap-2">
                            <span>Analysis Findings</span>
                            <div className="h-px flex-1 bg-white/10" />
                        </h3>
                        <div className="space-y-3">
                            {report.weaknesses.length === 0 ? (
                                <div className="p-6 rounded-2xl bg-green-500/5 border border-green-500/20 text-green-400 flex flex-col items-center gap-2 text-center">
                                    <span className="text-3xl">🎉</span>
                                    <span className="font-semibold">Excellent Prompt!</span>
                                    <span className="text-sm opacity-80">We couldn't find any significant issues. High five!</span>
                                </div>
                            ) : (
                                report.weaknesses.map((weakness, i) => (
                                    <div key={i} className="p-4 rounded-xl bg-red-500/5 border border-red-500/10 hover:bg-red-500/10 transition-colors group">
                                        <div className="flex items-start gap-3">
                                            <div className="mt-0.5 w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_5px_rgba(239,68,68,0.5)] flex-shrink-0" />
                                            <div className="flex-1">
                                                <div className="text-sm font-medium text-zinc-200 leading-relaxed">
                                                    {weakness}
                                                </div>
                                                {report.suggestions[i] && (
                                                    <div className="mt-3 flex items-start gap-2 text-zinc-400 bg-black/20 p-3 rounded-lg border border-white/5">
                                                        <span className="text-yellow-500 text-xs">💡</span>
                                                        <span className="text-xs leading-relaxed">{report.suggestions[i]}</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
