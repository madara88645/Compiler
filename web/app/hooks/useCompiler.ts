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

function extractSecurityMetadata(
    result: CompileResponse,
): SecurityMetadata | undefined {
    return result.ir.metadata?.security;
}

export function useCompiler() {
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<CompileResponse | null>(null);
    const [status, setStatus] = useState("Ready");
    const [securityFindings, setSecurityFindings] = useState<SecurityFinding[]>(
        [],
    );
    const [redactedText, setRedactedText] = useState("");
    const [pendingText, setPendingText] = useState("");
    const [lastError, setLastError] = useState<unknown>(null);

    const controllerRef = useRef<AbortController | null>(null);
    const lastCallRef = useRef<{ text: string; mode: CompileMode } | null>(
        null,
    );

    const runCompile = useCallback(async (text: string, mode: CompileMode) => {
        if (!text.trim()) {
            return;
        }

        // Abort any in-flight request
        controllerRef.current?.abort();

        const controller = new AbortController();
        controllerRef.current = controller;
        const timeoutId = window.setTimeout(
            () => controller.abort(),
            REQUEST_TIMEOUT_MS,
        );

        lastCallRef.current = { text, mode };
        setLastError(null);
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
            if (
                controller.signal.aborted &&
                controllerRef.current !== controller
            ) {
                return;
            }
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
            await runCompile(
                lastCallRef.current.text,
                lastCallRef.current.mode,
            );
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
