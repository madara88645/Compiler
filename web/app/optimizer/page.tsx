"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { apiJson, describeRequestError } from "@/config";
import { showError } from "../lib/showError";
import { copyToClipboard } from "../lib/copyToClipboard";
import { BENCHMARK_MODELS } from "../benchmark/modelCatalog";

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
    estimated_optimized_input_cost_usd: number;
    english_variant: string;
    english_variant_tokens: number;
    english_variant_cost_usd: number;
    warnings: string[];
    pricing_known: boolean;
    pricing_source: string | null;
    pricing_verified_at: string | null;
    tokenizer_name: string | null;
    token_count_is_estimate: boolean;
    context_length: number | null;
    optimizer_model: string;
    actual_input_tokens: number | null;
    actual_output_tokens: number | null;
    actual_cost_usd: number | null;
    estimated_actual_cost_usd: number | null;
    optimizer_provider: string;
    optimizer_call_usage?: Record<string, unknown> | null;
    english_optimizer_call_usage?: Record<string, unknown> | null;
};

const DEFAULT_OPTIMIZER_PROVIDER = "openrouter";
const DEFAULT_OPTIMIZER_MODEL = "openai/gpt-oss-20b";
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

    const hasLegacyPricingFields =
        data.estimated_input_cost_usd !== undefined || data.estimated_output_cost_usd !== undefined;
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
        estimated_optimized_input_cost_usd: toFiniteNumber(
            data.estimated_optimized_input_cost_usd,
            toFiniteNumber(data.estimated_output_cost_usd),
        ),
        english_variant: toStringValue(data.english_variant),
        english_variant_tokens: toFiniteNumber(data.english_variant_tokens),
        english_variant_cost_usd: toFiniteNumber(data.english_variant_cost_usd),
        warnings: toWarnings(data.warnings),
        pricing_known: typeof data.pricing_known === "boolean" ? data.pricing_known : hasLegacyPricingFields,
        pricing_source: typeof data.pricing_source === "string" ? data.pricing_source : null,
        pricing_verified_at: typeof data.pricing_verified_at === "string" ? data.pricing_verified_at : null,
        tokenizer_name: typeof data.tokenizer_name === "string" ? data.tokenizer_name : null,
        token_count_is_estimate: data.token_count_is_estimate !== false,
        context_length: typeof data.context_length === "number" ? data.context_length : null,
        optimizer_model: toStringValue(data.optimizer_model, toStringValue(data.model, DEFAULT_OPTIMIZER_MODEL)),
        actual_input_tokens: typeof data.actual_input_tokens === "number" ? data.actual_input_tokens : null,
        actual_output_tokens: typeof data.actual_output_tokens === "number" ? data.actual_output_tokens : null,
        actual_cost_usd: typeof data.actual_cost_usd === "number" ? data.actual_cost_usd : null,
        estimated_actual_cost_usd: typeof data.estimated_actual_cost_usd === "number" ? data.estimated_actual_cost_usd : null,
        optimizer_provider: toStringValue(data.optimizer_provider, toStringValue(data.provider, DEFAULT_OPTIMIZER_PROVIDER)),
        optimizer_call_usage: data.optimizer_call_usage ?? null,
        english_optimizer_call_usage: data.english_optimizer_call_usage ?? null,
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

function formatEstimatedCost(value: number, pricingKnown: boolean): string {
    return pricingKnown ? formatUsd(value) : "Unavailable";
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

function formatProviderName(provider: string): string {
    const normalized = (provider ?? "").toLowerCase();
    if (normalized === "openrouter") {
        return "OpenRouter";
    }
    if (normalized === "local") {
        return "Local";
    }
    return provider || "Unknown";
}

function isCloudOptimizerUnavailable(message: string | null): boolean {
    if (!message) {
        return false;
    }

    const normalized = message.toLowerCase();
    return (
        normalized.includes("api key") ||
        normalized.includes("401") ||
        normalized.includes("403") ||
        normalized.includes("unauthorized") ||
        normalized.includes("forbidden") ||
        normalized.includes("provider") ||
        normalized.includes("temporarily unavailable")
    );
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

// Keep literal material and Markdown structure intact. Local mode only
// collapses redundant spaces in plain prose; it never truncates to a budget.
const runLocalOfflineCompression = (text: string): string => {
    let fence = "";
    let inComment = false;
    return (text.match(/[^\n]*\n|[^\n]+$/g) ?? []).map((line) => {
        const trimmed = line.trim();
        const marker = line.match(/^ {0,3}(`{3,}|~{3,})/);
        if (fence) {
            if (trimmed.length >= fence.length && [...trimmed].every((char) => char === fence[0])) fence = "";
            return line;
        }
        if (marker) { fence = marker[1]; return line; }
        if (inComment || line.includes("<!--")) {
            inComment = !line.includes("-->");
            return line;
        }
        if (/^\s/.test(line) || /[`"'{}<>/\\]/.test(line)) return line;
        return line.replace(/(\S)[ \t]{2,}(?=\S)/g, "$1 ");
    }).join("");
};

const estimateLocalTokens = (text: string): number => text.length
    ? Math.max(1, Math.ceil(new TextEncoder().encode(text).length / 4), text.trim().split(/\s+/).length)
    : 0;

export default function OptimizerPage() {
    const router = useRouter();
    const [input, setInput] = useState(() => {
        if (typeof window === "undefined") return "";
        return window.localStorage.getItem("promptc_optimizer_prompt") || "";
    });
    const [result, setResult] = useState<OptimizeResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [maxTokens, setMaxTokens] = useState<number>(1000);
    const [provider, setProvider] = useState(DEFAULT_OPTIMIZER_PROVIDER);
    const [model, setModel] = useState(DEFAULT_OPTIMIZER_MODEL);
    const [optimizationError, setOptimizationError] = useState<string | null>(null);

    const output = result?.text ?? "";
    const englishVariant = result?.english_variant ?? "";
    const sourceLanguage = (result?.source_language ?? "").toLowerCase();
    const showEnglishPanel =
        !!result &&
        sourceLanguage !== "en" &&
        englishVariant.trim().length > 0 &&
        englishVariant.trim() !== output.trim();

    const handleOptimize = async (overrideProvider?: string, overrideModel?: string) => {
        if (!input.trim()) return;
        const activeProvider = overrideProvider ?? provider;
        const activeModel = overrideModel ?? model;
        setLoading(true);
        setOptimizationError(null);
        setResult(null);

        if (activeProvider === "local") {
            const compressed = runLocalOfflineCompression(input);
            const beforeLen = input.length;
            const afterLen = compressed.length;

            // Same transparent byte/word fallback used by backend local estimates.
            const beforeTokens = estimateLocalTokens(input);
            const afterTokens = estimateLocalTokens(compressed);
            const savedPercent = beforeTokens > 0
                ? Number((((beforeTokens - afterTokens) / beforeTokens) * 100).toFixed(1))
                : 0;

            setResult({
                text: compressed,
                before_chars: beforeLen,
                after_chars: afterLen,
                before_tokens: beforeTokens,
                after_tokens: afterTokens,
                saved_percent: savedPercent,
                changed: compressed !== input,
                provider: "local",
                model: "offline",
                source_language: "unknown",
                tokenizer_method: "heuristic:utf8_bytes_words:estimated",
                estimated_input_cost_usd: 0,
                estimated_output_cost_usd: 0,
                estimated_savings_usd: 0,
                estimated_optimized_input_cost_usd: 0,
                english_variant: "",
                english_variant_tokens: 0,
                english_variant_cost_usd: 0,
                warnings: [
                    "Offline Local Heuristic compression active.",
                    "No cloud API key required for this mode.",
                    "Character and token metrics are approximations.",
                    ...(afterTokens > maxTokens ? [`Estimated output (${afterTokens} tokens) exceeds your ${maxTokens}-token target. Local mode keeps your content instead of truncating it.`] : [])
                ],
                pricing_known: true,
                pricing_source: "local:no-metered-provider",
                pricing_verified_at: null,
                tokenizer_name: "local heuristic",
                token_count_is_estimate: true,
                context_length: null,
                optimizer_model: "offline",
                actual_input_tokens: null,
                actual_output_tokens: null,
                actual_cost_usd: null,
                estimated_actual_cost_usd: null,
                optimizer_provider: "local",
            });
            setLoading(false);
            return;
        }

        try {
            const data = await apiJson<Partial<OptimizeResponse>>("/optimize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: input,
                    max_tokens: maxTokens,
                    provider: activeProvider,
                    model: activeModel,
                }),
            });
            setResult(normalizeOptimizeResponse(data));
        } catch (error: unknown) {
            showError(error);
            setOptimizationError(
                describeRequestError(error, { fallback: "Failed to optimize prompt." }),
            );
        } finally {
            setLoading(false);
        }
    };

    const handleSendToCompiler = (text: string = output) => {
        if (!text) return;
        window.localStorage.setItem("promptc_compiler_prompt", text);
        router.push("/");
    };

    const copyText = (text: string) => {
        if (!text) return;
        void copyToClipboard(text);
    };

    return (
        <main className="relative flex min-h-screen flex-col items-center justify-start overflow-x-hidden p-3 py-4 sm:p-4 md:h-screen md:justify-center md:overflow-hidden md:p-8">
            {/* Ambient Background Orbs */}
            <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-emerald-600/10 blur-[120px] pointer-events-none" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-teal-600/10 blur-[120px] pointer-events-none" />

            {/* Floating Main Container */}
            <div className="glass flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col overflow-hidden rounded-2xl shadow-2xl ring-1 ring-white/10 animate-fade-in md:h-full md:max-h-[90vh] md:rounded-3xl">
            <header className="flex flex-col gap-3 border-b border-white/5 bg-black/20 p-4 backdrop-blur-md lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-center gap-3">
                    <div className="h-9 w-9 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-emerald-500/20">
                        <Sparkles size={18} aria-hidden="true" />
                    </div>
                    <div>
                        <h1 className="font-semibold text-lg tracking-tight text-white">Token Optimizer</h1>
                        <div className="text-xs text-zinc-400 font-mono tracking-wider uppercase opacity-70">
                            Compress safely / Compare cost
                        </div>
                    </div>
                    <InfoButton
                        title="Token Optimizer"
                        description="Shortens prompts while keeping intent, constraints, variables, and safety details visible. Estimates OpenRouter cost and compares language efficiency."
                    />
                </div>

                <div className="flex w-full flex-col gap-3 rounded-lg border border-white/10 bg-zinc-950/50 p-3 sm:flex-row sm:items-center lg:w-auto">
                    <div className="flex min-w-[160px] flex-col gap-1">
                        <label htmlFor="optimizer-engine" className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                            Estimate model
                        </label>
                        <select
                            id="optimizer-engine"
                            value={`${provider}:${model}`}
                            onChange={(e) => {
                                const [p, m] = e.target.value.split(":");
                                setProvider(p);
                                setModel(m);
                                setOptimizationError(null);
                            }}
                            className="rounded-lg border border-white/10 bg-zinc-900 px-3 py-1.5 text-xs text-white outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50"
                        >
                            {BENCHMARK_MODELS.map((candidate) => (
                                <option key={candidate.id} value={`openrouter:${candidate.id}`}>
                                    {`OpenRouter ${candidate.label} (${candidate.availability === "preview" ? "Preview" : "Cloud"})`}
                                </option>
                            ))}
                            <option value="local:offline">Local Heuristics (Offline)</option>
                        </select>
                    </div>
                    <p className="max-w-[14rem] text-[10px] leading-relaxed text-zinc-500">
                        Cloud prices and tokenizer labels are reviewed from OpenRouter on 2026-09-12. They are estimates;
                        the server&apos;s configured cloud model performs the call and reports actual usage when available.
                    </p>

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
                            className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-zinc-600 accent-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        />
                        <span className="text-right font-mono text-xs text-emerald-300">{maxTokens}</span>
                    </div>

                    <button
                        type="button"
                        onClick={() => void handleOptimize()}
                        disabled={loading || !input.trim()}
                        aria-busy={loading}
                        title={!input.trim() ? "Enter a prompt first to optimize & estimate cost" : "Optimize & estimate cost"}
                        className="w-full rounded-lg bg-emerald-600 px-5 py-2 text-sm font-bold text-white shadow-lg shadow-emerald-950/30 transition-colors hover:bg-emerald-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 sm:w-auto"
                    >
                        {loading ? "Analyzing..." : (
                            <>
                                Optimize & estimate cost
                                <kbd className="ml-2 hidden rounded border border-white/20 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] opacity-60 md:inline-block">
                                    Ctrl/Cmd Enter
                                </kbd>
                            </>
                        )}
                    </button>
                </div>
            </header>

            <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-4 md:min-h-0 md:p-6">
            {optimizationError && (
                <div className="rounded-xl border border-red-500/25 bg-red-950/25 p-4 backdrop-blur-md animate-fade-in">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex flex-col gap-1">
                            <h3 className="text-sm font-semibold text-red-200">Cloud Optimizer Alert</h3>
                            <p className="text-xs text-red-300 opacity-90 leading-relaxed">
                                {isCloudOptimizerUnavailable(optimizationError)
                                    ? "The cloud optimizer could not run right now. If you are self-hosting, check the server's provider setup. Otherwise switch to Local Heuristics and keep going offline."
                                    : optimizationError}
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={() => {
                                setProvider("local");
                                setModel("offline");
                                setOptimizationError(null);
                                void handleOptimize("local", "offline");
                            }}
                            className="w-full sm:w-auto shrink-0 rounded-lg bg-emerald-600/20 border border-emerald-500/40 px-4 py-2 text-xs font-bold text-emerald-200 transition-all hover:bg-emerald-600/30 active:scale-95"
                        >
                            Switch to Local Heuristics (Offline)
                        </button>
                    </div>
                </div>
            )}
            <div className="grid min-h-[50vh] grid-cols-1 gap-5 md:grid-cols-2">
                <section className="flex min-h-80 flex-col gap-2">
                    <label htmlFor="original-prompt" className="ml-1 text-xs font-bold uppercase tracking-wider text-zinc-500" id="original-prompt-label">
                        Original Prompt
                    </label>
                    <div className="min-h-0 flex-1 rounded-lg border border-white/10 bg-zinc-950/50 p-4 transition-colors focus-within:border-emerald-500/40 relative">
                        <textarea
                            id="original-prompt"
                            aria-labelledby="original-prompt-label"
                            aria-describedby="original-prompt-description"
                            value={input}
                            onChange={(e) => {
                                setInput(e.target.value);
                                window.localStorage.setItem("promptc_optimizer_prompt", e.target.value);
                            }}
                            onKeyDown={(e) => {
                                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                                    e.preventDefault();
                                    if (!loading && input.trim()) {
                                        void handleOptimize();
                                    }
                                }
                            }}
                            placeholder="Paste a verbose prompt here..."
                            className="h-full min-h-72 w-full resize-none bg-transparent pr-14 font-mono text-sm leading-relaxed text-zinc-200 outline-none placeholder:text-zinc-500"
                        />
                        {input && (
                            <button
                                type="button"
                                onClick={() => {
                                    setInput("");
                                    window.localStorage.removeItem("promptc_optimizer_prompt");
                                }}
                                className="absolute top-2 right-2 text-xs text-zinc-500 hover:text-zinc-300 bg-black/40 hover:bg-black/60 px-2 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/50"
                                title="Clear prompt"
                                aria-label="Clear prompt"
                            >
                                Clear
                            </button>
                        )}
                    </div>
                </section>

                <section className="flex min-h-80 flex-col gap-2">
                    <div className="flex items-center justify-between gap-3">
                        <label htmlFor="optimized-result" className="ml-1 text-xs font-bold uppercase tracking-wider text-zinc-500" id="optimized-result-label">
                            Optimized Result
                        </label>
                        {!!output && (
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => handleSendToCompiler()}
                                    className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-bold text-white shadow-md shadow-emerald-950/30 transition-all hover:bg-emerald-500 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                                    aria-label="Send optimized result to compiler"
                                >
                                    Send to Compiler
                                </button>
                                <button
                                    type="button"
                                    onClick={() => copyText(output)}
                                    className="rounded-lg border border-emerald-500/30 px-3 py-1 text-xs font-semibold text-emerald-200 transition-colors hover:bg-emerald-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                                    aria-label="Copy optimized result"
                                >
                                    Copy
                                </button>
                            </div>
                        )}
                    </div>
                    <div className="min-h-0 flex-1 rounded-lg border border-emerald-500/25 bg-emerald-950/20 p-4">
                        {output ? (
                            <textarea
                                id="optimized-result"
                                aria-labelledby="optimized-result-label"
                                readOnly
                                value={output}
                                className="h-full min-h-72 w-full resize-none bg-transparent font-mono text-sm leading-relaxed text-emerald-50 outline-none selection:bg-emerald-500/30"
                            />
                        ) : (
                            <div className="flex h-full min-h-72 flex-col items-center justify-center text-center">
                                <div className="text-sm italic text-zinc-400 mb-4">
                                    Paste a prompt on the left, then run the analyzer to see a shorter version here.
                                </div>
                                <div className="flex flex-col items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => void handleOptimize()}
                                    disabled={loading || !input.trim()}
                                    aria-busy={loading}
                                    title={!input.trim() ? "Enter a prompt first to optimize & estimate cost" : "Optimize & estimate cost"}
                                    className="rounded-lg bg-emerald-600/20 border border-emerald-500/30 px-5 py-2 text-sm font-medium text-emerald-300 transition-colors hover:bg-emerald-600/30 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                                >
                                    {loading ? "Analyzing..." : "Optimize & estimate cost"}
                                </button>
                                {!input.trim() && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setInput("You are a helpful assistant. Provide a detailed, step-by-step summary of the provided text, ensuring that no important information is left out, and format the output as a bulleted list with clear headings for each section.");
                                        }}
                                        className="text-xs text-emerald-400/80 hover:text-emerald-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 rounded px-2 py-1"
                                    >
                                        or try an example
                                    </button>
                                )}
                                </div>
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
                            detail={`${formatEstimatedCost(result.estimated_input_cost_usd, result.pricing_known)} input cost`}
                        />
                        <MetricTile
                            label="Optimized estimate"
                            value={`${result.after_tokens}`}
                            detail={`${formatEstimatedCost(result.estimated_optimized_input_cost_usd, result.pricing_known)} optimized cost`}
                        />
                        <MetricTile
                            label="Saved"
                            value={`${result.saved_percent}%`}
                            detail={`${formatEstimatedCost(result.estimated_savings_usd, result.pricing_known)} estimated delta`}
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

                    <p className="text-xs text-zinc-600">
                        {result.pricing_known
                            ? `Estimate for ${result.provider} / ${result.model}${result.pricing_verified_at ? ` (verified ${result.pricing_verified_at})` : ""}. `
                            : "Pricing is unavailable for this model; dollar amounts are intentionally hidden. "}
                        {result.tokenizer_name ? `${result.tokenizer_name} tokenizer; ` : ""}
                        {result.token_count_is_estimate ? "token counts are estimates." : "token counts come from provider usage."}
                        {` Actual call: ${formatProviderName(result.optimizer_provider)} / ${result.optimizer_model}.`}
                        {result.actual_input_tokens !== null && result.actual_output_tokens !== null
                            ? ` Main optimizer usage: ${result.actual_input_tokens} input + ${result.actual_output_tokens} output tokens${result.actual_cost_usd !== null ? ` (${formatUsd(result.actual_cost_usd)} reported)` : result.estimated_actual_cost_usd !== null ? ` (${formatUsd(result.estimated_actual_cost_usd)} estimated)` : ""}.`
                            : ""}
                        {result.english_optimizer_call_usage ? " An additional English-variant call was made; its usage is excluded from the main-call figures above." : ""}
                    </p>

                    {showEnglishPanel && (
                        <div className="rounded-lg border border-white/10 bg-zinc-950/40 p-4">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <h2 className="text-sm font-semibold text-white">English compact suggestion</h2>
                                    <p className="mt-1 text-xs text-zinc-500">
                                        {formatProviderName(result.provider)} / {result.model}
                                    </p>
                                </div>
                                <span className="rounded-lg border border-white/10 px-2 py-1 font-mono text-xs text-zinc-400">
                                    {result.english_variant_tokens} tokens
                                </span>
                            </div>

                            <div className="mt-3 flex flex-col gap-3">
                                <label htmlFor="english-variant-output" className="sr-only" id="english-variant-output-label">English compact suggestion</label>
                                <textarea
                                    id="english-variant-output"
                                    readOnly
                                    value={englishVariant}
                                    aria-labelledby="english-variant-output-label"
                                    className="min-h-24 w-full resize-none rounded-lg border border-white/10 bg-black/20 p-3 font-mono text-sm text-cyan-50 outline-none"
                                />
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <span className="text-xs text-zinc-500">
                                        Estimated cost: {formatEstimatedCost(result.english_variant_cost_usd, result.pricing_known)}
                                    </span>
                                    <div className="flex items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => handleSendToCompiler(englishVariant)}
                                            className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-emerald-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                                            aria-label="Send English variant to compiler"
                                        >
                                            Send to Compiler
                                        </button>
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
