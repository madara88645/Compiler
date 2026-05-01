import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useContextManager } from "./useContextManager";
import { apiFetch } from "../../config";
import {
  fetchRagStats,
  ingestContextPath,
  searchContext,
  uploadContextFile,
} from "../../lib/api/promptc";

vi.mock("../../config", async () => {
  const actual = await vi.importActual<typeof import("../../config")>("../../config");
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

vi.mock("../../lib/api/promptc", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api/promptc")>("../../lib/api/promptc");
  return {
    ...actual,
    fetchRagStats: vi.fn(),
    ingestContextPath: vi.fn(),
    searchContext: vi.fn(),
    uploadContextFile: vi.fn(),
  };
});

const apiFetchMock = vi.mocked(apiFetch);
const fetchRagStatsMock = vi.mocked(fetchRagStats);
const ingestContextPathMock = vi.mocked(ingestContextPath);
const searchContextMock = vi.mocked(searchContext);
const uploadContextFileMock = vi.mocked(uploadContextFile);

describe("useContextManager", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    fetchRagStatsMock.mockReset();
    ingestContextPathMock.mockReset();
    searchContextMock.mockReset();
    uploadContextFileMock.mockReset();

    apiFetchMock.mockResolvedValue({ ok: true } as Response);
    fetchRagStatsMock.mockResolvedValue({ docs: 0, chunks: 0, total_bytes: 0 });
  });

  it("clears a stale error status after a successful search", async () => {
    searchContextMock.mockResolvedValue([
      {
        path: "src/compiler.ts",
        snippet: "Compile request flow",
        score: 0.91,
      },
    ]);

    const { result } = renderHook(() => useContextManager());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    act(() => {
      result.current.setStatus("Search failed: timeout");
      result.current.setQuery(" compiler ");
    });

    await act(async () => {
      await result.current.runSearch();
    });

    await waitFor(() => {
      expect(result.current.results).toHaveLength(1);
    });

    expect(result.current.status).toBe("");
    expect(searchContextMock).toHaveBeenCalledWith({ query: "compiler", limit: 5 });
  });

  it("surfaces a stats warning when health succeeds but stats loading fails", async () => {
    fetchRagStatsMock.mockRejectedValueOnce(new Error("stats offline"));

    const { result } = renderHook(() => useContextManager());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.status).toBe("Stats unavailable: stats offline");
    });
  });

  it("skips searches for whitespace-only queries", async () => {
    const { result } = renderHook(() => useContextManager());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    act(() => {
      result.current.setQuery("   ");
    });

    await act(async () => {
      await result.current.runSearch();
    });

    expect(searchContextMock).not.toHaveBeenCalled();
    expect(result.current.searching).toBe(false);
  });

  it("tracks upload progress and refreshes stats after successful uploads", async () => {
    const file = new File(["hello world"], "notes.md", { type: "text/markdown" });

    let resolveUpload: ((value: {
      ingested_docs: number;
      total_chunks: number;
      elapsed_ms: number;
      filename: string;
      success: boolean;
      num_chunks: number;
      message: string;
    }) => void) | null = null;

    uploadContextFileMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve;
        }),
    );

    const { result } = renderHook(() => useContextManager());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    fetchRagStatsMock.mockClear();

    let uploadPromise!: Promise<void>;
    act(() => {
      uploadPromise = result.current.uploadFiles([file]);
    });

    await waitFor(() => {
      expect(result.current.uploadProgress).toMatchObject({
        completed: 0,
        currentFile: "notes.md",
        total: 1,
      });
    });

    resolveUpload?.({
      ingested_docs: 1,
      total_chunks: 3,
      elapsed_ms: 12,
      filename: "notes.md",
      success: true,
      num_chunks: 3,
      message: "Indexed notes.md into the RAG index.",
    });

    await act(async () => {
      await uploadPromise;
    });

    await waitFor(() => {
      expect(result.current.uploadProgress).toBeNull();
    });

    expect(result.current.status).toBe("Indexed 1/1 files (3 chunks)");
    expect(fetchRagStatsMock).toHaveBeenCalledTimes(1);
  });

  it("resets the indexed path after a successful manual ingest", async () => {
    ingestContextPathMock.mockResolvedValueOnce({
      ingested_docs: 2,
      total_chunks: 7,
      elapsed_ms: 15,
    });

    const { result } = renderHook(() => useContextManager());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    fetchRagStatsMock.mockClear();

    act(() => {
      result.current.setFilePath("docs/architecture");
    });

    await act(async () => {
      await result.current.ingestPath("docs/architecture");
    });

    expect(ingestContextPathMock).toHaveBeenCalledWith({ paths: ["docs/architecture"] });
    expect(result.current.filePath).toBe("");
    expect(result.current.status).toBe("Indexed 2 files (7 chunks)");
    expect(fetchRagStatsMock).toHaveBeenCalledTimes(1);
  });
});
