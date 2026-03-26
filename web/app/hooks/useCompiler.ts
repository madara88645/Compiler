"use client";

import { useCallback, useState } from "react";

import { ApiError } from "../../config";
import { compilePrompt } from "../../lib/api/promptc";
import type {
  CompileMode,
  CompileResponse,
  SecurityFinding,
  SecurityMetadata,
} from "../../lib/api/types";

const REQUEST_TIMEOUT_MS = 190_000;

function buildCompileSignal() {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  return {
    signal: controller.signal,
    cleanup() {
      window.clearTimeout(timeoutId);
    },
  };
}

function extractSecurityMetadata(result: CompileResponse): SecurityMetadata | undefined {
  return result.ir.metadata?.security;
}

function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail;
  }

  if (error instanceof Error && error.name === "AbortError") {
    return "Timeout: AI model took too long.";
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Connection failed.";
}

export function useCompiler() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CompileResponse | null>(null);
  const [status, setStatus] = useState("Ready");
  const [securityFindings, setSecurityFindings] = useState<SecurityFinding[]>([]);
  const [redactedText, setRedactedText] = useState("");
  const [pendingText, setPendingText] = useState("");

  const runCompile = useCallback(async (text: string, mode: CompileMode) => {
    if (!text.trim()) {
      return;
    }

    setLoading(true);
    setStatus("Generating...");

    const { signal, cleanup } = buildCompileSignal();

    try {
      setStatus("AI Thinking...");

      const response = await compilePrompt(
        {
          text,
          diagnostics: true,
          v2: true,
          render_v2_prompts: true,
          mode,
        },
        signal,
      );

      const security = extractSecurityMetadata(response);
      if (security && !security.is_safe) {
        setSecurityFindings(security.findings);
        setRedactedText(security.redacted_text);
        setPendingText(text);
        setStatus("Security Alert Detected");
        return;
      }

      setResult(response);
      setStatus(`Done in ${response.processing_ms}ms`);
    } catch (error: unknown) {
      setStatus(`Error: ${toUserMessage(error)}`);
    } finally {
      cleanup();
      setLoading(false);
    }
  }, []);

  const resolveSecurityDecision = useCallback(
    async (useRedacted: boolean, mode: CompileMode) => {
      const textToCompile = useRedacted ? redactedText : pendingText;
      if (!textToCompile.trim()) {
        return;
      }

      setSecurityFindings([]);
      setLoading(true);
      setStatus(`Resuming with ${useRedacted ? "Safe" : "Unsafe"} text...`);

      const { signal, cleanup } = buildCompileSignal();

      try {
        const response = await compilePrompt(
          {
            text: textToCompile,
            diagnostics: true,
            v2: true,
            render_v2_prompts: true,
            mode,
          },
          signal,
        );

        setResult(response);
        setStatus(`Done in ${response.processing_ms}ms`);
      } catch (error: unknown) {
        setStatus(`Error: ${toUserMessage(error)}`);
      } finally {
        cleanup();
        setLoading(false);
      }
    },
    [pendingText, redactedText],
  );

  const cancelSecurityReview = useCallback(() => {
    setSecurityFindings([]);
    setLoading(false);
    setStatus("Cancelled");
  }, []);

  return {
    loading,
    result,
    status,
    securityFindings,
    redactedText,
    runCompile,
    resolveSecurityDecision,
    cancelSecurityReview,
  };
}
