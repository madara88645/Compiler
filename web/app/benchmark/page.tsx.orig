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
import { showError } from "../lib/showError";
import DiffViewer from "../components/DiffViewer";
import InfoButton from "../components/InfoButton";
import {
  BENCHMARK_MODEL_GROUPS,
  getBenchmarkModelById,
} from "./modelCatalog";

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

export default function BenchmarkPage() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkPayload | null>(null);
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
    setErrorMessage(null);

    const modelLabel = selectedModelMeta?.label ?? "Mock Engine";
    setStatus(`Benchmarking with ${modelLabel}...`);

    try {
      if (selectedModel === "mock") {
        await new Promise((resolve) => setTimeout(resolve, 1200));
        setBenchmarkResult(generateMockResult());
        setStatus("Benchmark complete (Mock)");
        return;
      }

      const data = await apiJson<BenchmarkPayload>("/benchmark/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: prompt.trim(), model: selectedModel }),
      });
      setBenchmarkResult(data);
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
      { subject: "Safety", A: benchmarkResult.metrics.safety.raw, B: benchmarkResult.metrics.safety.compiled, fullMark: 10 },
      { subject: "Clarity", A: benchmarkResult.metrics.clarity.raw, B: benchmarkResult.metrics.clarity.compiled, fullMark: 10 },
      {
        subject: "Conciseness",
        A: benchmarkResult.metrics.conciseness.raw,
        B: benchmarkResult.metrics.conciseness.compiled,
        fullMark: 10,
      },
    ];
  }, [benchmarkResult]);

  return (
    <main className="relative flex h-screen flex-col items-center justify-center overflow-hidden bg-[#050505] p-4 md:p-8">
      <div className="pointer-events-none absolute left-[-20%] top-[-20%] h-[50vw] w-[50vw] rounded-full bg-amber-600/10 blur-[150px]" />
      <div className="pointer-events-none absolute bottom-[-20%] right-[-20%] h-[50vw] w-[50vw] rounded-full bg-orange-600/10 blur-[150px]" />

      <div className="glass animate-fade-in z-10 flex h-full max-h-[95vh] w-full max-w-7xl flex-col overflow-hidden rounded-3xl shadow-2xl ring-1 ring-white/10">
        <header className="flex shrink-0 items-center justify-between border-b border-white/5 bg-black/40 p-4 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-600 to-orange-600 text-xl font-bold text-white shadow-lg shadow-amber-500/20">
                B
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight text-white/90">Battle Arena</h1>
                <div className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                  Raw vs Compiled Benchmark
                </div>
              </div>
            </div>
            <InfoButton
              title="Benchmark Suite"
              description="Run automated tests across multiple LLM models to evaluate the effectiveness and token efficiency of your compiled prompts."
            />
          </div>

          <div className="flex items-center gap-4">
            <div className="rounded-lg border border-white/5 bg-black/30 p-1">
              <label
                htmlFor="benchmark-model"
                className="block px-2 pb-1 pt-1 font-mono text-[10px] uppercase tracking-wider text-zinc-500"
              >
                Model
              </label>
              <select
                id="benchmark-model"
                value={selectedModel}
                onChange={(event) => setSelectedModel(event.target.value)}
                className="min-w-[240px] cursor-pointer rounded border-none px-2 py-1.5 text-xs text-zinc-200 transition-colors focus:outline-none"
                style={{ backgroundColor: "#1a1a1a" }}
              >
                <option value="mock" style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}>
                  Mock Engine [local]
                </option>
                {BENCHMARK_MODEL_GROUPS.map((group) => (
                  <optgroup
                    key={group.label}
                    label={`-- ${group.label} --`}
                    style={{ backgroundColor: "#1a1a1a", color: "#888" }}
                  >
                    {group.options.map((model) => (
                      <option
                        key={model.id}
                        value={model.id}
                        style={{ backgroundColor: "#1a1a1a", color: "#e4e4e7" }}
                      >
                        {`${model.label} [${model.badge}]`}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <p className="px-2 pb-1 pt-2 text-[11px] text-zinc-500">
                {selectedModel === "mock"
                  ? "Client-side mock engine for instant UI previews."
                  : selectedModelMeta?.helperText}
              </p>
            </div>

            <div
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold ${
                errorMessage
                  ? "border-red-500/30 bg-red-500/10 text-red-300"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-400"
              }`}
            >
              {status}
            </div>
          </div>
        </header>

        <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
          <div className="z-20 flex w-full md:w-[350px] md:shrink-0 flex-col gap-5 border-b md:border-b-0 md:border-r border-white/5 bg-black/20 p-5">
            <div className="group relative flex-1">
              <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-amber-500/5 to-orange-500/5 opacity-0 transition-opacity duration-500 group-focus-within:opacity-100" />
              <textarea
                id="benchmark-prompt"
                aria-label="Benchmark prompt input"
                className="h-full min-h-[180px] w-full resize-none rounded-xl border border-white/10 bg-black/30 p-4 font-mono text-sm leading-relaxed text-zinc-300 shadow-inner transition-all placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-amber-500/50"
                placeholder={"Enter a prompt to start the battle...\n\ne.g. 'Write a Python script to scrape data'"}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
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
              title={!prompt.trim() ? "Enter a prompt first to start battle" : "Start Battle"}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 py-4 text-sm font-bold text-white shadow-lg shadow-amber-500/20 transition-all active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 hover:from-amber-500 hover:to-orange-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/50"
            >
            {loading ? <span className="animate-pulse">FIGHTING...</span> : <>START BATTLE <kbd className="hidden md:inline-block ml-2 text-[10px] font-mono opacity-50 border border-white/20 rounded px-1.5 py-0.5 bg-white/5">Ctrl/⌘ Enter</kbd></>}
            </button>

            {errorMessage && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-200">
                {errorMessage}
              </div>
            )}
          </div>

          <div className="relative flex flex-1 flex-col overflow-hidden bg-black/10">
            {benchmarkResult ? (
              <div className="flex h-full flex-1 flex-col overflow-hidden animate-fade-in">
                <div className="flex h-[40%] min-h-[300px] border-b border-white/5">
                  <div className="relative flex flex-1 items-center justify-center p-4">
                    <h3 className="absolute left-4 top-4 text-xs font-semibold uppercase text-zinc-500">
                      Performance Radar
                    </h3>
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
                  <p className="text-sm text-zinc-400">
                    {errorMessage
                      ? errorMessage
                      : "Paste a prompt on the left, pick a model, then hit Start Battle to compare raw vs compiled output."}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
