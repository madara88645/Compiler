import { apiJson } from "../../config.ts";
import type {
  CompileRequest,
  CompileResponse,
  CompileIr,
  CompileMetadata,
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
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function readOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function normalizeSecurityFinding(value: unknown): SecurityFinding {
  const record = asObject(value);
  return {
    type: readString(record?.type, "unknown"),
    original: readString(record?.original),
    masked: readString(record?.masked),
  };
}

function normalizeSecurityMetadata(value: unknown): SecurityMetadata | undefined {
  const record = asObject(value);
  if (!record) {
    return undefined;
  }

  return {
    is_safe: Boolean(record.is_safe),
    findings: Array.isArray(record.findings) ? record.findings.map(normalizeSecurityFinding) : [],
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
    retrieval_status: readString(record.retrieval_status),
    retrieval_note: readString(record.retrieval_note),
  };
}

function normalizeIr(value: unknown): CompileIr {
  const record = asObject(value) || {};
  return {
    ...record,
    metadata: normalizeMetadata(record.metadata),
  };
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

  return {
    system_prompt: readString(record.system_prompt),
    user_prompt: readString(record.user_prompt),
    plan: readString(record.plan),
    expanded_prompt: readString(record.expanded_prompt),
    system_prompt_v2: readString(record.system_prompt_v2) || undefined,
    user_prompt_v2: readString(record.user_prompt_v2) || undefined,
    plan_v2: readString(record.plan_v2) || undefined,
    expanded_prompt_v2: readString(record.expanded_prompt_v2) || undefined,
    ir: normalizeIr(record.ir),
    processing_ms: readNumber(record.processing_ms),
    critique: normalizeCritique(record.critique),
  };
}

export function normalizeRagUploadResponse(value: unknown): RagUploadResponse {
  const record = asObject(value);
  if (!record) {
    throw new Error("Invalid RAG upload response.");
  }

  const filename = readString(record.filename, "upload.txt");
  const totalChunks = readNumber(record.total_chunks, readNumber(record.num_chunks));

  return {
    ingested_docs: readNumber(record.ingested_docs, record.success ? 1 : 0),
    total_chunks: totalChunks,
    elapsed_ms: readNumber(record.elapsed_ms),
    filename,
    success: typeof record.success === "boolean" ? record.success : true,
    num_chunks: readNumber(record.num_chunks, totalChunks),
    message: readString(record.message, `Indexed ${filename} into the RAG index.`),
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
    avg_bytes: readNumber(record.avg_bytes),
    largest: Array.isArray(record.largest)
      ? record.largest.map((item) => {
          const largestRecord = asObject(item);
          return {
            path: readString(largestRecord?.path),
            size: readNumber(largestRecord?.size),
          };
        })
      : [],
  };
}

export function formatSearchResultForPrompt(result: RagSearchResult): string {
  const location = result.path ? `[Source: ${result.path}]` : "[Source: unknown]";
  return `${location}\n${result.snippet}`.trim();
}

export function formatSearchScore(result: RagSearchResult): string {
  return Number.isFinite(result.score) ? result.score.toFixed(3) : "0.000";
}

export async function compilePrompt(request: CompileRequest, signal?: AbortSignal): Promise<CompileResponse> {
  const response = await apiJson<unknown>("/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  return normalizeCompileResponse(response);
}

export async function uploadContextFile(request: RagUploadRequest): Promise<RagUploadResponse> {
  const response = await apiJson<unknown>("/rag/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return normalizeRagUploadResponse(response);
}

export async function ingestContextPath(request: RagIngestRequest): Promise<RagIngestResponse> {
  return apiJson<RagIngestResponse>("/rag/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function searchContext(request: RagSearchRequest): Promise<RagSearchResult[]> {
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
