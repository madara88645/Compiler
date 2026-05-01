"use client";

import { useState, useEffect, useRef } from "react";
import { apiFetch } from "@/config";

type SkillFormat = "langchain-tool" | "claude-tool-use";
type OutputTab = "python" | "json";

interface SkillExportResult {
    python_code: string | null;
    json_config: string | null;
}

interface ExportPanelProps {
    skillDefinition: string | null;
}

const FORMATS: {
    id: SkillFormat;
    label: string;
    color: string;
    activeColor: string;
}[] = [
    {
        id: "langchain-tool",
        label: "LangChain Tool",
        color: "text-zinc-400 border-transparent hover:border-green-500/40 hover:text-green-300",
        activeColor: "text-green-300 border-green-500/60 bg-green-500/10",
    },
    {
        id: "claude-tool-use",
        label: "Claude tool_use",
        color: "text-zinc-400 border-transparent hover:border-orange-500/40 hover:text-orange-300",
        activeColor: "text-orange-300 border-orange-500/60 bg-orange-500/10",
    },
];

export default function SkillExportPanel({
    skillDefinition,
}: ExportPanelProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [format, setFormat] = useState<SkillFormat>("langchain-tool");
    const [outputTab, setOutputTab] = useState<OutputTab>("python");
    const [cache, setCache] = useState<
        Partial<Record<SkillFormat, SkillExportResult>>
    >({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);
    const prevDefRef = useRef<string | null>(null);

    // Reset cache when skill definition changes
    useEffect(() => {
        if (skillDefinition !== prevDefRef.current) {
            prevDefRef.current = skillDefinition;
            setCache({});
            setError(null);
        }
    }, [skillDefinition]);

    const currentResult = cache[format] ?? null;

    const fetchExport = async (fmt: SkillFormat) => {
        if (!skillDefinition) return;
        if (cache[fmt]) return;

        setLoading(true);
        setError(null);
        try {
            const res = await apiFetch("/skills-generator/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    skill_definition: skillDefinition,
                    format: fmt,
                    output_type: "both",
                }),
            });

            if (!res.ok) {
                const body = await res
                    .json()
                    .catch(() => ({ detail: res.statusText }));
                throw new Error(body.detail ?? `Export failed (${res.status})`);
            }

            const data: SkillExportResult = await res.json();
            setCache((prev) => ({ ...prev, [fmt]: data }));
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Export failed");
        } finally {
            setLoading(false);
        }
    };

    const handleFormatClick = (fmt: SkillFormat) => {
        setFormat(fmt);
        fetchExport(fmt);
        // Reset output tab to a valid default for each format
        if (fmt === "claude-tool-use") setOutputTab("json");
        else setOutputTab("python");
    };

    const handleToggle = () => {
        const next = !isOpen;
        setIsOpen(next);
        if (next && !cache[format]) {
            fetchExport(format);
        }
    };

    const handleCopy = () => {
        const text =
            outputTab === "python"
                ? currentResult?.python_code
                : currentResult?.json_config;
        if (text) {
            navigator.clipboard.writeText(text).then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            });
        }
    };

    const outputTabs: { id: OutputTab; label: string }[] =
        format === "claude-tool-use"
            ? [
                  { id: "json", label: "JSON Config" },
                  { id: "python", label: "Python Tool" },
              ]
            : [
                  { id: "python", label: "Python Tool" },
                  { id: "json", label: "JSON Schema" },
              ];

    const codeContent =
        outputTab === "python"
            ? currentResult?.python_code
            : currentResult?.json_config;

    if (!skillDefinition) return null;

    return (
        <div className="mt-6 border-t border-white/5 pt-4">
            {/* Toggle header */}
            <button
                type="button"
                onClick={handleToggle}
                aria-expanded={isOpen}
                aria-controls="export-panel-content"
                className="w-full flex items-center justify-between px-2 py-1 group"
            >
                <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-zinc-400 uppercase tracking-widest group-hover:text-zinc-200 transition-colors">
                        Export
                    </span>
                    <span className="text-[10px] text-zinc-600 font-mono">
                        → framework code
                    </span>
                </div>
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className={`text-zinc-500 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
                >
                    <path d="m6 9 6 6 6-6" />
                </svg>
            </button>

            {isOpen && (
                <div
                    id="export-panel-content"
                    className="mt-3 rounded-2xl border border-white/8 bg-black/30 overflow-hidden"
                >
                    {/* Format tabs */}
                    <div className="flex gap-1 p-3 border-b border-white/5">
                        {FORMATS.map((f) => (
                            <button
                                type="button"
                                key={f.id}
                                onClick={() => handleFormatClick(f.id)}
                                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                                    format === f.id ? f.activeColor : f.color
                                }`}
                            >
                                {f.label}
                            </button>
                        ))}
                    </div>

                    {/* Output type tabs */}
                    <div className="flex gap-1 px-3 pt-3">
                        {outputTabs.map((tab) => (
                            <button
                                type="button"
                                key={tab.id}
                                onClick={() => setOutputTab(tab.id)}
                                className={`px-3 py-1 text-[11px] font-mono rounded-md transition-all ${
                                    outputTab === tab.id
                                        ? "bg-white/10 text-zinc-100"
                                        : "text-zinc-500 hover:text-zinc-300"
                                }`}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Code area */}
                    <div className="relative p-3">
                        {loading ? (
                            <div className="flex items-center justify-center h-24 text-zinc-500 text-xs animate-pulse">
                                Generating export...
                            </div>
                        ) : error ? (
                            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-300">
                                {error}
                            </div>
                        ) : codeContent ? (
                            <div className="relative group/code">
                                <pre className="overflow-x-auto overflow-y-auto max-h-72 text-[11px] leading-relaxed font-mono text-zinc-300 bg-black/40 rounded-xl p-4 border border-white/5 whitespace-pre">
                                    <code>{codeContent}</code>
                                </pre>
                                <button
                                    type="button"
                                    onClick={handleCopy}
                                    className="absolute top-3 right-3 opacity-0 group-hover/code:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 transition-opacity bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-2.5 py-1.5 rounded-lg text-[10px] font-medium flex items-center gap-1.5 border border-white/10"
                                    aria-label="Copy code"
                                >
                                    {copied ? (
                                        <>
                                            <svg
                                                xmlns="http://www.w3.org/2000/svg"
                                                width="11"
                                                height="11"
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="currentColor"
                                                strokeWidth="2.5"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                            >
                                                <path d="M20 6 9 17l-5-5" />
                                            </svg>
                                            Copied!
                                        </>
                                    ) : (
                                        <>
                                            <svg
                                                xmlns="http://www.w3.org/2000/svg"
                                                width="11"
                                                height="11"
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="currentColor"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                            >
                                                <rect
                                                    width="14"
                                                    height="14"
                                                    x="8"
                                                    y="8"
                                                    rx="2"
                                                    ry="2"
                                                />
                                                <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
                                            </svg>
                                            Copy
                                        </>
                                    )}
                                </button>
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-16 text-zinc-600 text-xs">
                                Select a format above to generate export code
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
