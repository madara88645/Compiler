"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

import { apiJson } from "@/config";
import DiffViewer from "../components/DiffViewer";
import InfoButton from "../components/InfoButton";
import { showError } from "../lib/showError";
import { BENCHMARK_MODEL_GROUPS, getBenchmarkModelById } from "./modelCatalog";

type BenchmarkPayload = {
  raw_output: string;
  compiled_output: string;
  metrics: {
    safety: { raw: number; compiled: number };
    clarity: { raw: number; compiled: number };
    conciseness: { raw: number; compiled: number };
  };
  processing_ms: number;
  winner: "compiled" | "raw";
  improvement_score: number;
};

function buildBenchmarkErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return "Benchmark failed. Try another model or re-run with the mock engine.";
}

function isBackendConfigIssue(message: string | null): boolean {
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

export default function BenchmarkPage() {
  const [prompt, setPrompt] = useState(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem("promptc_last_prompt") || "";
  });
  const [loading, setLoading] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkPayload | null>(null);
  const [resultIsMock, setResultIsMock] = useState(false);
  const [selectedModel, setSelectedModel] = useState("mock");
  const [status, setStatus] = useState("Ready");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedModelMeta = useMemo(
    () => (selectedModel === "mock" ? null : getBenchmarkModelById(selectedModel)),
    [selectedModel],
  );

  const generateMockResult = useCallback((): BenchmarkPayload => {
    const promptPreview = prompt.slice(0, 40) || "your prompt";
    const raw =
      `Here is a response to "${promptPreview}..."\n\n` +
      "This baseline answer is helpful but generic and lightly structured.";
    const compiled =
      `Here is an optimized response to "${promptPreview}..."\n\n` +
      "1. Direct answer\n2. Constraints\n3. Examples\n\n" +
      "The compiled version keeps tighter structure, clearer phrasing, and safer guardrails.";

    return {
      raw_output: raw,
      compiled_output: compiled,
      metrics: {
        safety: { raw: +(6 + Math.random() * 2).toFixed(1), compiled: +(9 + Math.random()).toFixed(1) },
        clarity: { raw: +(5 + Math.random() * 2).toFixed(1), compiled: +(8 + Math.random() * 2).toFixed(1) },
        conciseness: {
          raw: +(4 + Math.random() * 3).toFixed(1),
          compiled: +(7 + Math.random() * 2).toFixed(1),
        },
      },
      processing_ms: 850 + Math.floor(Math.random() * 400),
      winner: "compiled",
      improvement_score: 35,
    };
  }, [prompt]);

  const handleBenchmark = useCallback(async () => {
    if (!prompt.trim()) {
      return;
    }

    setLoading(true);
    setBenchmarkResult(null);
    setResultIsMock(false);
    setErrorMessage(null);

    const modelLabel =
      selectedModel === "mock" ? "Mock Engine (demo)" : selectedModelMeta?.label ?? "Mock Engine (demo)";
    setStatus(`Benchmarking with ${modelLabel}...`);

    try {
      if (selectedModel === "mock") {
        await new Promise((resolve) => setTimeout(resolve, 1200));
        setBenchmarkResult(generateMockResult());
        setResultIsMock(true);
        setStatus("Demo result (Mock Engine — fake scores)");
        return;
      }

      const data = await apiJson<BenchmarkPayload>("/benchmark/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: prompt.trim(), model: selectedModel }),
      });
      setBenchmarkResult(data);
      setResultIsMock(false);
      setStatus(`Benchmark complete (${data.processing_ms}ms)`);
    } catch (error) {
      showError(error);
      setStatus("Benchmark failed");
      setErrorMessage(buildBenchmarkErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [generateMockResult, prompt, selectedModel, selectedModelMeta]);

  const chartData = useMemo(() => {
    if (!benchmarkResult) {
      return [];
    }

    return [
      {
        subject: "Safety",
        A: benchmarkResult.metrics.safety.raw,
        B: benchmarkResult.metrics.safety.compiled,
        fullMark: 10,
      },
      {
        subject: "Clarity",
        A: benchmarkResult.metrics.clarity.raw,
        B: benchmarkResult.metrics.clarity.compiled,
        fullMark: 10,
      },
      {
        subject: "Conciseness",
        A: benchmarkResult.metrics.conciseness.raw,
        B: benchmarkResult.metrics.conciseness.compiled,
        fullMark: 10,
      },
    ];
  }, [benchmarkResult]);

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-start overflow-x-hidden bg-[#050505] p-3 py-4 sm:p-4 md:h-screen md:justify-center md:overflow-hidden md:p-8">
      <div className="pointer-events-none absolute left-[-20%] top-[-20%] h-[50vw] w-[50vw] rounded-full bg-amber-600/10 blur-[150px]" />
      <div className="pointer-events-none absolute bottom-[-20%] right-[-20%] h-[50vw] w-[50vw] rounded-full bg-orange-600/10 blur-[150px]" />

      <div className="glass z-10 flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col overflow-hidden rounded-2xl shadow-2xl ring-1 ring-white/10 animate-fade-in md:h-full md:max-h-[95vh] md:rounded-3xl">
        <header className="flex shrink-0 flex-col gap-3 border-b border-white/5 bg-black/40 p-4 backdrop-blur-md lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-600 to-orange-600 text-xl font-bold text-white shadow-lg shadow-amber-500/20">
                B
              </div>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-xl font-bold tracking-tight text-white/90">Prompt Benchmark</h1>
                  {selectedModel === "mock" && (
                    <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[10px] font-bold text-amber-300 shadow-[0_0_15px_rgba(245,158,11,0.08)] animate-pulse shrink-0">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-ping" />
                      Demo Mode Active: Fake Scores
                    </div>
                  )}
                </div>
                <div className="font-mono text-xs uppercase tracking-wider text-zinc-500 mt-0.5">
                  Compare raw vs compiled output
                </div>
                <div className="mt-1 text-xs text-zinc-400">
                  <span className="font-semibold text-amber-300">Raw</span> = your prompt as-is &nbsp;·&nbsp;{" "}
                  <span className="font-semibold text-emerald-300">Compiled</span> = Prompt Compiler&apos;s polished
                  version
                </div>
              </div>
            </div>
            <InfoButton
              title="What this page does"
              description="We send your prompt to a real AI model twice: once exactly as you wrote it (the Raw version) and once after Prompt Compiler rewrites it (the Compiled version). The radar chart and winner banner show whose answer was clearer, safer, and more concise."
            />
          </div>

          <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center lg:w-auto">
            <div className="w-full rounded-lg border border-white/5 bg-black/30 p-1 sm:w-auto">
              <label
                htmlFor="benchmark-model"
                className="block px-2 pb-1 pt-1 font-mono text-xs uppercase tracking-wider text-zinc-500"
              >
                Model
              </label>
              <select
                id="benchmark-model"
                value={selectedModel}
                onChange={(event) => setSelectedModel(event.target.value)}
                className="w-full cursor-pointer rounded border-none bg-[#1a1a1a] px-2 py-1.5 text-xs text-zinc-200 transition-colors focus:outline-none sm:min-w-[240px]"
              >
                <option value="mock" className="bg-[#1a1a1a] text-zinc-200">
                  Mock Engine — demo (fake scores)
                </option>
                {BENCHMARK_MODEL_GROUPS.map((group) => (
                  <optgroup
                    key={group.label}
                    label={`-- ${group.label} --`}
                    className="bg-[#1a1a1a] text-zinc-500"
                  >
                    {group.options.map((model) => (
                      <option key={model.id} value={model.id} className="bg-[#1a1a1a] text-zinc-200">
                        {`${model.label} [${model.badge}]`}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <p
                className={`px-2 pb-1 pt-2 text-xs ${selectedModel === "mock" ? "text-amber-300/80" : "text-zinc-500"}`}
              >
                {selectedModel === "mock"
                  ? "No model is called. Numbers below are randomized for UI preview only — pick a real model to run an actual benchmark."
                  : selectedModelMeta?.helperText}
              </p>
              <p className="px-2 pb-2 text-[10px] leading-relaxed text-zinc-600">
                <span className="font-mono text-zinc-500">[cheap]</span> runs fast and costs little.{" "}
                <span className="font-mono text-zinc-500">[balanced]</span> is smarter but slower.{" "}
                <span className="font-mono text-zinc-500">[preview]</span> is a newer model still being tested.
              </p>
            </div>

            <div
              className={`flex items-center justify-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold sm:justify-start ${
                errorMessage
                  ? "border-red-500/30 bg-red-500/10 text-red-300"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-400"
              }`}
            >
              {status}
            </div>
          </div>
        </header>

        <div className="flex flex-1 flex-col overflow-visible md:min-h-0 md:flex-row md:overflow-hidden">
          <div className="z-20 flex w-full flex-col gap-4 border-b border-white/5 bg-black/20 p-4 sm:p-5 md:w-[350px] md:shrink-0 md:border-b-0 md:border-r">
            <div className="group relative flex-1">
              <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-amber-500/5 to-orange-500/5 opacity-0 transition-opacity duration-500 group-focus-within:opacity-100" />
              <textarea
                id="benchmark-prompt"
                aria-label="Benchmark prompt input"
                className="h-full min-h-[160px] w-full resize-none rounded-xl border border-white/10 bg-black/30 p-4 font-mono text-sm leading-relaxed text-zinc-300 shadow-inner transition-all placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-amber-500/50"
                placeholder={"Enter a prompt to benchmark...\n\ne.g. 'Write a Python script to scrape data'"}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault();
                    if (!loading && prompt.trim()) {
                      void handleBenchmark();
                    }
                  }
                }}
              />
            </div>

            <button
              type="button"
              onClick={handleBenchmark}
              disabled={loading || !prompt.trim()}
              title={!prompt.trim() ? "Enter a prompt first to run a benchmark" : "Run Benchmark"}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 py-4 text-sm font-bold text-white shadow-lg shadow-amber-500/20 transition-all active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 hover:from-amber-500 hover:to-orange-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/50"
            >
              {loading ? (
                <span className="animate-pulse">Running...</span>
              ) : (
                <>
                  Run Benchmark{" "}
                  <kbd className="ml-2 hidden rounded border border-white/20 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] opacity-50 md:inline-block">
                    Ctrl/Cmd Enter
                  </kbd>
                </>
              )}
            </button>

            {errorMessage && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3.5 text-xs leading-relaxed text-red-200">
                <div className="space-y-2">
                  <div className="font-semibold text-red-300">
                    {isBackendConfigIssue(errorMessage)
                      ? "Cloud Benchmark Unavailable"
                      : "Benchmark Issue"}
                  </div>
                  <p className="opacity-90">
                    {isBackendConfigIssue(errorMessage)
                      ? "The selected cloud model could not run right now. If you are hosting this yourself, check the server's provider configuration. Otherwise switch to Mock Engine and keep exploring."
                      : errorMessage}
                  </p>
                  {isBackendConfigIssue(errorMessage) && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedModel("mock");
                        setErrorMessage(null);
                        setStatus("Ready");
                      }}
                      className="w-full rounded-lg border border-amber-500/40 bg-amber-600/20 px-3 py-1.5 text-[11px] font-bold text-amber-200 transition-all hover:bg-amber-600/30 active:scale-95"
                    >
                      Switch to Mock Engine (Demo Trial)
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="relative flex flex-1 flex-col overflow-hidden bg-black/10">
            {benchmarkResult ? (
              <div className="flex h-full flex-1 flex-col overflow-hidden animate-fade-in">
                {resultIsMock && (
                  <div className="shrink-0 border-b border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-100">
                    <strong className="font-bold text-amber-50">Demo data — not a real benchmark.</strong>{" "}
                    These scores are randomized to show what a real run looks like. Pick a real model above and re-run
                    to measure your prompt.
                  </div>
                )}
                <div className="flex h-[40%] min-h-[300px] border-b border-white/5">
                  <div className="relative flex flex-1 items-center justify-center p-4">
                    <h3 className="absolute left-4 top-4 text-xs font-semibold uppercase text-zinc-500">
                      Performance Radar
                    </h3>
                    <p className="absolute left-4 top-9 text-[10px] text-zinc-500">
                      Higher = better. The bigger shape wins.
                    </p>
                    <div className="h-full w-full max-w-[400px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <RadarChart outerRadius="70%" data={chartData}>
                          <PolarGrid stroke="rgba(255,255,255,0.1)" />
                          <PolarAngleAxis dataKey="subject" tick={{ fill: "#71717a", fontSize: 10 }} />
                          <PolarRadiusAxis angle={30} domain={[0, 10]} tick={false} axisLine={false} />
                          <Radar name="Raw" dataKey="A" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.3} />
                          <Radar name="Compiled" dataKey="B" stroke="#10b981" fill="#10b981" fillOpacity={0.4} />
                          <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} />
                        </RadarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="flex w-[300px] flex-col items-center justify-center gap-4 border-l border-white/5 bg-black/10 p-6">
                    <div className="space-y-1 text-center">
                      <div className="font-mono text-xs uppercase text-zinc-500">Winner</div>
                      <div
                        className={`text-2xl font-black tracking-tighter ${
                          benchmarkResult.winner === "compiled" ? "text-emerald-400" : "text-amber-400"
                        }`}
                      >
                        {benchmarkResult.winner === "compiled" ? "COMPILED PROMPT" : "RAW PROMPT"}
                      </div>
                    </div>

                    <div className="h-px w-full bg-white/10" />

                    <div className="space-y-1 text-center">
                      <div className="font-mono text-xs uppercase text-zinc-500">Improvement</div>
                      <div className="text-4xl font-black text-emerald-400 drop-shadow-lg">
                        +{benchmarkResult.improvement_score}%
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex min-h-0 flex-1 flex-col bg-black/20">
                  <div className="flex-1 overflow-hidden p-4">
                    <DiffViewer oldText={benchmarkResult.raw_output} newText={benchmarkResult.compiled_output} />
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-6 p-10 text-center animate-fade-in">
                <div className={`text-6xl drop-shadow-2xl ${errorMessage ? "text-red-300" : "text-zinc-400"}`}>
                  {errorMessage ? "!" : "B"}
                </div>
                <div className="max-w-sm space-y-2">
                  <h3 className="font-medium tracking-wide text-zinc-200">
                    {errorMessage ? "Benchmark unavailable" : "No benchmark yet"}
                  </h3>
                  <p className="mb-4 text-sm text-zinc-400">
                    {errorMessage
                      ? errorMessage
                      : "Paste a prompt on the left, pick a real model (the default Mock Engine returns demo numbers), then run a benchmark."}
                  </p>
                  {!errorMessage && (
                    <div className="flex flex-col items-center gap-3 mt-6 w-full">
                      <button
                        type="button"
                        onClick={handleBenchmark}
                        disabled={loading || !prompt.trim()}
                        title={!prompt.trim() ? "Enter a prompt first to run a benchmark" : "Run Benchmark"}
                        className="mx-auto flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-amber-500/20 transition-all active:scale-95 hover:from-amber-500 hover:to-orange-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Run Benchmark
                      </button>
                      {!prompt.trim() && (
                        <button
                          type="button"
                          onClick={() => {
                            setPrompt("Write a Python script to scrape data from a Wikipedia page and extract all the tables.");
                            setTimeout(() => {
                              const textarea = document.getElementById('benchmark-prompt');
                              if (textarea) textarea.focus();
                            }, 0);
                          }}
                          className="text-xs text-amber-400/80 hover:text-amber-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-500 rounded px-2 py-1"
                        >
                          or try an example
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
