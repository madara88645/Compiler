import { ApiError, apiJson } from "../../config.ts";
import type {
    CompileRequest,
    CompileResponse,
    CompileIr,
    CompileMetadata,
    CompilePolicy,
    ContextSnippet,
    ContextSuggestion,
    Critique,
    CritiqueIssue,
    JsonObject,
    RagIngestRequest,
    RagIngestResponse,
    RagSearchRequest,
    RagSearchResult,
    RagStats,
    RagUploadRequest,
    RagUploadResponse,
    SecurityFinding,
    SecurityMetadata,
} from "./types";

function asObject(value: unknown): JsonObject | null {
    return value && typeof value === "object" && !Array.isArray(value)
        ? (value as JsonObject)
        : null;
}

function readString(value: unknown, fallback = ""): string {
    return typeof value === "string" ? value : fallback;
}

function readNumber(value: unknown, fallback = 0): number {
    return typeof value === "number" && Number.isFinite(value)
        ? value
        : fallback;
}

function readOptionalNumber(value: unknown): number | undefined {
    return typeof value === "number" && Number.isFinite(value)
        ? value
        : undefined;
}

function readStringList(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }

    return value.filter(
        (item): item is string =>
            typeof item === "string" && item.trim().length > 0,
    );
}

function normalizePolicy(value: unknown): CompilePolicy {
    const record = asObject(value);

    return {
        risk_level: readString(record?.risk_level, "low"),
        risk_domains: readStringList(record?.risk_domains),
        allowed_tools: readStringList(record?.allowed_tools),
        forbidden_tools: readStringList(record?.forbidden_tools),
        sanitization_rules: readStringList(record?.sanitization_rules),
        data_sensitivity: readString(record?.data_sensitivity, "public"),
        execution_mode: readString(record?.execution_mode, "advice_only"),
    };
}

function normalizeSecurityFinding(value: unknown): SecurityFinding {
    const record = asObject(value);
    return {
        type: readString(record?.type, "unknown"),
        original: readString(record?.original),
        masked: readString(record?.masked),
    };
}

function normalizeSecurityMetadata(
    value: unknown,
): SecurityMetadata | undefined {
    const record = asObject(value);
    if (!record) {
        return undefined;
    }

    const findings = Array.isArray(record.findings)
        ? record.findings.map(normalizeSecurityFinding)
        : [];
    const explicitSafety =
        typeof record.is_safe === "boolean" ? record.is_safe : undefined;

    return {
        is_safe: explicitSafety ?? findings.length === 0,
        findings,
        redacted_text: readString(record.redacted_text),
    };
}

function normalizeSuggestions(value: unknown): ContextSuggestion[] | undefined {
    if (!Array.isArray(value)) {
        return undefined;
    }

    return value.map((item) => {
        const record = asObject(item);
        return {
            path: readString(record?.path),
            name: readString(record?.name),
            reason: readString(record?.reason),
        };
    });
}

function normalizeSnippets(value: unknown): ContextSnippet[] | undefined {
    if (!Array.isArray(value)) {
        return undefined;
    }

    return value.map((item) => {
        const record = asObject(item);
        return {
            path: readString(record?.path),
            snippet: readString(record?.snippet),
            score: readOptionalNumber(record?.score),
        };
    });
}

function normalizeMetadata(value: unknown): CompileMetadata | undefined {
    const record = asObject(value);
    if (!record) {
        return undefined;
    }

    return {
        ...record,
        security: normalizeSecurityMetadata(record.security),
        context_suggestions: normalizeSuggestions(record.context_suggestions),
        context_snippets: normalizeSnippets(record.context_snippets),
        retrieval_status: readString(record.retrieval_status) || undefined,
        retrieval_note: readString(record.retrieval_note) || undefined,
    };
}

function normalizeIr(value: unknown): CompileIr {
    const record = asObject(value) || {};
    return {
        ...record,
        metadata: normalizeMetadata(record.metadata),
        policy: normalizePolicy(record.policy),
    };
}

function hasNonEmptyString(value: unknown): boolean {
    return typeof value === "string" && value.trim().length > 0;
}

function hasNonEmptyArray(value: unknown): boolean {
    return Array.isArray(value) && value.length > 0;
}

function hasNonEmptyObject(value: unknown): boolean {
    const record = asObject(value);
    return record ? Object.keys(record).length > 0 : false;
}

function hasUsableIr(value: unknown): boolean {
    const record = asObject(value);
    if (!record) {
        return false;
    }

    return (
        hasNonEmptyString(record.language) ||
        hasNonEmptyString(record.persona) ||
        hasNonEmptyString(record.role) ||
        hasNonEmptyString(record.domain) ||
        hasNonEmptyArray(record.intents) ||
        hasNonEmptyArray(record.goals) ||
        hasNonEmptyArray(record.tasks) ||
        hasNonEmptyArray(record.constraints) ||
        hasNonEmptyArray(record.steps) ||
        hasNonEmptyArray(record.tools) ||
        hasNonEmptyObject(record.metadata) ||
        hasNonEmptyObject(record.policy)
    );
}

function hasUsableCompileOutput(record: JsonObject): boolean {
    return (
        hasNonEmptyString(record.system_prompt) ||
        hasNonEmptyString(record.user_prompt) ||
        hasNonEmptyString(record.plan) ||
        hasNonEmptyString(record.expanded_prompt) ||
        hasNonEmptyString(record.system_prompt_v2) ||
        hasNonEmptyString(record.user_prompt_v2) ||
        hasNonEmptyString(record.plan_v2) ||
        hasNonEmptyString(record.expanded_prompt_v2) ||
        hasUsableIr(record.ir) ||
        hasUsableIr(record.ir_v2)
    );
}

function normalizeCritiqueIssues(value: unknown): CritiqueIssue[] {
    if (!Array.isArray(value)) {
        return [];
    }

    return value.map((item) => {
        const record = asObject(item);
        return {
            type: readString(record?.type, "unknown"),
            description: readString(record?.description),
            severity: readString(record?.severity, "info"),
        };
    });
}

function normalizeCritique(value: unknown): Critique | undefined {
    const record = asObject(value);
    if (!record) {
        return undefined;
    }

    return {
        verdict: readString(record.verdict),
        score: readNumber(record.score),
        issues: normalizeCritiqueIssues(record.issues),
        feedback: readString(record.feedback),
    };
}

export function normalizeCompileResponse(value: unknown): CompileResponse {
    const record = asObject(value);
    if (!record) {
        throw new Error("Invalid compile response.");
    }

    if (!hasUsableCompileOutput(record)) {
        throw new Error("Invalid compile response: missing compiler output.");
    }

    const ir = normalizeIr(record.ir);
    const irV2 = asObject(record.ir_v2) ? normalizeIr(record.ir_v2) : ir;

    return {
        system_prompt: readString(record.system_prompt),
        user_prompt: readString(record.user_prompt),
        plan: readString(record.plan),
        expanded_prompt: readString(record.expanded_prompt),
        system_prompt_v2: readString(record.system_prompt_v2) || undefined,
        user_prompt_v2: readString(record.user_prompt_v2) || undefined,
        plan_v2: readString(record.plan_v2) || undefined,
        expanded_prompt_v2: readString(record.expanded_prompt_v2) || undefined,
        ir,
        ir_v2: irV2,
        processing_ms: readNumber(record.processing_ms),
        request_id: readString(record.request_id) || undefined,
        heuristic_version: readString(record.heuristic_version) || undefined,
        heuristic2_version: readString(record.heuristic2_version) || undefined,
        trace: Array.isArray(record.trace)
            ? readStringList(record.trace)
            : undefined,
        critique: normalizeCritique(record.critique),
    };
}

export function normalizeRagUploadResponse(value: unknown): RagUploadResponse {
    const record = asObject(value);
    if (!record) {
        throw new Error("Invalid RAG upload response.");
    }

    const filename = readString(record.filename, "upload.txt");
    const totalChunks = readNumber(
        record.total_chunks,
        readNumber(record.num_chunks),
    );

    return {
        ingested_docs: readNumber(record.ingested_docs, record.success ? 1 : 0),
        total_chunks: totalChunks,
        elapsed_ms: readNumber(record.elapsed_ms),
        filename,
        success: typeof record.success === "boolean" ? record.success : true,
        num_chunks: readNumber(record.num_chunks, totalChunks),
        message: readString(
            record.message,
            `Indexed ${filename} into the RAG index.`,
        ),
    };
}

export function normalizeRagSearchResults(value: unknown): RagSearchResult[] {
    if (!Array.isArray(value)) {
        throw new Error("Invalid RAG search response.");
    }

    return value.map((item) => {
        const record = asObject(item);
        return {
            path: readString(record?.path, readString(record?.source)),
            snippet: readString(record?.snippet, readString(record?.content)),
            score: readNumber(record?.score),
        };
    });
}

export function normalizeRagStats(value: unknown): RagStats {
    const record = asObject(value);
    if (!record) {
        throw new Error("Invalid RAG stats response.");
    }

    return {
        docs: readNumber(record.docs),
        chunks: readNumber(record.chunks),
        total_bytes: readNumber(record.total_bytes),
        avg_bytes: readOptionalNumber(record.avg_bytes),
        largest: Array.isArray(record.largest)
            ? record.largest.map((item) => {
                  const largestRecord = asObject(item);
                  return {
                      path: readString(largestRecord?.path),
                      size: readNumber(largestRecord?.size),
                  };
              })
            : undefined,
    };
}

export function formatSearchResultForPrompt(result: RagSearchResult): string {
    const location = result.path
        ? `[Source: ${result.path}]`
        : "[Source: unknown]";
    return `${location}\n${result.snippet}`.trim();
}

export function formatSearchScore(result: RagSearchResult): string {
    return Number.isFinite(result.score) ? result.score.toFixed(3) : "0.000";
}

function isAbortError(error: unknown): boolean {
    return error instanceof Error && error.name === "AbortError";
}

function isTransientCompileError(error: unknown): boolean {
    if (isAbortError(error)) {
        return false;
    }

    if (error instanceof ApiError) {
        return [408, 429, 502, 503, 504].includes(error.status);
    }

    if (error instanceof TypeError) {
        return true;
    }

    if (error instanceof Error) {
        const message = error.message.toLowerCase();
        return (
            message.includes("failed to fetch") ||
            message.includes("networkerror") ||
            message.includes("load failed")
        );
    }

    return false;
}

async function postCompile(
    request: CompileRequest,
    signal?: AbortSignal,
): Promise<unknown> {
    return apiJson<unknown>("/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal,
    });
}

export async function compilePrompt(
    request: CompileRequest,
    signal?: AbortSignal,
): Promise<CompileResponse> {
    let response: unknown;
    try {
        response = await postCompile(request, signal);
    } catch (error) {
        if (!isTransientCompileError(error) || signal?.aborted) {
            throw error;
        }
        response = await postCompile(request, signal);
    }

    return normalizeCompileResponse(response);
}

export async function uploadContextFile(
    request: RagUploadRequest,
): Promise<RagUploadResponse> {
    const response = await apiJson<unknown>("/rag/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
    return normalizeRagUploadResponse(response);
}

export async function ingestContextPath(
    request: RagIngestRequest,
): Promise<RagIngestResponse> {
    return apiJson<RagIngestResponse>("/rag/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}

export async function searchContext(
    request: RagSearchRequest,
): Promise<RagSearchResult[]> {
    const response = await apiJson<unknown>("/rag/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
    return normalizeRagSearchResults(response);
}

export async function fetchRagStats(): Promise<RagStats> {
    const response = await apiJson<unknown>("/rag/stats");
    return normalizeRagStats(response);
}
