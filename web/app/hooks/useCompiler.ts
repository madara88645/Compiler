"use client";

import { useCallback, useRef, useState } from "react";

import { showError } from "../lib/showError";
import { compilePrompt } from "../../lib/api/promptc";
import type {
  CompileMode,
  CompileResponse,
  SecurityFinding,
  SecurityMetadata,
} from "../../lib/api/types";

const REQUEST_TIMEOUT_MS = 190_000;

function extractSecurityMetadata(result: CompileResponse): SecurityMetadata | undefined {
  // Check v1 security metadata from scan_text
  const v1Security = result.ir.metadata?.security;

  // Check critique verdict
  const critique = result.critique;
  const critiqueVerdict = critique?.verdict?.toUpperCase();

  // Check if there are critical diagnostics in ir_v2
  const criticalDiagnostics = (result.ir_v2?.diagnostics ?? []).filter(
    (d) => d.severity === "critical"
  );

  // If critique REJECTs or has critical security diagnostics, escalate to security alert
  const hasCritiqueRejection = critiqueVerdict === "REJECT";
  const hasCriticalSecurityDiagnostic = criticalDiagnostics.some(
    (d) => d.category === "security" || d.category === "safety"
  );

  if (hasCritiqueRejection || hasCriticalSecurityDiagnostic) {
    // Build findings from critique issues
    const critiqueFindings = (critique?.issues || []).map((issue) => ({
      type: `critique_${issue.type.toLowerCase().replace(/\s+/g, "_")}`,
      original: "***",
      masked: `[SECURITY CONCERN: ${issue.type}]`,
    }));

    // Merge with v1 security findings if any
    const allFindings = [
      ...(v1Security?.findings || []),
      ...critiqueFindings,
    ];

    // Create a synthetic redacted text message
    const redactedText = result.ir.metadata?.original_text || "";
    const securityMessage = hasCritiqueRejection
      ? `\n\n[SECURITY NOTICE: This request was flagged by the critique layer. Verdict: ${critiqueVerdict}. Feedback: ${critique?.feedback || "N/A"}]`
      : `\n\n[SECURITY NOTICE: Critical security diagnostics were detected.]`;

    return {
      is_safe: false,
      findings: allFindings,
      redacted_text: redactedText + securityMessage,
    };
  }

  return v1Security;
}

export function useCompiler() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CompileResponse | null>(null);
  const [status, setStatus] = useState("Ready");
  const [securityFindings, setSecurityFindings] = useState<SecurityFinding[]>([]);
  const [redactedText, setRedactedText] = useState("");
  const [pendingText, setPendingText] = useState("");
  const [lastError, setLastError] = useState<unknown>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const lastCallRef = useRef<{ text: string; mode: CompileMode } | null>(null);

  const runCompile = useCallback(async (text: string, mode: CompileMode) => {
    if (!text.trim()) {
      return;
    }

    // Abort any in-flight request
    controllerRef.current?.abort();

    const controller = new AbortController();
    controllerRef.current = controller;
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    lastCallRef.current = { text, mode };
    setLastError(null);
    setResult(null);
    setLoading(true);
    setStatus("Generating...");

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
        controller.signal,
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
      // Ignore aborts from a superseded request
      if (controller.signal.aborted && controllerRef.current !== controller) {
        return;
      }
      console.error("Compile request failed", {
        mode,
        textLength: text.length,
        aborted: controller.signal.aborted,
      });
      setLastError(error);
      showError(error);
      setStatus("Error");
    } finally {
      window.clearTimeout(timeoutId);
      if (controllerRef.current === controller) {
        setLoading(false);
      }
    }
  }, []);

  const retry = useCallback(async () => {
    if (lastCallRef.current) {
      await runCompile(lastCallRef.current.text, lastCallRef.current.mode);
    }
  }, [runCompile]);

  const resolveSecurityDecision = useCallback(
    async (useRedacted: boolean, mode: CompileMode) => {
      const textToCompile = useRedacted ? redactedText : pendingText;
      if (!textToCompile.trim()) {
        return;
      }

      setSecurityFindings([]);
      await runCompile(textToCompile, mode);
    },
    [pendingText, redactedText, runCompile],
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
    lastError,
    securityFindings,
    redactedText,
    runCompile,
    retry,
    resolveSecurityDecision,
    cancelSecurityReview,
  };
}
