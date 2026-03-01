"use client";

import { useState } from "react";

interface InfoButtonProps {
    title?: string;
    description: string;
}

export default function InfoButton({ title, description }: InfoButtonProps) {
    const [showTooltip, setShowTooltip] = useState(false);

    return (
        <div className="relative inline-block ml-2 group">
            <button
                type="button"
                className="w-4 h-4 rounded-full bg-neutral-800 border border-neutral-700 text-neutral-400 text-[10px] font-bold flex items-center justify-center hover:bg-neutral-700 hover:text-white transition-colors cursor-help"
                onMouseEnter={() => setShowTooltip(true)}
                onMouseLeave={() => setShowTooltip(false)}
                onClick={(e) => {
                    e.preventDefault();
                    setShowTooltip(!showTooltip);
                }}
                aria-label="More information"
            >
                ?
            </button>

            {showTooltip && (
                <div className="absolute z-50 w-64 p-3 mt-2 text-xs font-normal text-left text-neutral-300 bg-neutral-900 border border-neutral-700 rounded-md shadow-xl -left-2 top-full break-words">
                    <div className="absolute w-2 h-2 bg-neutral-900 border-l border-t border-neutral-700 transform rotate-45 -top-1 left-3"></div>
                    {description}
                </div>
            )}
        </div>
    );
}
