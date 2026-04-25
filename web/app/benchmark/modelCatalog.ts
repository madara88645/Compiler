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
        helperText: "Lowest-cost baseline on Groq for fast A/B checks.",
        group: "Cheap",
    },
    {
        id: "openai/gpt-oss-20b",
        label: "GPT-OSS 20B",
        badge: "cheap",
        availability: "production",
        helperText: "Cheap open model with a strong quality-to-cost ratio.",
        group: "Cheap",
    },
    {
        id: "mistral-saba-24b",
        label: "Mistral Saba 24B",
        badge: "cheap",
        availability: "production",
        helperText:
            "Affordable multilingual option for broader prompt coverage.",
        group: "Cheap",
    },
    {
        id: "llama-3.3-70b-versatile",
        label: "Llama 3.3 70B Versatile",
        badge: "balanced",
        availability: "production",
        helperText: "Balanced quality model for richer benchmark comparisons.",
        group: "Balanced",
    },
    {
        id: "openai/gpt-oss-120b",
        label: "GPT-OSS 120B",
        badge: "balanced",
        availability: "production",
        helperText:
            "Stronger reference model when you want a higher-quality comparison.",
        group: "Balanced",
    },
    {
        id: "meta-llama/llama-4-scout-17b-16e-instruct",
        label: "Llama 4 Scout 17B 16E",
        badge: "preview",
        availability: "preview",
        helperText:
            "Preview Meta model with modern context handling and multimodal lineage.",
        group: "Preview",
    },
    {
        id: "qwen/qwen3-32b",
        label: "Qwen 3 32B",
        badge: "preview",
        availability: "preview",
        helperText:
            "Preview Qwen model for alternative reasoning and response style checks.",
        group: "Preview",
    },
];

export const BENCHMARK_MODEL_GROUPS = [
    {
        label: "Cheap",
        options: BENCHMARK_MODELS.filter((model) => model.group === "Cheap"),
    },
    {
        label: "Balanced",
        options: BENCHMARK_MODELS.filter((model) => model.group === "Balanced"),
    },
    {
        label: "Preview",
        options: BENCHMARK_MODELS.filter((model) => model.group === "Preview"),
    },
] as const;

export function getBenchmarkModelById(
    id: string,
): BenchmarkModelDefinition | undefined {
    return BENCHMARK_MODELS.find((model) => model.id === id);
}
