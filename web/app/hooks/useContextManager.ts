"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, apiFetch } from "../../config";
import {
  fetchRagStats,
  ingestContextPath,
  searchContext,
  uploadContextFile,
} from "../../lib/api/promptc";
import type { RagSearchResult, RagStats } from "../../lib/api/types";

function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Connection failed.";
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

  const refreshStats = useCallback(async () => {
    const stats = await fetchRagStats();
    setIndexStats(stats);
  }, []);

  const checkConnection = useCallback(async () => {
    try {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 2_000);

      const response = await apiFetch("/health", { signal: controller.signal });
      window.clearTimeout(timeoutId);

      if (!response.ok) {
        setIsConnected(false);
        return;
      }

      setIsConnected(true);
      try {
        await refreshStats();
      } catch (error: unknown) {
        setStatus(`Stats unavailable: ${toUserMessage(error)}`);
      }
    } catch {
      setIsConnected(false);
    }
  }, [refreshStats]);

  useEffect(() => {
    void checkConnection();
  }, [checkConnection]);

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        return;
      }

      setIngesting(true);
      setStatus(`Uploading ${files.length} file(s)...`);

      let totalChunks = 0;
      let successCount = 0;

      try {
        for (const file of files) {
          const content = await file.text();
          const response = await uploadContextFile({
            filename: file.name,
            content,
          });

          if (response.success) {
            totalChunks += response.total_chunks;
            successCount += 1;
          }
        }

        setStatus(`Indexed ${successCount}/${files.length} files (${totalChunks} chunks)`);
        await refreshStats();
      } catch (error: unknown) {
        setStatus(`Error: ${toUserMessage(error)}`);
      } finally {
        setIngesting(false);
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
    checkConnection,
    uploadFiles,
    ingestPath,
    runSearch,
  };
}
