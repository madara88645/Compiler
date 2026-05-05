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

function toUserMessage(error: unknown): string {
  return describeRequestError(error, {
    network: "Could not reach the backend. Check the API URL or make sure the server is running.",
  });
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
        setStatus("Backend health check failed. Verify the API URL and server status.");
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

      setIngesting(true);
      setStatus(`Uploading ${files.length} file(s)...`);
      setUploadProgress({
        completed: 0,
        currentFile: files[0]?.name ?? null,
        total: files.length,
      });

      let totalChunks = 0;
      let successCount = 0;

      try {
        for (const [index, file] of files.entries()) {
          setUploadProgress({
            completed: successCount,
            currentFile: file.name,
            total: files.length,
          });
          setStatus(`Uploading ${index + 1}/${files.length}: ${file.name}`);

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
              total: files.length,
            });
          }
        }

        setIsConnected(true);
        setStatus(`Indexed ${successCount}/${files.length} files (${totalChunks} chunks)`);
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
