"use client";

import type { ContextSuggestion } from "../../lib/api/types";
import { useContextManager } from "../hooks/useContextManager";
import ContextSuggestions from "./context/ContextSuggestions";
import FileUploadZone from "./context/FileUploadZone";
import RagSearchPanel from "./context/RagSearchPanel";

type ContextManagerProps = {
    onInsertContext: (text: string) => void;
    suggestions?: ContextSuggestion[];
};

function getConnectionBadge(isConnected: boolean | null): { label: string; tone: string } {
    if (isConnected === true) return { label: "Connected", tone: "text-green-400 bg-green-500/10" };
    if (isConnected === false) return { label: "Connection Issue", tone: "text-amber-300 bg-amber-500/10" };
    return { label: "Checking", tone: "text-zinc-400 bg-zinc-800/80" };
}

function getStatusTone(status: string): string {
    if (status.startsWith("Indexed")) return "bg-green-500/10 text-green-400";
    if (status.startsWith("Error") || status.startsWith("Search failed")) return "bg-red-500/10 text-red-400";
    if (status.startsWith("Stats unavailable") || status.startsWith("Could not reach") || status.startsWith("Backend health check failed")) {
        return "bg-amber-500/10 text-amber-300";
    }
    return "bg-zinc-800/50 text-zinc-400";
}

export default function ContextManager({ onInsertContext, suggestions = [] }: ContextManagerProps) {
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

            <ContextSuggestions suggestions={suggestions} onInsertContext={onInsertContext} />

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

            <FileUploadZone ingesting={ingesting} uploadProgress={uploadProgress} onUploadFiles={uploadFiles} />

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
                        aria-label="Path to file or folder..."
                        className="w-full bg-black/30 p-2.5 rounded-lg text-xs border border-white/5 focus:border-blue-500/30 focus:outline-none transition-colors placeholder-zinc-600 font-mono"
                        placeholder="Path to file or folder..."
                        value={filePath}
                        onChange={(e) => setFilePath(e.target.value)}
                    />
                    <button
                        type="button"
                        onClick={() => void ingestPath(filePath)}
                        disabled={ingesting || !filePath}
                        className="w-full py-2 bg-zinc-800/50 hover:bg-zinc-700/50 text-xs font-medium text-zinc-300 rounded-lg disabled:opacity-50 transition-colors border border-white/5 flex items-center justify-center gap-2"
                    >
                        {ingesting ? <span className="animate-pulse">Indexing...</span> : "Ingest Path"}
                    </button>
                </div>
            </details>

            <RagSearchPanel
                query={query}
                setQuery={setQuery}
                searching={searching}
                results={results}
                onRunSearch={() => void runSearch()}
                onInsertContext={onInsertContext}
            />
        </div>
    );
}
