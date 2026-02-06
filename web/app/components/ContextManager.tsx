"use client";

import { useState } from "react";

type SearchResult = {
    content: string;
    source: string;
    score: number;
};

type ContextManagerProps = {
    onInsertContext: (text: string) => void;
};

export default function ContextManager({ onInsertContext }: ContextManagerProps) {
    const [ingesting, setIngesting] = useState(false);
    const [searching, setSearching] = useState(false);
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<SearchResult[]>([]);
    const [filePath, setFilePath] = useState("");
    const [status, setStatus] = useState("");

    const handleIngest = async () => {
        if (!filePath) return;
        setIngesting(true);
        setStatus("Ingesting...");
        try {
            const res = await fetch("http://127.0.0.1:8080/rag/ingest", {
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
        if (!query) return;
        setSearching(true);
        try {
            const res = await fetch("http://127.0.0.1:8080/rag/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, limit: 3, method: "hybrid" }),
            });
            const data = await res.json();
            setResults(data);
        } catch (e) {
            console.error(e);
        } finally {
            setSearching(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 border-t border-white/5 pt-4 mt-4">
            <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-2">
                <span>Context Manager</span>
                <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[9px]">RAG</span>
            </h3>

            {/* Ingest Section */}
            <div className="flex flex-col gap-2">
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
                    {ingesting ? <span className="animate-pulse">Indexing...</span> : "📂 Ingest Files"}
                </button>
                {status && <div className="text-[10px] text-zinc-500 truncate pl-1">{status}</div>}
            </div>

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
