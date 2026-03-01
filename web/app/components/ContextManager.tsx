"use client";

import { useState, useRef, DragEvent, useEffect } from "react";
import { API_BASE } from "@/config";

type SearchResult = {
    content: string;
    source: string;
    score: number;
};

type ContextManagerProps = {
    onInsertContext: (text: string) => void;
    suggestions?: { path: string; name: string; reason: string }[];
};

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB per file
const ALLOWED_EXTENSIONS = /\.(txt|md|py|js|ts|tsx|jsx|json|yaml|yml|toml|ini|cfg|conf|sh|bash|zsh|html|css|scss|rs|go|java|cpp|c|h|cs|rb|php|swift|kt|sql|xml|env|gitignore|dockerfile)$/i;

export default function ContextManager({ onInsertContext, suggestions = [] }: ContextManagerProps) {
    const [ingesting, setIngesting] = useState(false);
    const [searching, setSearching] = useState(false);
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<SearchResult[]>([]);
    const [filePath, setFilePath] = useState("");
    const [status, setStatus] = useState("");
    const [isDragging, setIsDragging] = useState(false);
    const [isConnected, setIsConnected] = useState<boolean | null>(null);
    const [indexStats, setIndexStats] = useState<any>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Check connectivity on mount
    useEffect(() => {
        checkConnection();
    }, []);

    const checkConnection = async () => {
        try {
            // Use a short timeout to prevent hanging if backend is unresponsive
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2000);

            const res = await fetch(`${API_BASE}/health`, { signal: controller.signal });
            clearTimeout(timeoutId);

            if (res.ok) {
                setIsConnected(true);
                fetchStats();
            } else {
                setIsConnected(false);
            }
        } catch (e) {
            setIsConnected(false);
            // Silent error for connection checks to avoid console spam
        }
    };

    const fetchStats = async () => {
        try {
            const res = await fetch(`${API_BASE}/rag/stats`);
            const data = await res.json();
            setIndexStats(data);
        } catch (e) {
            console.error("Stats fetch failed:", e);
        }
    };

    // Handle file drop
    const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);

        const files = Array.from(e.dataTransfer.files);
        if (files.length === 0) return;

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

    // Handle file input change
    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;
        await uploadFiles(Array.from(files));
    };

    // Ref for directory input
    const directoryInputRef = useRef<HTMLInputElement>(null);

    // Handle directory input change
    const handleDirectorySelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;
        await uploadFiles(Array.from(files));
    };

    // Upload files to the backend
    const uploadFiles = async (files: File[]) => {
        setIngesting(true);
        setStatus(`Uploading ${files.length} file(s)...`);

        let totalChunks = 0;
        let successCount = 0;
        const skipped: string[] = [];

        for (const file of files) {
            if (!ALLOWED_EXTENSIONS.test(file.name)) {
                console.warn(`Skipping unsupported file type: ${file.name}`);
                skipped.push(`${file.name} (unsupported type)`);
                continue;
            }
            if (file.size > MAX_FILE_SIZE) {
                console.warn(`Skipping file too large (>${MAX_FILE_SIZE / 1024 / 1024} MB): ${file.name}`);
                skipped.push(`${file.name} (too large)`);
                continue;
            }
            try {
                const content = await file.text();

                const res = await fetch(`${API_BASE}/rag/upload`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        filename: file.name,
                        content: content,
                        force: true
                    }),
                });

                const data = await res.json();
                if (data.success) {
                    totalChunks += data.num_chunks || 0;
                    successCount++;
                } else {
                    console.error(`Failed to upload ${file.name}: ${data.message || data.detail || 'Unknown error'}`);
                }
            } catch (err) {
                console.error(`Failed to upload ${file.name}:`, err);
            }
        }

        let statusMsg = `✓ Indexed ${successCount}/${files.length} files (${totalChunks} chunks)`;
        if (skipped.length > 0) {
            statusMsg += ` — skipped: ${skipped.join(", ")}`;
        }
        setStatus(statusMsg);
        setIngesting(false);

        // Reset file input
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const handleIngest = async () => {
        if (!filePath) return;
        setIngesting(true);
        setStatus("Ingesting...");
        try {
            const res = await fetch(`${API_BASE}/rag/ingest`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ paths: [filePath], force: true }),
            });
            const data = await res.json();
            if (res.ok) {
                setStatus(`Indexed ${data.num_files} files (${data.num_chunks} chunks)`);
                setFilePath("");
            } else {
                setStatus(`Error: ${data.detail}`);
            }
        } catch (e) {
            setStatus("Ingest failed");
        } finally {
            setIngesting(false);
        }
    };

    const handleSearch = async () => {
        if (!query.trim()) return;
        setSearching(true);
        setResults([]); // Clear previous results
        try {
            console.log(`Searching for: '${query.trim()}'`);
            const res = await fetch(`${API_BASE}/rag/search`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query.trim(), limit: 5, method: "keyword" }),
            });
            const data = await res.json();
            console.log("Search results:", data);

            if (Array.isArray(data)) {
                setResults(data);
            } else {
                console.error("Invalid search response:", data);
                setResults([]);
            }
        } catch (e) {
            console.error("Search error:", e);
            setStatus("Search failed: Connection error");
        } finally {
            setSearching(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 border-t border-white/5 pt-4 mt-4">
            <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <span>Context Manager</span>
                    <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[9px]">RAG</span>
                </div>
                {isConnected === false && (
                    <span className="text-[9px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded animate-pulse">
                        Backend Offline
                    </span>
                )}
                {isConnected === true && (
                    <span className="text-[9px] text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded">
                        Connected
                    </span>
                )}

            </h3>

            {/* Suggestions Area */}
            {suggestions.length > 0 && (
                <div className="flex flex-col gap-2 mb-4 animate-fade-in">
                    <span className="text-[9px] text-blue-400 font-bold uppercase tracking-widest px-1">Suggested Files</span>
                    <div className="flex flex-wrap gap-2">
                        {suggestions.map((s, i) => (
                            <button
                                key={i}
                                onClick={() => onInsertContext(`[File: ${s.name}]\n(Reason: ${s.reason})`)}
                                className="group flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 hover:border-blue-500/40 rounded-full transition-all text-left"
                                title={`Add ${s.path} to context`}
                            >
                                <span className="text-[10px] text-blue-300 font-mono">{s.name}</span>
                                <span className="text-[9px] text-blue-400/60 group-hover:text-blue-400 opacity-60 group-hover:opacity-100 transition-opacity">
                                    +
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Stats Display */}
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

            {/* Drag & Drop Zone */}
            <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                className={`
                    relative flex flex-col items-center justify-center gap-2 p-4
                    border-2 border-dashed rounded-xl
                    transition-all duration-200
                    ${isDragging
                        ? "border-blue-500 bg-blue-500/10 scale-[1.02]"
                        : "border-white/10 bg-white/[0.02]"
                    }
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
                    // @ts-ignore - webkitdirectory is not in standard types but supported by browsers
                    webkitdirectory=""
                    // @ts-ignore - directory is also a non-standard but supported attribute
                    directory=""
                    onChange={handleDirectorySelect}
                    className="hidden"
                />

                {ingesting ? (
                    <div className="flex items-center gap-2 text-blue-400">
                        <span className="animate-spin">⏳</span>
                        <span className="text-xs">Indexing...</span>
                    </div>
                ) : (
                    <>
                        <div className={`text-2xl ${isDragging ? "scale-110" : ""} transition-transform`}>
                            📂
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
                            Or drag & drop (Project Context)
                        </div>
                    </>
                )}
            </div>

            {/* Status */}
            {status && (
                <div className={`text-[10px] px-2 py-1.5 rounded-lg ${status.startsWith("✓")
                    ? "bg-green-500/10 text-green-400"
                    : status.startsWith("Error")
                        ? "bg-red-500/10 text-red-400"
                        : "bg-zinc-800/50 text-zinc-400"
                    }`}>
                    {status}
                </div>
            )}

            {/* Legacy Path Input (Collapsed) */}
            <details className="group">
                <summary className="text-[10px] text-zinc-600 cursor-pointer hover:text-zinc-400 transition-colors">
                    ⚙️ Advanced: Index by path
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
                        onClick={handleIngest}
                        disabled={ingesting || !filePath}
                        className="w-full py-2 bg-zinc-800/50 hover:bg-zinc-700/50 text-xs font-medium text-zinc-300 rounded-lg disabled:opacity-50 transition-colors border border-white/5 flex items-center justify-center gap-2"
                    >
                        {ingesting ? <span className="animate-pulse">Indexing...</span> : "📂 Ingest Path"}
                    </button>
                </div>
            </details>

            {/* Search Section */}
            <div className="flex flex-col gap-2">
                <div className="flex gap-2">
                    <input
                        type="text"
                        className="flex-1 bg-black/30 p-2.5 rounded-lg text-xs border border-white/5 focus:border-blue-500/30 focus:outline-none transition-colors placeholder-zinc-600 font-mono"
                        placeholder="Search context..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    />
                    <button
                        onClick={handleSearch}
                        disabled={searching || !query}
                        className="px-3 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg text-xs hover:bg-blue-500/20 transition-all font-medium"
                    >
                        Search
                    </button>
                </div>

                {/* Results List */}
                <div className="flex flex-col gap-2 max-h-[180px] overflow-y-auto pr-1 custom-scrollbar">
                    {!searching && query && results.length === 0 && (
                        <div className="text-[10px] text-zinc-500 text-center py-4 bg-white/[0.02] rounded-lg border border-dashed border-white/5">
                            No results found for "{query}"
                        </div>
                    )}

                    {results.map((r, i) => (
                        <div key={i} className="group flex flex-col gap-1.5 p-3 bg-white/5 rounded-xl border border-white/5 hover:border-white/10 transition-all hover:bg-white/[0.07]">
                            <div className="flex justify-between items-center">
                                <span className="text-[10px] text-zinc-500 font-mono truncate max-w-[120px] bg-black/20 px-1.5 py-0.5 rounded">{r.source}</span>
                                <span className="text-[10px] text-green-400/80 font-mono bg-green-500/10 px-1.5 py-0.5 rounded">{(r.score * 100).toFixed(0)}%</span>
                            </div>
                            <div className="text-xs text-zinc-300 line-clamp-3 leading-relaxed opacity-80 group-hover:opacity-100">
                                {r.content}
                            </div>
                            <button
                                onClick={() => onInsertContext(r.content)}
                                className="mt-1 text-[10px] text-blue-300 hover:text-blue-200 text-left opacity-0 group-hover:opacity-100 transition-all flex items-center gap-1 font-medium"
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
