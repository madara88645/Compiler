"use client";

import { useEffect, useState } from "react";
// Try named import which is standard for the typed package
import { diff_match_patch } from "diff-match-patch";

interface DiffViewerProps {
    oldText: string;
    newText: string;
}

export default function DiffViewer({ oldText, newText }: DiffViewerProps) {
    const [htmlContent, setHtmlContent] = useState<string>("");

    useEffect(() => {
        // Check if diff_match_patch is available
        if (typeof diff_match_patch !== 'undefined') {
            const dmp = new diff_match_patch();
            const diffs = dmp.diff_main(oldText, newText);
            dmp.diff_cleanupSemantic(diffs);
            const html = dmp.diff_prettyHtml(diffs);
            setHtmlContent(html);
        } else {
            // Fallback or retry logic if import mechanism differs
            console.error("diff-match-patch not loaded correctly");
            setHtmlContent("<div>Error loading diff tool</div>");
        }
    }, [oldText, newText]);

    return (
        <div className="w-full h-full bg-black/20 rounded-xl border border-white/5 overflow-hidden flex flex-col">
            <div className="px-4 py-2 border-b border-white/5 bg-white/5 flex items-center justify-between shrink-0">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Semantic Diff</span>
                <div className="flex gap-3 text-[10px] font-mono">
                    <span className="flex items-center gap-1.5"><div className="w-2 h-2 bg-green-500/20 border border-green-500/50 rounded-sm"></div> Added</span>
                    <span className="flex items-center gap-1.5"><div className="w-2 h-2 bg-red-500/20 border border-red-500/50 rounded-sm"></div> Removed</span>
                </div>
            </div>
            <div
                className="p-4 font-mono text-xs md:text-sm text-zinc-300 overflow-auto whitespace-pre-wrap leading-relaxed diff-content flex-1"
                dangerouslySetInnerHTML={{ __html: htmlContent }}
            />
            <style jsx global>{`
        .diff-content ins {
          background-color: rgba(16, 185, 129, 0.2);
          text-decoration: none;
          color: #6ee7b7;
          border-radius: 2px;
          padding: 0 2px;
          border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .diff-content del {
          background-color: rgba(239, 68, 68, 0.2);
          text-decoration: none;
          color: #fca5a5;
          border-radius: 2px;
          padding: 0 2px;
          border: 1px solid rgba(239, 68, 68, 0.3);
          opacity: 0.8;
        }
      `}</style>
        </div>
    );
}
