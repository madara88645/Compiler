export type JsonObject = Record<string, unknown>;

export type ContextSuggestion = {
  path: string;
  name: string;
  reason: string;
};

export type ContextSnippet = {
  path: string;
  snippet: string;
  score?: number;
};

export type SecurityFinding = {
  type: string;
  original: string;
  masked: string;
};

export type SecurityMetadata = {
  is_safe: boolean;
  findings: SecurityFinding[];
  redacted_text: string;
};

export type CompileMetadata = JsonObject & {
  security?: SecurityMetadata;
  context_suggestions?: ContextSuggestion[];
  context_snippets?: ContextSnippet[];
  retrieval_status?: string;
  retrieval_note?: string;
};

export type CompileIr = JsonObject & {
  metadata?: CompileMetadata;
};

export type CritiqueIssue = {
  type: string;
  description: string;
  severity: string;
};

export type Critique = {
  verdict: string;
  score: number;
  issues: CritiqueIssue[];
  feedback: string;
};

export type CompileResponse = {
  system_prompt: string;
  user_prompt: string;
  plan: string;
  expanded_prompt: string;
  system_prompt_v2?: string;
  user_prompt_v2?: string;
  plan_v2?: string;
  expanded_prompt_v2?: string;
  ir: CompileIr;
  processing_ms: number;
  critique?: Critique | null;
};

export type CompileMode = "conservative" | "default";

export type CompileRequest = {
  text: string;
  diagnostics: boolean;
  v2: boolean;
  render_v2_prompts: boolean;
  mode: CompileMode;
};

export type RagUploadRequest = {
  filename: string;
  content: string;
};

export type RagUploadResponse = {
  ingested_docs: number;
  total_chunks: number;
  elapsed_ms: number;
  filename: string;
  success: boolean;
  num_chunks: number;
  message: string;
};

export type RagIngestRequest = {
  paths: string[];
};

export type RagIngestResponse = {
  ingested_docs: number;
  total_chunks: number;
  elapsed_ms: number;
};

export type RagSearchRequest = {
  query: string;
  limit: number;
};

export type RagSearchResult = {
  path: string;
  snippet: string;
  score: number;
};

export type RagStats = {
  docs: number;
  chunks: number;
  total_bytes: number;
  avg_bytes?: number;
  largest?: Array<{ path: string; size: number }>;
};
