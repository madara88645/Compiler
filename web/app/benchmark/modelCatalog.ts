export type BenchmarkModelBadge = "cheap" | "balanced" | "preview";
export type BenchmarkModelAvailability = "production" | "preview";

export type BenchmarkModelDefinition = {
  id: string;
  label: string;
  badge: BenchmarkModelBadge;
  availability: BenchmarkModelAvailability;
  helperText: string;
  group: "Cheap" | "Balanced" | "Preview";
};

export const BENCHMARK_MODELS: BenchmarkModelDefinition[] = [
  {
    id: "openai/gpt-oss-20b",
    label: "GPT-OSS 20B",
    badge: "cheap",
    availability: "production",
    helperText: "Cheap and surprisingly capable. Good default for everyday tests.",
    group: "Cheap",
  },
  {
    id: "mistralai/mistral-small-3.2-24b-instruct",
    label: "Mistral Small 3.2 24B",
    badge: "cheap",
    availability: "production",
    helperText: "Affordable and strong at instruction-following plus structured output.",
    group: "Cheap",
  },
  {
    id: "openai/gpt-oss-120b",
    label: "GPT-OSS 120B",
    badge: "balanced",
    availability: "production",
    helperText: "Higher-quality option when you can trade speed for depth.",
    group: "Balanced",
  },
  {
    id: "qwen/qwen3-32b",
    label: "Qwen 3 32B",
    badge: "preview",
    availability: "preview",
    helperText: "Newer model with a different reasoning style. Useful for a second opinion on your prompt.",
    group: "Preview",
  },
];

export const BENCHMARK_MODEL_GROUPS = [
  { label: "Cheap", options: BENCHMARK_MODELS.filter((model) => model.group === "Cheap") },
  { label: "Balanced", options: BENCHMARK_MODELS.filter((model) => model.group === "Balanced") },
  { label: "Preview", options: BENCHMARK_MODELS.filter((model) => model.group === "Preview") },
] as const;

export function getBenchmarkModelById(id: string): BenchmarkModelDefinition | undefined {
  return BENCHMARK_MODELS.find((model) => model.id === id);
}
