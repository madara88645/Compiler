"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { formatSearchResultForPrompt, formatSearchScore } from "../../lib/api/promptc";
import type { ContextSuggestion } from "../../lib/api/types";
import { useContextManager } from "../hooks/useContextManager";

type ContextManagerProps = {
    onInsertContext: (text: string) => void;
    suggestions?: ContextSuggestion[];
};

function getStatusTone(status: string): string {
    if (status.startsWith("Indexed")) {
        return "bg-green-500/10 text-green-400";
    }

    if (status.startsWith("Error") || status.startsWith("Search failed")) {
        return "bg-red-500/10 text-red-400";
    }

    if (
        status.startsWith("Stats unavailable") ||
        status.startsWith("Could not reach") ||
        status.startsWith("Backend health check failed")
    ) {
        return "bg-amber-500/10 text-amber-300";
    }

    return "bg-zinc-800/50 text-zinc-400";
}

function getConnectionBadge(isConnected: boolean | null): { label: string; tone: string } {
    if (isConnected === true) {
        return {
            label: "Connected",
            tone: "text-green-400 bg-green-500/10",
        };
    }

    if (isConnected === false) {
        return {
            label: "Connection Issue",
            tone: "text-amber-300 bg-amber-500/10",
        };
    }

    return {
        label: "Checking",
        tone: "text-zinc-400 bg-zinc-800/80",
    };
}

export default function ContextManager({ onInsertContext, suggestions = [] }: ContextManagerProps) {
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const directoryInputRef = useRef<HTMLInputElement>(null);
    const {
        ingesting,
        searching,
        query,
        setQuery,
        results,
        filePath,
        setFilePath,
        status,
        isConnected,
        indexStats,
        uploadProgress,
        uploadFiles,
        ingestPath,
        runSearch,
    } = useContextManager();
    const connectionBadge = getConnectionBadge(isConnected);
    const uploadPercent = uploadProgress
        ? Math.max(
              8,
              Math.min(
                  100,
                  Math.round(
                      ((uploadProgress.completed + (uploadProgress.currentFile ? 0.45 : 0)) / uploadProgress.total) * 100,
                  ),
              ),
          )
        : 0;
    const currentUploadStep = uploadProgress
        ? Math.min(uploadProgress.total, uploadProgress.completed + (uploadProgress.currentFile ? 1 : 0))
        : 0;

    const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);

        const files = Array.from(e.dataTransfer.files);
        if (files.length === 0) {
            return;
        }

        await uploadFiles(files);
    };

    const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) {
            return;
        }

        await uploadFiles(Array.from(files));
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const handleDirectorySelect = async (e: ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) {
            return;
        }

        await uploadFiles(Array.from(files));
        if (directoryInputRef.current) {
            directoryInputRef.current.value = "";
        }
    };

    return (
        <div className="flex flex-col gap-4 border-t border-white/5 pt-4 mt-4">
            <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <span>Context Manager</span>
                    <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[9px]">RAG</span>
                </div>
                <span className={`text-[9px] px-1.5 py-0.5 rounded ${connectionBadge.tone}`}>
                    {connectionBadge.label}
                </span>
            </h3>

            {suggestions.length > 0 && (
                <div className="flex flex-col gap-2 mb-4 animate-fade-in">
                    <span className="text-[9px] text-blue-400 font-bold uppercase tracking-widest px-1">Suggested Files</span>
                    <div className="flex flex-wrap gap-2">
                        {suggestions.map((suggestion) => (
                            <button
                                key={suggestion.path}
                                onClick={() => onInsertContext(`[File: ${suggestion.name}]\n(Reason: ${suggestion.reason})`)}
                                className="group flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 hover:border-blue-500/40 rounded-full transition-all text-left"
                                title={`Add ${suggestion.path} to context`}
                            >
                                <span className="text-[10px] text-blue-300 font-mono">{suggestion.name}</span>
                                <span className="text-[9px] text-blue-400/60 group-hover:text-blue-400 opacity-60 group-hover:opacity-100 transition-opacity">
                                    +
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {indexStats && indexStats.docs > 0 && (
                <div className="flex gap-4 px-3 py-2 bg-white/5 rounded-lg border border-white/5">
                    <div className="flex flex-col">
                        <span className="text-[9px] text-zinc-500 uppercase">Documents</span>
                        <span className="text-xs font-mono text-zinc-300">{indexStats.docs}</span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[9px] text-zinc-500 uppercase">Chunks</span>
                        <span className="text-xs font-mono text-zinc-300">{indexStats.chunks}</span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[9px] text-zinc-500 uppercase">Size</span>
                        <span className="text-xs font-mono text-zinc-300">{(indexStats.total_bytes / 1024).toFixed(1)} KB</span>
                    </div>
                </div>
            )}

            <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                className={`
                    relative flex flex-col items-center justify-center gap-2 p-4
                    border-2 border-dashed rounded-xl
                    transition-all duration-200
                    ${isDragging ? "border-blue-500 bg-blue-500/10 scale-[1.02]" : "border-white/10 bg-white/[0.02]"}
                    ${ingesting ? "pointer-events-none opacity-50" : ""}
                `}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    onChange={handleFileSelect}
                    className="hidden"
                />

                <input
                    ref={directoryInputRef}
                    type="file"
                    multiple
                    // @ts-expect-error - webkitdirectory is not in standard types but supported by browsers
                    webkitdirectory=""
                    directory=""
                    onChange={handleDirectorySelect}
                    className="hidden"
                />

                {ingesting ? (
                    <div className="w-full max-w-sm rounded-2xl border border-cyan-400/20 bg-cyan-500/[0.08] p-4 shadow-[0_0_40px_rgba(34,211,238,0.08)]">
                        <div className="flex items-start gap-3">
                            <span className="mt-1 relative flex h-3 w-3 shrink-0">
                                <span className="absolute inline-flex h-full w-full rounded-full bg-cyan-300/30 animate-ping" />
                                <span className="relative inline-flex h-3 w-3 rounded-full bg-cyan-300" />
                            </span>
                            <div className="min-w-0 flex-1">
                                <div className="flex items-center justify-between gap-3">
                                    <span className="text-sm font-medium text-cyan-100">Uploading context</span>
                                    {uploadProgress && (
                                        <span className="text-[10px] font-mono text-cyan-200/80">
                                            {currentUploadStep}/{uploadProgress.total}
                                        </span>
                                    )}
                                </div>
                                <p className="mt-1 text-[11px] leading-relaxed text-cyan-100/70">
                                    {uploadProgress?.currentFile ? uploadProgress.currentFile : "Preparing files..."}
                                </p>
                                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/20">
                                    <div
                                        className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-400 transition-[width] duration-500"
                                        style={{ width: `${uploadPercent}%` }}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <>
                        <div className={`text-2xl ${isDragging ? "scale-110" : ""} transition-transform`}>
                            Files
                        </div>
                        <div className="flex gap-2">
                            <button
                                onClick={() => fileInputRef.current?.click()}
                                className="text-xs text-blue-400 font-medium hover:text-blue-300 transition-colors"
                            >
                                Upload Files
                            </button>
                            <span className="text-xs text-zinc-500">|</span>
                            <button
                                onClick={() => directoryInputRef.current?.click()}
                                className="text-xs text-blue-400 font-medium hover:text-blue-300 transition-colors"
                            >
                                Upload Folder
                            </button>
                        </div>
                        <div className="text-[10px] text-zinc-600 mt-1">
                            Or drag and drop project context
                        </div>
                    </>
                )}
            </div>

            {status && (
                <div aria-live="polite" className={`text-[10px] px-2 py-1.5 rounded-lg ${getStatusTone(status)}`}>
                    {status}
                </div>
            )}

            <details className="group">
                <summary className="text-[10px] text-zinc-600 cursor-pointer hover:text-zinc-400 transition-colors">
                    Advanced: Index by path
                </summary>
                <div className="flex flex-col gap-2 mt-2 pl-2 border-l border-white/5">
                    <input
                        type="text"
                        className="w-full bg-black/30 p-2.5 rounded-lg text-xs border border-white/5 focus:border-blue-500/30 focus:outline-none transition-colors placeholder-zinc-600 font-mono"
                        placeholder="Path to file or folder..."
                        value={filePath}
                        onChange={(e) => setFilePath(e.target.value)}
                    />
                    <button
                        onClick={() => void ingestPath(filePath)}
                        disabled={ingesting || !filePath}
                        className="w-full py-2 bg-zinc-800/50 hover:bg-zinc-700/50 text-xs font-medium text-zinc-300 rounded-lg disabled:opacity-50 transition-colors border border-white/5 flex items-center justify-center gap-2"
                    >
                        {ingesting ? <span className="animate-pulse">Indexing...</span> : "Ingest Path"}
                    </button>
                </div>
            </details>

            <div className="flex flex-col gap-2">
                <div className="flex gap-2">
                    <input
                        type="text"
                        className="flex-1 bg-black/30 p-2.5 rounded-lg text-xs border border-white/5 focus:border-blue-500/30 focus:outline-none transition-colors placeholder-zinc-600 font-mono"
                        placeholder="Search context..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && void runSearch()}
                    />
                    <button
                        onClick={() => void runSearch()}
                        disabled={searching || !query}
                        className="px-3 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg text-xs hover:bg-blue-500/20 transition-all font-medium"
                    >
                        Search
                    </button>
                </div>

                <div className="flex flex-col gap-2 max-h-[180px] overflow-y-auto pr-1 custom-scrollbar">
                    {!searching && query && results.length === 0 && (
                        <div className="text-[10px] text-zinc-500 text-center py-4 bg-white/[0.02] rounded-lg border border-dashed border-white/5">
                            No results found for &quot;{query}&quot;
                        </div>
                    )}

                    {results.map((result) => (
                        <div key={result.path} className="group flex flex-col gap-1.5 p-3 bg-white/5 rounded-xl border border-white/5 hover:border-white/10 transition-all hover:bg-white/[0.07]">
                            <div className="flex justify-between items-center gap-2">
                                <span className="text-[10px] text-zinc-500 font-mono truncate max-w-[180px] bg-black/20 px-1.5 py-0.5 rounded">{result.path}</span>
                                <span className="text-[10px] text-green-400/80 font-mono bg-green-500/10 px-1.5 py-0.5 rounded">{formatSearchScore(result)}</span>
                            </div>
                            <div className="text-xs text-zinc-300 line-clamp-3 leading-relaxed opacity-80 group-hover:opacity-100">
                                {result.snippet}
                            </div>
                            <button
                                onClick={() => onInsertContext(formatSearchResultForPrompt(result))}
                                className="mt-1 text-[10px] text-blue-300 hover:text-blue-200 text-left opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500 rounded transition-all flex items-center gap-1 font-medium"
                            >
                                <span>+</span> Insert into Prompt
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
