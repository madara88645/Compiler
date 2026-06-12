"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch, describeRequestError } from "../../config";
import {
  fetchRagStats,
  ingestContextPath,
  searchContext,
  uploadContextFile,
} from "../../lib/api/promptc";
import type { RagSearchResult, RagStats } from "../../lib/api/types";

export type UploadProgress = {
  completed: number;
  currentFile: string | null;
  total: number;
};

type FileWithRelativePath = File & {
  webkitRelativePath?: string;
};

const EMPTY_FILE_MESSAGE = "This file is empty. Please upload a file with content.";

function toUserMessage(error: unknown): string {
  return describeRequestError(error, {
    network: "The service is temporarily unavailable or still waking up. Please retry in a few seconds.",
  });
}

async function readResponseDetail(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (payload && typeof payload === "object") {
      const detail = (payload as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        return detail.trim();
      }
    }
  } catch {
    // Ignore body parsing failures and fall back to generic copy.
  }

  return "The service is temporarily unavailable or still waking up. Please retry in a few seconds.";
}

function getUploadRelativePath(file: File): string {
  const relativePath = (file as FileWithRelativePath).webkitRelativePath?.trim();
  return relativePath ? relativePath.replace(/\\/g, "/") : file.name;
}

export function useContextManager() {
  const [ingesting, setIngesting] = useState(false);
  const [searching, setSearching] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RagSearchResult[]>([]);
  const [filePath, setFilePath] = useState("");
  const [status, setStatus] = useState("");
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [indexStats, setIndexStats] = useState<RagStats | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

  const refreshStats = useCallback(async () => {
    const stats = await fetchRagStats();
    setIndexStats(stats);
  }, []);

  const checkConnection = useCallback(async () => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 2_000);

    try {
      const response = await apiFetch("/health", { signal: controller.signal });

      if (!response.ok) {
        setIsConnected(false);
        setStatus(await readResponseDetail(response));
        return;
      }

      setIsConnected(true);
      try {
        await refreshStats();
      } catch (error: unknown) {
        setStatus(`Stats unavailable: ${toUserMessage(error)}`);
      }
    } catch (error: unknown) {
      setIsConnected(false);
      setStatus(toUserMessage(error));
    } finally {
      window.clearTimeout(timeoutId);
    }
  }, [refreshStats]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void checkConnection();
  }, [checkConnection]);

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        return;
      }

      // Pre-validate: never send an empty file to the server. This avoids a raw
      // "API Error: 422" and keeps stats untouched after a failed empty upload.
      const validFiles = files.filter((file) => file.size > 0);
      const emptyCount = files.length - validFiles.length;

      if (validFiles.length === 0) {
        setStatus(`Error: ${EMPTY_FILE_MESSAGE}`);
        setUploadProgress(null);
        return;
      }

      setIngesting(true);
      setStatus(`Uploading ${validFiles.length} file(s)...`);
      setUploadProgress({
        completed: 0,
        currentFile: validFiles[0]?.name ?? null,
        total: validFiles.length,
      });

      let totalChunks = 0;
      let successCount = 0;

      try {
        for (const [index, file] of validFiles.entries()) {
          setUploadProgress({
            completed: successCount,
            currentFile: file.name,
            total: validFiles.length,
          });
          setStatus(`Uploading ${index + 1}/${validFiles.length}: ${file.name}`);

          const content = await file.text();
          const response = await uploadContextFile({
            filename: file.name,
            relative_path: getUploadRelativePath(file),
            content,
          });

          if (response.success) {
            totalChunks += response.total_chunks;
            successCount += 1;
            setUploadProgress({
              completed: successCount,
              currentFile: file.name,
              total: validFiles.length,
            });
          }
        }

        setIsConnected(true);
        const skippedNote = emptyCount > 0 ? ` — skipped ${emptyCount} empty file(s)` : "";
        setStatus(`Indexed ${successCount}/${validFiles.length} files (${totalChunks} chunks)${skippedNote}`);
        await refreshStats();
      } catch (error: unknown) {
        setStatus(`Error: ${toUserMessage(error)}`);
      } finally {
        setIngesting(false);
        setUploadProgress(null);
      }
    },
    [refreshStats],
  );

  const ingestPath = useCallback(
    async (path: string) => {
      if (!path.trim()) {
        return;
      }

      setIngesting(true);
      setStatus("Ingesting...");

      try {
        const response = await ingestContextPath({ paths: [path] });
        setIsConnected(true);
        setStatus(`Indexed ${response.ingested_docs} files (${response.total_chunks} chunks)`);
        setFilePath("");
        await refreshStats();
      } catch (error: unknown) {
        setStatus(`Error: ${toUserMessage(error)}`);
      } finally {
        setIngesting(false);
      }
    },
    [refreshStats],
  );

  const runSearch = useCallback(async () => {
    if (!query.trim()) {
      return;
    }

    setSearching(true);
    setResults([]);

    try {
      const response = await searchContext({ query: query.trim(), limit: 5 });
      setResults(response);
      setStatus("");
      setIsConnected(true);
    } catch (error: unknown) {
      setStatus(`Search failed: ${toUserMessage(error)}`);
    } finally {
      setSearching(false);
    }
  }, [query]);

  return {
    ingesting,
    searching,
    query,
    setQuery,
    results,
    filePath,
    setFilePath,
    status,
    setStatus,
    isConnected,
    indexStats,
    uploadProgress,
    checkConnection,
    uploadFiles,
    ingestPath,
    runSearch,
  };
}
