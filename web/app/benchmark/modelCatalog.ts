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
    id: "llama-3.1-8b-instant",
    label: "Llama 3.1 8B Instant",
    badge: "cheap",
    availability: "production",
    helperText: "Cheapest model. Use this for a quick sanity check — runs in a second or two.",
    group: "Cheap",
  },
  {
    id: "openai/gpt-oss-20b",
    label: "GPT-OSS 20B",
    badge: "cheap",
    availability: "production",
    helperText: "Cheap and surprisingly capable. Good default for everyday tests.",
    group: "Cheap",
  },
  {
    id: "mistral-saba-24b",
    label: "Mistral Saba 24B",
    badge: "cheap",
    availability: "production",
    helperText: "Affordable and works well in multiple languages — handy if your prompt isn't in English.",
    group: "Cheap",
  },
  {
    id: "llama-3.3-70b-versatile",
    label: "Llama 3.3 70B Versatile",
    badge: "balanced",
    availability: "production",
    helperText: "Smarter model. Slower and pricier, but answers are more thoughtful.",
    group: "Balanced",
  },
  {
    id: "openai/gpt-oss-120b",
    label: "GPT-OSS 120B",
    badge: "balanced",
    availability: "production",
    helperText: "Bigger and stronger. Use this when you want the most polished comparison.",
    group: "Balanced",
  },
  {
    id: "meta-llama/llama-4-scout-17b-16e-instruct",
    label: "Llama 4 Scout 17B 16E",
    badge: "preview",
    availability: "preview",
    helperText: "Newer model. Still being evaluated — try it if you want to compare cutting-edge results.",
    group: "Preview",
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
