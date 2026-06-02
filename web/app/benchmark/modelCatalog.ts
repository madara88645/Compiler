import benchmarkModelsData from "./models.json" with { type: "json" };

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

export const BENCHMARK_MODELS = benchmarkModelsData as BenchmarkModelDefinition[];

export const BENCHMARK_MODEL_GROUPS = [
  { label: "Cheap", options: BENCHMARK_MODELS.filter((model) => model.group === "Cheap") },
  { label: "Balanced", options: BENCHMARK_MODELS.filter((model) => model.group === "Balanced") },
  { label: "Preview", options: BENCHMARK_MODELS.filter((model) => model.group === "Preview") },
] as const;

export function getBenchmarkModelById(id: string): BenchmarkModelDefinition | undefined {
  return BENCHMARK_MODELS.find((model) => model.id === id);
}
