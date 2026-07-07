"use client";

import { useState } from "react";
import { copyToClipboard } from "../lib/copyToClipboard";

interface CopyButtonProps {
  text: string;
  className?: string;
  label?: string;
  variant?: "default" | "gray";
}

export default function CopyButton({
  text,
  className = "",
  label = "Copy to Clipboard",
  variant = "default",
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const success = await copyToClipboard(text);
    if (!success) return;
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const baseClasses = "p-3 rounded-xl shadow-lg transition-all hover:scale-105 active:scale-95 z-20 focus-visible:outline-none focus-visible:ring-2";
  const variantClasses =
    variant === "gray"
      ? "bg-zinc-700 hover:bg-zinc-600 text-white focus-visible:ring-zinc-500"
      : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20 focus-visible:ring-blue-500";

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`${baseClasses} ${variantClasses} ${className}`}
      title={copied ? "Copied!" : label}
      aria-label={copied ? "Copied" : label}
      aria-live="polite"
    >
      {copied ? (
        <>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span className="sr-only">Copied!</span>
        </>
      ) : (
        <>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
            <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
          </svg>
          <span className="sr-only">{label}</span>
        </>
      )}
    </button>
  );
}
