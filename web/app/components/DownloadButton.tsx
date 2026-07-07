"use client";

import { useState } from "react";
import { toast } from "sonner";
import { downloadFile } from "../lib/downloadFile";

interface DownloadButtonProps {
  content: string;
  filename: string;
  mimeType?: string;
  className?: string;
  label?: string;
  variant?: "default" | "gray";
}

export default function DownloadButton({
  content,
  filename,
  mimeType = "text/plain",
  className = "",
  label = "Download",
  variant = "gray",
}: DownloadButtonProps) {
  const [downloaded, setDownloaded] = useState(false);

  const handleDownload = () => {
    downloadFile(content, filename, mimeType);
    setDownloaded(true);
    toast.success(`Downloaded ${filename}`);
    setTimeout(() => setDownloaded(false), 2000);
  };

  const baseClasses = "p-3 rounded-xl shadow-lg transition-all hover:scale-105 active:scale-95 z-20 focus-visible:outline-none focus-visible:ring-2";
  const variantClasses =
    variant === "gray"
      ? "bg-zinc-700 hover:bg-zinc-600 text-white focus-visible:ring-zinc-500"
      : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20 focus-visible:ring-blue-500";

  return (
    <button
      type="button"
      onClick={handleDownload}
      className={`${baseClasses} ${variantClasses} ${className}`}
      title={downloaded ? "Downloaded!" : `${label} (${filename})`}
      aria-label={downloaded ? "Downloaded" : `${label} ${filename}`}
      aria-live="polite"
    >
      {downloaded ? (
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
          <span className="sr-only">Downloaded!</span>
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
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <span className="sr-only">{label}</span>
        </>
      )}
    </button>
  );
}
