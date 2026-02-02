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
        <div className="flex flex-col h-full bg-zinc-950 p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
                    <span>🛡️ Quality Coach</span>
                    {report && (
                        <span className={`text-sm px-2 py-0.5 rounded ${report.score >= 90 ? 'bg-green-900/50 text-green-400' :
                                report.score >= 70 ? 'bg-yellow-900/50 text-yellow-400' :
                                    'bg-red-900/50 text-red-400'
                            }`}>
                            Score: {report.score}/100
                        </span>
                    )}
                </h2>
                <div className="flex gap-2">
                    <button
                        onClick={handleAnalyze}
                        disabled={analyzing}
                        className="px-4 py-2 bg-blue-900/30 text-blue-400 border border-blue-800 rounded hover:bg-blue-900/50 text-sm font-medium disabled:opacity-50"
                    >
                        {analyzing ? "Analyzing..." : "Run Analysis"}
                    </button>
                    <button
                        onClick={handleAutoFix}
                        disabled={fixing || !prompt.trim()}
                        className="px-4 py-2 bg-purple-900/30 text-purple-400 border border-purple-800 rounded hover:bg-purple-900/50 text-sm font-medium disabled:opacity-50"
                    >
                        {fixing ? "Auto-Fixing..." : "✨ Auto-Fix"}
                    </button>
                </div>
            </div>

            {!report && !fixResult && (
                <div className="flex-1 flex items-center justify-center text-zinc-600">
                    <p>Run analysis to detect issues or Auto-Fix to improve instantly.</p>
                </div>
            )}

            {/* Fix Result Preview */}
            {fixResult && (
                <div className="mb-8 p-4 bg-purple-900/10 border border-purple-900/30 rounded-lg">
                    <h3 className="text-purple-400 font-bold mb-2 flex justify-between">
                        <span>✨ Auto-Fix Proposed</span>
                    </h3>
                    <div className="space-y-4">
                        <div className="bg-zinc-900 p-3 rounded border border-zinc-800 font-mono text-sm text-zinc-300 max-h-40 overflow-y-auto w-full whitespace-pre-wrap">
                            {fixResult.fixed_text}
                        </div>
                        <div>
                            <h4 className="text-xs font-bold text-purpe-300 mb-1">Explanation:</h4>
                            <p className="text-xs text-zinc-400 mb-2">{fixResult.explanation}</p>

                            <h4 className="text-xs font-bold text-purpe-300 mb-1">Changes Applied:</h4>
                            <ul className="list-disc list-inside text-xs text-zinc-400">
                                {fixResult.changes.map((change, i) => (
                                    <li key={i}>{change}</li>
                                ))}
                            </ul>
                        </div>
                        <div className="flex gap-2">
                            <button
                                onClick={applyFix}
                                className="flex-1 py-2 bg-purple-600 text-white rounded font-medium text-sm hover:bg-purple-500"
                            >
                                Apply Changes
                            </button>
                            <button
                                onClick={() => setFixResult(null)}
                                className="px-4 py-2 bg-zinc-800 text-zinc-400 rounded hover:text-zinc-200"
                            >
                                Discard
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Analysis Report */}
            {report && (
                <div className="space-y-6">
                    {/* Category Scores */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {Object.entries(report.score).map(([cat, score]) => (
                            <div key={cat} className="bg-zinc-900 p-3 rounded border border-zinc-800">
                                <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{cat}</div>
                                <div className="text-lg font-bold text-zinc-200">
                                    {typeof score === 'number' ? score.toFixed(1) : score}
                                </div>
                                {typeof score === 'number' && (
                                    <div className="w-full bg-zinc-800 h-1 mt-2 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full ${score > 80 ? 'bg-green-500' : score > 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                            style={{ width: `${score}%` }}
                                        />
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Issues List (Weaknesses) */}
                    <div>
                        <h3 className="text-zinc-400 font-bold mb-3 uppercase text-xs tracking-wider">Analysis Feedback</h3>
                        <div className="space-y-3">
                            {report.weaknesses.length === 0 ? (
                                <div className="text-green-500 flex items-center gap-2">
                                    <span>✅</span> No issues detected!
                                </div>
                            ) : (
                                report.weaknesses.map((weakness, i) => (
                                    <div key={i} className="p-3 rounded border bg-red-900/10 border-red-900/30">
                                        <div className="flex items-start gap-3">
                                            <span className="text-lg">🔴</span>
                                            <div>
                                                <div className="text-sm font-medium text-zinc-200">
                                                    {weakness}
                                                </div>
                                                {report.suggestions[i] && (
                                                    <div className="text-xs text-zinc-500 mt-1">
                                                        💡 {report.suggestions[i]}
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
