"use client";

import { useState } from "react";
import { API_BASE } from "@/config";
import InfoButton from "../components/InfoButton";
import ContextManager from "../components/ContextManager";

export default function SkillsGenerator() {
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!description.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/skills-generator/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description }),
      });

      if (!res.ok) {
        throw new Error(`API Error: ${res.status}`);
      }

      const data = await res.json();
      setResult(data.skill_definition);
    } catch (e: any) {
      setError(e.message || "Failed to generate skill");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (result) {
      navigator.clipboard.writeText(result);
    }
  };

  return (
    <main className="flex h-screen flex-col items-center justify-center p-4 md:p-8 relative overflow-hidden bg-[#050505]">
      {/* Ambient Background */}
      <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] rounded-full bg-yellow-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] rounded-full bg-orange-600/10 blur-[120px] pointer-events-none" />

      {/* Main Container */}
      <div className="glass w-full max-w-7xl h-full max-h-[90vh] rounded-3xl flex flex-col shadow-2xl overflow-hidden animate-fade-in ring-1 ring-white/10 bg-black/40 backdrop-blur-xl">

        {/* Header */}
        <header className="border-b border-white/5 bg-black/20 p-4 flex items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 bg-gradient-to-br from-yellow-600 to-orange-600 rounded-xl flex items-center justify-center font-bold text-white shadow-lg shadow-yellow-500/20">
                ⚡
              </div>
              <div>
                <h1 className="font-semibold text-lg tracking-tight text-white">Skills Generator</h1>
                <div className="text-[10px] text-zinc-400 font-mono tracking-wider uppercase opacity-70">
                  Capability Architect
                </div>
              </div>
            </div>
            <InfoButton
              description="Describe a capability, and this tool will generate a structured Tool/Skill definition (with input/output schemas) that can be integrated into your AI agents."
            />
          </div>
        </header>

        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          {/* Left Panel: Input */}
          <div className="w-full md:w-[35%] p-5 flex flex-col gap-5 border-r border-white/5 bg-black/10">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300">Skill Description</label>
              <p className="text-xs text-zinc-500">
                Describe the skill's purpose, inputs, and expected behavior.
              </p>
            </div>

            <div className="flex-1 flex flex-col relative group">
              <textarea
                className="flex-1 w-full bg-black/20 p-5 rounded-2xl border border-white/10 resize-none focus:outline-none focus:ring-1 focus:ring-yellow-500/50 font-mono text-sm leading-relaxed text-zinc-200 placeholder-zinc-600 transition-all shadow-inner"
                placeholder="e.g., 'A skill that parses JSON and validates schemas' or 'Fetch and summarize web pages'"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <button
              onClick={handleGenerate}
              disabled={loading || !description.trim()}
              className="w-full px-4 py-3 text-sm font-bold text-white rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-500 hover:to-orange-500 shadow-yellow-500/20"
            >
              {loading ? (
                <span className="animate-pulse">Forging Skill...</span>
              ) : (
                <>Generate Skill <span className="group-hover:translate-x-0.5 transition-transform">→</span></>
              )}
            </button>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-300">
                {error}
              </div>
            )}

            {/* Context Manager */}
            <ContextManager
              onInsertContext={(text) => setDescription(prev => prev + "\n\n---\nContext:\n" + text)}
            />
          </div>

          {/* Right Panel: Output */}
          <div className="w-full md:w-[65%] flex flex-col bg-black/20 relative">
            {result ? (
              <div className="flex-1 p-0 overflow-hidden relative group bg-black/20 flex flex-col">
                <div className="flex border-b border-white/5 px-4 pt-4 gap-2">
                  <button className="px-4 py-2 text-[13px] font-medium rounded-t-lg text-white bg-white/5 border-t border-x border-white/5 relative">
                    Skill Definition
                  </button>
                </div>

                <div className="relative flex-1">
                  <textarea
                    className="w-full h-full bg-transparent p-6 font-mono text-sm text-zinc-300 resize-none focus:outline-none leading-relaxed selection:bg-yellow-500/30"
                    readOnly
                    value={result}
                  />

                  <button
                    onClick={copyToClipboard}
                    className="absolute bottom-6 right-6 bg-yellow-600 hover:bg-yellow-500 text-white p-3 rounded-xl shadow-lg shadow-yellow-500/20 transition-all hover:scale-105 active:scale-95 z-20 flex items-center gap-2"
                    title="Copy to Clipboard"
                  >
                    <span className="text-xs font-bold">Copy Markdown</span>
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-zinc-600 gap-6 p-10 text-center opacity-60">
                <div className="relative group">
                  <div className="absolute inset-0 bg-yellow-500/30 blur-[40px] rounded-full group-hover:bg-yellow-500/50 transition-all duration-700" />
                  <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-zinc-800 to-black border border-white/10 flex items-center justify-center shadow-2xl skew-y-3 group-hover:skew-y-0 transition-transform duration-500">
                    <span className="text-4xl filter drop-shadow-[0_0_10px_rgba(255,255,255,0.3)]">⚡</span>
                  </div>
                </div>
                <div className="max-w-xs space-y-2">
                  <h3 className="text-zinc-200 font-medium tracking-wide">Skill Forge</h3>
                  <p className="text-sm text-zinc-500">
                    Define a capability to generate a robust, modular skill definition for your AI agents.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
