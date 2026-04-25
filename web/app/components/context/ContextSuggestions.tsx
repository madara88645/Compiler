import type { ContextSuggestion } from "../../../lib/api/types";

type ContextSuggestionsProps = {
    suggestions: ContextSuggestion[];
    onInsertContext: (text: string) => void;
};

export default function ContextSuggestions({ suggestions, onInsertContext }: ContextSuggestionsProps) {
    if (suggestions.length === 0) return null;

    return (
        <div className="flex flex-col gap-2 mb-4 animate-fade-in">
            <span className="text-[9px] text-blue-400 font-bold uppercase tracking-widest px-1">Suggested Files</span>
            <div className="flex flex-wrap gap-2">
                {suggestions.map((suggestion) => (
                    <button
                        key={suggestion.path}
                        type="button"
                        onClick={() => onInsertContext(`[File: ${suggestion.name}]\n(Reason: ${suggestion.reason})`)}
                        className="group flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 hover:border-blue-500/40 rounded-full transition-all text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                        title={`Add ${suggestion.path} to context`}
                        aria-label={`Add ${suggestion.path} to context`}
                    >
                        <span className="text-[10px] text-blue-300 font-mono">{suggestion.name}</span>
                        <span className="text-[9px] text-blue-400/60 group-hover:text-blue-400 opacity-60 group-hover:opacity-100 transition-opacity">
                            +
                        </span>
                    </button>
                ))}
            </div>
        </div>
    );
}
