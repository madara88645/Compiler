import { toast } from "sonner";
import { formatSearchResultForPrompt, formatSearchScore } from "../../../lib/api/promptc";
import type { RagSearchResult } from "../../../lib/api/types";

type RagSearchPanelProps = {
    query: string;
    setQuery: (q: string) => void;
    searching: boolean;
    results: RagSearchResult[];
    onRunSearch: () => void;
    onInsertContext: (text: string) => void;
};

export default function RagSearchPanel({
    query,
    setQuery,
    searching,
    results,
    onRunSearch,
    onInsertContext,
}: RagSearchPanelProps) {
    return (
        <div className="flex flex-col gap-2">
            <div className="flex gap-2">
                <div className="relative flex-1">
                    <input
                        type="text"
                        aria-label="Search context..."
                        className="w-full bg-black/30 p-2.5 pr-8 rounded-lg text-xs border border-white/5 focus:border-blue-500/30 focus:outline-none transition-colors placeholder-zinc-600 font-mono"
                        placeholder="Search context..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && onRunSearch()}
                    />
                    {query && (
                        <button
                            type="button"
                            onClick={() => { setQuery(""); }}
                            aria-label="Clear search"
                            className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full flex items-center justify-center text-[10px] text-zinc-500 hover:text-zinc-300 hover:bg-white/5 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500"
                        >
                            ×
                        </button>
                    )}
                </div>
                <button
                    type="button"
                    onClick={onRunSearch}
                    disabled={searching || !query.trim()}
                    title={!query.trim() ? "Enter a query first to search" : "Search"}
                    className="px-3 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg text-xs hover:bg-blue-500/20 transition-all font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
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
                            type="button"
                            onClick={() => {
                                onInsertContext(formatSearchResultForPrompt(result));
                                toast.success("Snippet inserted into prompt");
                            }}
                            className="mt-1 text-[10px] text-blue-300 hover:text-blue-200 text-left opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500 rounded transition-all flex items-center gap-1 font-medium"
                        >
                            <span>+</span> Insert into Prompt
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}
