"use client";

import { useMemo } from "react";
import { ShieldAlert } from "lucide-react";
import type { SecurityFinding } from "../../lib/api/types";

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
        const friendlyLabel: Record<string, { singular: string; plural: string }> = {
            email: { singular: "email address", plural: "email addresses" },
            phone: { singular: "phone number", plural: "phone numbers" },
            secret: { singular: "secret / API key", plural: "secrets / API keys" },
            apikey: { singular: "API key", plural: "API keys" },
            token: { singular: "auth token", plural: "auth tokens" },
            creditcard: { singular: "credit-card number", plural: "credit-card numbers" },
            ssn: { singular: "social security number", plural: "social security numbers" },
            ip: { singular: "IP address", plural: "IP addresses" },
        };
        const counts: Record<string, number> = {};
        findings.forEach(f => {
            counts[f.type] = (counts[f.type] || 0) + 1;
        });
        return Object.entries(counts).map(([type, count]) => {
            const key = type.toLowerCase().replace(/[\s_-]/g, "");
            const label = friendlyLabel[key];
            if (label) {
                return `${count} ${count === 1 ? label.singular : label.plural}`;
            }
            return `${count} ${type.toLowerCase()}${count === 1 ? "" : "s"}`;
        });
    }, [findings]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-fade-in">
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="security-alert-title"
                className="bg-[#1a1a1a] w-full max-w-2xl rounded-2xl border border-red-500/30 shadow-2xl shadow-red-500/20 overflow-hidden flex flex-col"
            >

                {/* Header */}
                <div className="bg-red-500/10 border-b border-red-500/20 p-6 flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center shadow-lg shadow-red-500/20">
                            <ShieldAlert size={22} className="text-red-300" aria-hidden="true" />
                        </div>
                        <div>
                            <h2 id="security-alert-title" className="text-xl font-bold text-red-100 tracking-wide">Possible secrets in your prompt</h2>
                            <p className="text-sm text-red-300/80">We scanned locally and spotted patterns that look like personal data or credentials. Nothing has been sent to any model yet — it's your call.</p>
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
                        <p className="text-xs text-zinc-400 leading-relaxed">
                            <strong className="text-zinc-300">Strip Secrets &amp; Proceed</strong> will send the version below — your local prompt is unchanged.
                        </p>
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
                        type="button"
                        onClick={onCancel}
                        className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 rounded"
                    >
                        Cancel
                    </button>

                    <button
                        type="button"
                        onClick={onProceedOriginal}
                        className="px-4 py-2 text-sm font-medium text-red-400 border border-red-500/30 hover:bg-red-500/10 rounded-lg transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                    >
                        Send original anyway
                    </button>

                    <button
                        type="button"
                        onClick={onProceedRedacted}
                        autoFocus
                        className="px-6 py-2 text-sm font-bold bg-green-600 hover:bg-green-500 text-white rounded-lg shadow-lg shadow-green-500/20 transition-all active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                    >
                        Strip Secrets & Proceed
                    </button>
                </div>
            </div>
        </div>
    );
}
