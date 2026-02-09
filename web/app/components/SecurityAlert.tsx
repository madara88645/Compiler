"use client";

import { useMemo } from "react";

type SecurityFinding = {
    type: string;
    original: string;
    masked: string;
};

type SecurityAlertProps = {
    findings: SecurityFinding[];
    redactedText: string;
    onProceedRedacted: () => void;
    onProceedOriginal: () => void;
    onCancel: () => void;
};

export default function SecurityAlert({
    findings,
    redactedText,
    onProceedRedacted,
    onProceedOriginal,
    onCancel,
}: SecurityAlertProps) {

    const findingsSummary = useMemo(() => {
        const counts: Record<string, number> = {};
        findings.forEach(f => {
            counts[f.type] = (counts[f.type] || 0) + 1;
        });
        return Object.entries(counts).map(([type, count]) => `${count} x ${type.toUpperCase()}`);
    }, [findings]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-fade-in">
            <div className="bg-[#1a1a1a] w-full max-w-2xl rounded-2xl border border-red-500/30 shadow-2xl shadow-red-500/20 overflow-hidden flex flex-col">

                {/* Header */}
                <div className="bg-red-500/10 border-b border-red-500/20 p-6 flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center text-xl shadow-lg shadow-red-500/20">
                            🛡️
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-red-100 tracking-wide">Security Alert</h2>
                            <p className="text-sm text-red-300/80">Sensitive information detected in your prompt.</p>
                        </div>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6 flex flex-col gap-4">

                    <div className="flex flex-wrap gap-2">
                        {findingsSummary.map((summary, i) => (
                            <span key={i} className="px-3 py-1 bg-red-500/20 text-red-200 text-xs font-mono rounded-full border border-red-500/30">
                                {summary}
                            </span>
                        ))}
                    </div>

                    <div className="bg-black/30 rounded-xl border border-white/5 p-4 flex flex-col gap-2">
                        <span className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">Preview Redacted Version</span>
                        <pre className="text-xs text-zinc-400 font-mono whitespace-pre-wrap leading-relaxed max-h-[200px] overflow-y-auto custom-scrollbar">
                            {redactedText}
                        </pre>
                    </div>

                    <div className="p-4 bg-yellow-500/5 border border-yellow-500/10 rounded-lg">
                        <p className="text-xs text-yellow-200/80 leading-relaxed">
                            <strong className="text-yellow-100">Warning:</strong> Sending original secrets to an External LLM provider may expose them.
                            We recommend stripping them before proceeding.
                        </p>
                    </div>

                </div>

                {/* Actions */}
                <div className="p-6 pt-0 flex gap-3 justify-end">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors"
                    >
                        Cancel
                    </button>

                    <button
                        onClick={onProceedOriginal}
                        className="px-4 py-2 text-sm font-medium text-red-400 border border-red-500/30 hover:bg-red-500/10 rounded-lg transition-all"
                    >
                        Proceed Unsafe (Original)
                    </button>

                    <button
                        onClick={onProceedRedacted}
                        className="px-6 py-2 text-sm font-bold bg-green-600 hover:bg-green-500 text-white rounded-lg shadow-lg shadow-green-500/20 transition-all active:scale-95"
                    >
                        Strip Secrets & Proceed
                    </button>
                </div>
            </div>
        </div>
    );
}
