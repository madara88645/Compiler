"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { apiJson } from "@/config";
import { showError } from "../lib/showError";

import InfoButton from "../components/InfoButton";

type OptimizeResponse = {
    text: string;
    before_chars: number;
    after_chars: number;
    before_tokens: number;
    after_tokens: number;
    saved_percent: number;
    changed: boolean;
    provider: string;
    model: string;
    source_language: string;
    tokenizer_method: string;
    estimated_input_cost_usd: number;
    estimated_output_cost_usd: number;
    estimated_savings_usd: number;
    english_variant: string;
    english_variant_tokens: number;
    english_variant_cost_usd: number;
    warnings: string[];
};

const DEFAULT_OPTIMIZER_PROVIDER = "groq";
const DEFAULT_OPTIMIZER_MODEL = "llama-3.1-8b-instant";
const DEFAULT_TOKENIZER_METHOD = "tiktoken:o200k_base:estimated";

function toFiniteNumber(value: unknown, fallback = 0): number {
    const parsed = typeof value === "number" ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function toStringValue(value: unknown, fallback = ""): string {
    return typeof value === "string" ? value : fallback;
}

function toWarnings(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }
    return value.filter((warning): warning is string => typeof warning === "string" && warning.trim().length > 0);
}

function normalizeOptimizeResponse(data: Partial<OptimizeResponse>): OptimizeResponse {
    const beforeTokens = toFiniteNumber(data.before_tokens);
    const afterTokens = toFiniteNumber(data.after_tokens);
    const calculatedSavedPercent = beforeTokens > 0
        ? Number((((beforeTokens - afterTokens) / beforeTokens) * 100).toFixed(1))
        : 0;

    return {
        text: toStringValue(data.text),
        before_chars: toFiniteNumber(data.before_chars),
        after_chars: toFiniteNumber(data.after_chars),
        before_tokens: beforeTokens,
        after_tokens: afterTokens,
        saved_percent: toFiniteNumber(data.saved_percent, calculatedSavedPercent),
        changed: Boolean(data.changed),
        provider: toStringValue(data.provider, DEFAULT_OPTIMIZER_PROVIDER),
        model: toStringValue(data.model, DEFAULT_OPTIMIZER_MODEL),
        source_language: toStringValue(data.source_language, "unknown"),
        tokenizer_method: toStringValue(data.tokenizer_method, DEFAULT_TOKENIZER_METHOD),
        estimated_input_cost_usd: toFiniteNumber(data.estimated_input_cost_usd),
        estimated_output_cost_usd: toFiniteNumber(data.estimated_output_cost_usd),
        estimated_savings_usd: toFiniteNumber(data.estimated_savings_usd),
        english_variant: toStringValue(data.english_variant),
        english_variant_tokens: toFiniteNumber(data.english_variant_tokens),
        english_variant_cost_usd: toFiniteNumber(data.english_variant_cost_usd),
        warnings: toWarnings(data.warnings),
    };
}

function formatUsd(value: number): string {
    if (!Number.isFinite(value) || value === 0) {
        return "$0";
    }
    if (Math.abs(value) < 0.01) {
        return `$${value.toExponential(2)}`;
    }
    return `$${value.toFixed(4)}`;
}

const LANGUAGE_LABELS: Record<string, string> = { tr: "TR", en: "EN" };

function formatLanguage(language: string): string {
    const key = (language ?? "").toLowerCase();
    return LANGUAGE_LABELS[key] ?? "UNKNOWN";
}

function charsPerToken(chars: number, tokens: number): string {
    if (!tokens) {
        return "0.00";
    }
    return (chars / tokens).toFixed(2);
}

function MetricTile({
    label,
    value,
    detail,
}: {
    label: string;
    value: string;
    detail: string;
}) {
    return (
        <div className="rounded-lg border border-white/10 bg-zinc-950/40 p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-zinc-500">{label}</div>
            <div className="mt-3 text-2xl font-semibold text-white">{value}</div>
            <div className="mt-1 text-xs text-zinc-500">{detail}</div>
        </div>
    );
}

export default function OptimizerPage() {
    const [input, setInput] = useState("");
    const [result, setResult] = useState<OptimizeResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [maxTokens, setMaxTokens] = useState<number>(1000);

    const output = result?.text ?? "";
    const englishVariant = result?.english_variant ?? "";
    const sourceLanguage = (result?.source_language ?? "").toLowerCase();
    const showEnglishPanel =
        !!result &&
        sourceLanguage !== "en" &&
        englishVariant.trim().length > 0 &&
        englishVariant.trim() !== output.trim();

    const handleOptimize = async () => {
        if (!input.trim()) return;
        setLoading(true);
        try {
            const data = await apiJson<Partial<OptimizeResponse>>("/optimize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: input,
                    max_tokens: maxTokens,
                    provider: DEFAULT_OPTIMIZER_PROVIDER,
                    model: DEFAULT_OPTIMIZER_MODEL,
                }),
            });
            setResult(normalizeOptimizeResponse(data));
        } catch (e) {
            showError(e);
        } finally {
            setLoading(false);
        }
    };

    const copyText = (text: string) => {
        if (!text) return;
        void navigator.clipboard?.writeText(text).catch(() => {});
    };

    return (
        <main className="flex h-screen flex-col items-center justify-center p-4 md:p-8 relative overflow-hidden">
            {/* Ambient Background Orbs */}
            <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-emerald-600/10 blur-[120px] pointer-events-none" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-teal-600/10 blur-[120px] pointer-events-none" />

            {/* Floating Main Container */}
            <div className="glass w-full max-w-7xl h-full max-h-[90vh] rounded-3xl flex flex-col shadow-2xl overflow-hidden animate-fade-in ring-1 ring-white/10">
            <header className="border-b border-white/5 bg-black/20 p-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between backdrop-blur-md">
                <div className="flex items-center gap-3">
                    <div className="h-9 w-9 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-emerald-500/20">
                        <Sparkles size={18} aria-hidden="true" />
                    </div>
                    <div>
                        <h1 className="font-semibold text-lg tracking-tight text-white">Token Optimizer</h1>
                        <div className="text-xs text-zinc-400 font-mono tracking-wider uppercase opacity-70">
                            Compress safely • Compare cost
                        </div>
                    </div>
                    <InfoButton
                        title="Prompt Optimizer"
                        description="Shortens prompts while keeping intent, constraints, variables, and safety details visible. Estimates Groq cost and compares language efficiency."
                    />
                </div>

                <div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-zinc-950/40 p-3 sm:flex-row sm:items-center">
                    <div className="flex min-w-40 flex-col gap-1">
                        <label htmlFor="max-tokens" className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                            Max Tokens
                        </label>
                        <input
                            id="max-tokens"
                            type="range"
                            min="100"
                            max="4096"
                            step="100"
                            value={maxTokens}
                            onChange={(e) => setMaxTokens(Number.parseInt(e.target.value, 10))}
                            className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-zinc-700 accent-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        />
                        <span className="text-right font-mono text-xs text-emerald-300">{maxTokens}</span>
                    </div>

                    <button
                        type="button"
                        onClick={handleOptimize}
                        disabled={loading || !input.trim()}
                        title={!input.trim() ? "Enter a prompt first to analyze cost" : "Analyze cost"}
                        className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-bold text-white shadow-lg shadow-emerald-950/30 transition-colors hover:bg-emerald-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                    >
                        {loading ? "Analyzing..." : (
                            <>
                                Analyze cost
                                <kbd className="ml-2 hidden rounded border border-white/20 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] opacity-60 md:inline-block">
                                    Ctrl/⌘ Enter
                                </kbd>
                            </>
                        )}
                    </button>
                </div>
            </header>

            <div className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6 flex flex-col gap-5">
            <div className="grid min-h-[50vh] grid-cols-1 gap-5 lg:grid-cols-2">
                <section className="flex min-h-80 flex-col gap-2">
                    <label htmlFor="original-prompt" className="ml-1 text-xs font-bold uppercase tracking-wider text-zinc-500">
                        Original Prompt
                    </label>
                    <div className="min-h-0 flex-1 rounded-lg border border-white/10 bg-zinc-950/30 p-4 transition-colors focus-within:border-emerald-500/40">
                        <textarea
                            id="original-prompt"
                            aria-label="Original Prompt"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                                    e.preventDefault();
                                    if (!loading && input.trim()) {
                                        void handleOptimize();
                                    }
                                }
                            }}
                            placeholder="Paste a verbose prompt here..."
                            className="h-full min-h-72 w-full resize-none bg-transparent font-mono text-sm leading-relaxed text-zinc-200 outline-none placeholder:text-zinc-500"
                        />
                    </div>
                </section>

                <section className="flex min-h-80 flex-col gap-2">
                    <div className="flex items-center justify-between gap-3">
                        <label htmlFor="optimized-result" className="ml-1 text-xs font-bold uppercase tracking-wider text-zinc-500">
                            Optimized Result
                        </label>
                        {!!output && (
                            <button
                                type="button"
                                onClick={() => copyText(output)}
                                className="rounded-lg border border-emerald-500/30 px-3 py-1 text-xs font-semibold text-emerald-200 transition-colors hover:bg-emerald-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                                aria-label="Copy optimized result"
                            >
                                Copy
                            </button>
                        )}
                    </div>
                    <div className="min-h-0 flex-1 rounded-lg border border-emerald-500/20 bg-emerald-950/10 p-4">
                        {output ? (
                            <textarea
                                id="optimized-result"
                                aria-label="Optimized Result"
                                readOnly
                                value={output}
                                className="h-full min-h-72 w-full resize-none bg-transparent font-mono text-sm leading-relaxed text-emerald-50 outline-none selection:bg-emerald-500/30"
                            />
                        ) : (
                            <div className="flex h-full min-h-72 items-center justify-center text-sm italic text-zinc-400">
                                Optimized prompt will appear here.
                            </div>
                        )}
                    </div>
                </section>
            </div>

            {result && (
                <section className="flex flex-col gap-4">
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <MetricTile
                            label="Original estimate"
                            value={`${result.before_tokens}`}
                            detail={`${formatUsd(result.estimated_input_cost_usd)} input cost`}
                        />
                        <MetricTile
                            label="Optimized estimate"
                            value={`${result.after_tokens}`}
                            detail={`${formatUsd(result.estimated_output_cost_usd)} optimized cost`}
                        />
                        <MetricTile
                            label="Saved"
                            value={`${result.saved_percent}%`}
                            detail={`${formatUsd(result.estimated_savings_usd)} estimated delta`}
                        />
                        <MetricTile
                            label="Efficiency"
                            value={formatLanguage(result.source_language)}
                            detail={`${charsPerToken(result.before_chars, result.before_tokens)} chars/token`}
                        />
                    </div>

                    {result.warnings.length > 0 && (
                        <section
                            aria-label="Optimizer warnings"
                            className="space-y-2"
                        >
                            {result.warnings.map((warning) => (
                                <p
                                    key={warning}
                                    className="rounded-lg border border-amber-400/20 bg-amber-500/10 p-3 text-xs text-amber-100"
                                >
                                    {warning}
                                </p>
                            ))}
                        </section>
                    )}

                    {showEnglishPanel && (
                        <div className="rounded-lg border border-white/10 bg-zinc-950/40 p-4">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <h2 className="text-sm font-semibold text-white">English compact suggestion</h2>
                                    <p className="mt-1 text-xs text-zinc-500">
                                        Groq / {result.model}
                                    </p>
                                </div>
                                <span className="rounded-lg border border-white/10 px-2 py-1 font-mono text-xs text-zinc-400">
                                    {result.english_variant_tokens} tokens
                                </span>
                            </div>

                            <div className="mt-3 flex flex-col gap-3">
                                <textarea
                                    readOnly
                                    value={englishVariant}
                                    aria-label="English compact suggestion"
                                    className="min-h-24 w-full resize-none rounded-lg border border-white/10 bg-black/20 p-3 font-mono text-sm text-cyan-50 outline-none"
                                />
                                <div className="flex items-center justify-between gap-3">
                                    <span className="text-xs text-zinc-500">
                                        Estimated cost: {formatUsd(result.english_variant_cost_usd)}
                                    </span>
                                    <button
                                        type="button"
                                        onClick={() => copyText(englishVariant)}
                                        className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-cyan-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                                        aria-label="Copy English variant"
                                    >
                                        Copy English variant
                                    </button>
                                </div>
                            </div>

                            <p className="mt-3 text-xs text-zinc-600">
                                {result.tokenizer_method}
                            </p>
                        </div>
                    )}
                </section>
            )}
            </div>
            </div>
        </main>
    );
}
