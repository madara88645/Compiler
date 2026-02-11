"use client";

import { useEffect, useState } from "react";
import { diff_match_patch, DIFF_INSERT, DIFF_DELETE, DIFF_EQUAL } from "diff-match-patch";

interface DiffViewerProps {
    oldText: string;
    newText: string;
}

/**
 * Custom HTML builder for diffs — avoids diff_prettyHtml's inline styles
 * which clash with our dark theme (light bg + light text = unreadable).
 */
function buildDarkThemeHtml(diffs: [number, string][]): string {
    const parts: string[] = [];
    for (const [op, text] of diffs) {
        const escaped = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\n/g, "<br>");

        switch (op) {
            case DIFF_INSERT:
                parts.push(`<span class="diff-added">${escaped}</span>`);
                break;
            case DIFF_DELETE:
                parts.push(`<span class="diff-removed">${escaped}</span>`);
                break;
            case DIFF_EQUAL:
            default:
                parts.push(`<span class="diff-equal">${escaped}</span>`);
                break;
        }
    }
    return parts.join("");
}

export default function DiffViewer({ oldText, newText }: DiffViewerProps) {
    const [htmlContent, setHtmlContent] = useState<string>("");

    useEffect(() => {
        if (typeof diff_match_patch !== "undefined") {
            const dmp = new diff_match_patch();
            const diffs = dmp.diff_main(oldText, newText);
            dmp.diff_cleanupSemantic(diffs);
            // Use our custom builder instead of diff_prettyHtml
            const html = buildDarkThemeHtml(diffs);
            setHtmlContent(html);
        } else {
            console.error("diff-match-patch not loaded correctly");
            setHtmlContent("<div>Error loading diff tool</div>");
        }
    }, [oldText, newText]);

    return (
        <div className="w-full h-full bg-black/20 rounded-xl border border-white/5 overflow-hidden flex flex-col">
            <div className="px-4 py-2 border-b border-white/5 bg-white/5 flex items-center justify-between shrink-0">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Semantic Diff</span>
                <div className="flex gap-3 text-[10px] font-mono">
                    <span className="flex items-center gap-1.5"><div className="w-2 h-2 bg-emerald-500/30 border border-emerald-500/60 rounded-sm"></div> Added</span>
                    <span className="flex items-center gap-1.5"><div className="w-2 h-2 bg-red-500/30 border border-red-500/60 rounded-sm"></div> Removed</span>
                </div>
            </div>
            <div
                className="p-4 font-mono text-xs md:text-sm text-zinc-300 overflow-auto whitespace-pre-wrap leading-relaxed diff-content flex-1"
                dangerouslySetInnerHTML={{ __html: htmlContent }}
            />
            <style jsx global>{`
                .diff-content .diff-added {
                    background-color: rgba(16, 185, 129, 0.15);
                    color: #6ee7b7;
                    border-radius: 3px;
                    padding: 1px 4px;
                    border-bottom: 1px solid rgba(16, 185, 129, 0.4);
                }
                .diff-content .diff-removed {
                    background-color: rgba(239, 68, 68, 0.15);
                    color: #fca5a5;
                    border-radius: 3px;
                    padding: 1px 4px;
                    text-decoration: line-through;
                    text-decoration-color: rgba(239, 68, 68, 0.4);
                    opacity: 0.7;
                }
                .diff-content .diff-equal {
                    color: #a1a1aa;
                }
            `}</style>
        </div>
    );
}
