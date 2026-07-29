"use client";

import type { ContextSuggestion } from "../../lib/api/types";
import { useContextManager, type ContextManagerState } from "../hooks/useContextManager";
import ContextSuggestions from "./context/ContextSuggestions";
import FileUploadZone from "./context/FileUploadZone";
import RagSearchPanel from "./context/RagSearchPanel";

type ContextManagerProps = {
    onInsertContext: (text: string) => void;
    suggestions?: ContextSuggestion[];
    /** Parent-owned hook state so banners and generate requests share one session scope. */
    context?: ContextManagerState;
};

function getConnectionBadge(isConnected: boolean | null): { label: string; tone: string } {
    if (isConnected === true) return { label: "Backend OK", tone: "text-zinc-300 bg-zinc-800/80" };
    if (isConnected === false) return { label: "Connection Issue", tone: "text-amber-300 bg-amber-500/10" };
    return { label: "Checking", tone: "text-zinc-400 bg-zinc-800/80" };
}

function getStatusTone(status: string): string {
    if (status.startsWith("Indexed") || status.startsWith("Detached")) return "bg-green-500/10 text-green-400";
    if (status.startsWith("Error") || status.startsWith("Search failed")) return "bg-red-500/10 text-red-400";
    if (status.startsWith("Stats unavailable") || status.startsWith("Could not reach") || status.startsWith("Backend health check failed")) {
        return "bg-amber-500/10 text-amber-300";
    }
    return "bg-zinc-800/50 text-zinc-400";
}

function contextSourceLabel(source: ContextManagerState["contextSource"]): string {
    if (source === "session") return "This session (upload/ingest)";
    if (source === "library") return "Persisted local library";
    return "None";
}

export default function ContextManager({ onInsertContext, suggestions = [], context }: ContextManagerProps) {
    const fallback = useContextManager();
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
        contextAttached,
        contextSource,
        attachContext,
        detachContext,
        uploadFiles,
        ingestPath,
        runSearch,
    } = context ?? fallback;

    const connectionBadge = getConnectionBadge(isConnected);
    const hasDocs = (indexStats?.docs ?? 0) > 0;
    const libraryAvailable = hasDocs && !contextAttached;

    return (
        <div className="mt-2 flex shrink-0 flex-col gap-3 border-t border-white/5 pt-3">
            <h3 className="flex items-center justify-between gap-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                <div className="flex items-center gap-2">
                    <span>Context Manager</span>
                    <span
                        title="Retrieval-Augmented Generation — fancy name for: the AI can quote from files you upload."
                        className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[9px] cursor-help"
                    >
                        RAG
                    </span>
                </div>
                <span className={`text-[9px] px-1.5 py-0.5 rounded ${connectionBadge.tone}`}>
                    {connectionBadge.label}
                </span>
            </h3>

            {!hasDocs && (
                <p className="text-[11px] leading-relaxed text-zinc-400 normal-case">
                    Upload your own docs (README, design notes, examples). The AI will quote from them when it writes your prompt.
                </p>
            )}

            <ContextSuggestions suggestions={suggestions} onInsertContext={onInsertContext} />

            {indexStats && indexStats.docs > 0 && (
                <div className="flex flex-col gap-2 rounded-lg border border-white/5 bg-white/5 px-3 py-2">
                    <div className="grid grid-cols-3 gap-2">
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
                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-2">
                        <div className="text-[10px] text-zinc-400 normal-case">
                            {contextAttached ? (
                                <>
                                    <span className="font-semibold text-emerald-300">Active for this request</span>
                                    <span className="text-zinc-500"> · {contextSourceLabel(contextSource)}</span>
                                    <span className="text-zinc-500"> · {indexStats.docs} {indexStats.docs === 1 ? "doc" : "docs"}</span>
                                </>
                            ) : (
                                <>
                                    <span className="font-semibold text-zinc-300">Library available</span>
                                    <span className="text-zinc-500"> · not attached to this session</span>
                                </>
                            )}
                        </div>
                        {contextAttached ? (
                            <button
                                type="button"
                                onClick={detachContext}
                                className="rounded-md border border-white/10 bg-black/30 px-2 py-1 text-[10px] font-medium text-zinc-300 transition-colors hover:bg-zinc-800 hover:text-white"
                            >
                                Detach context
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={() => attachContext("library")}
                                className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-medium text-emerald-200 transition-colors hover:bg-emerald-500/20"
                            >
                                Use library for this session
                            </button>
                        )}
                    </div>
                    {libraryAvailable && (
                        <p className="text-[10px] leading-relaxed text-zinc-500 normal-case">
                            Prior-session documents stay indexed but are not sent to generators until you attach them.
                        </p>
                    )}
                </div>
            )}

            <FileUploadZone ingesting={ingesting} uploadProgress={uploadProgress} onUploadFiles={uploadFiles} />

            {status && (
                <div aria-live="polite" className={`rounded-lg px-2.5 py-2 text-[10px] leading-relaxed border ${getStatusTone(status)}`}>
                    <div className="font-semibold mb-0.5 flex items-center gap-1.5">
                        {status.toLowerCase().includes("error") || status.toLowerCase().includes("failed") ? (
                            <><span>⚠️</span> Ingestion Alert</>
                        ) : (
                            <><span>ℹ️</span> Status</>
                        )}
                    </div>
                    <div>{status}</div>
                    {(status.includes("Permission") || status.includes("denied") || status.includes("ACL")) && (
                        <div className="mt-1.5 pt-1.5 border-t border-red-500/10 text-[9px] text-zinc-400">
                            Tip: Check Windows file permissions or try dragging & dropping the file into the upload zone above instead.
                        </div>
                    )}
                    {(status.includes("not allowed") || status.includes("security") || status.includes("root")) && (
                        <div className="mt-1.5 pt-1.5 border-t border-amber-500/10 text-[9px] text-zinc-400 font-mono">
                            Allowed roots: CWD & promptc_uploads. Use absolute paths inside the workspace.
                        </div>
                    )}
                </div>
            )}

            <div className="flex flex-col gap-2">
                <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-semibold">
                    …or paste a path to a local file/folder
                </p>
                <label htmlFor="file-path" className="sr-only">Path to file or folder</label>
                <input
                    id="file-path"
                    type="text"
                    aria-label="Path to file or folder..."
                    className="w-full rounded-lg border border-white/5 bg-black/30 p-2 text-xs font-mono transition-colors placeholder-zinc-600 focus:border-blue-500/30 focus:outline-none"
                    placeholder="e.g. ./docs or C:\Users\me\notes.md"
                    value={filePath}
                    onChange={(e) => setFilePath(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter" && !ingesting && filePath) {
                            void ingestPath(filePath);
                        }
                    }}
                />
                <button
                    type="button"
                    onClick={() => void ingestPath(filePath)}
                    disabled={ingesting || !filePath}
                    aria-busy={ingesting}
                    title={!filePath ? "Enter a file path first to ingest" : "Ingest Path"}
                    className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/5 bg-zinc-800/50 py-2 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700/50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {ingesting ? <span className="animate-pulse">Indexing...</span> : "Ingest Path"}
                </button>
            </div>

            {hasDocs ? (
                <RagSearchPanel
                    query={query}
                    setQuery={setQuery}
                    searching={searching}
                    results={results}
                    onRunSearch={() => void runSearch()}
                    onInsertContext={onInsertContext}
                />
            ) : (
                <div className="rounded-lg border border-dashed border-white/10 bg-black/20 px-3 py-2 text-[10px] text-zinc-500 normal-case">
                    Upload something above first, then you can search through it here.
                </div>
            )}
        </div>
    );
}
