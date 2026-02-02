"use client";

import { useState } from "react";

type SearchResult = {
    content: string;
    source: string;
    score: float;
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
        <div className="flex flex-col gap-4 border-t border-zinc-800 pt-4 mt-4">
            <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Context Manager (RAG)</h3>

            {/* Ingest Section */}
            <div className="flex flex-col gap-2">
                <input
                    type="text"
                    className="w-full bg-zinc-800 p-2 rounded text-xs border border-zinc-700"
                    placeholder="Path to file or folder..."
                    value={filePath}
                    onChange={(e) => setFilePath(e.target.value)}
                />
                <button
                    onClick={handleIngest}
                    disabled={ingesting || !filePath}
                    className="w-full py-1 bg-zinc-700 text-xs rounded hover:bg-zinc-600 disabled:opacity-50"
                >
                    {ingesting ? "Indexing..." : "📂 Ingest Files"}
                </button>
                {status && <div className="text-[10px] text-zinc-500 truncate">{status}</div>}
            </div>

            {/* Search Section */}
            <div className="flex flex-col gap-2">
                <div className="flex gap-2">
                    <input
                        type="text"
                        className="flex-1 bg-zinc-800 p-2 rounded text-xs border border-zinc-700"
                        placeholder="Search context..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    />
                    <button
                        onClick={handleSearch}
                        disabled={searching || !query}
                        className="px-2 bg-blue-900/40 text-blue-400 border border-blue-900 rounded text-xs hover:bg-blue-900/60"
                    >
                        Search
                    </button>
                </div>

                {/* Results List */}
                <div className="flex flex-col gap-2 max-h-[200px] overflow-y-auto">
                    {results.map((r, i) => (
                        <div key={i} className="group flex flex-col gap-1 p-2 bg-zinc-800/50 rounded border border-zinc-800 hover:border-zinc-700">
                            <div className="flex justify-between items-center">
                                <span className="text-[10px] text-zinc-500 font-mono truncate max-w-[120px]">{r.source}</span>
                                <span className="text-[10px] text-zinc-600">{(r.score * 100).toFixed(0)}%</span>
                            </div>
                            <div className="text-xs text-zinc-300 line-clamp-3 leading-relaxed">
                                {r.content}
                            </div>
                            <button
                                onClick={() => onInsertContext(r.content)}
                                className="mt-1 text-[10px] text-blue-400 hover:underline text-left opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                + Insert into Prompt
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
