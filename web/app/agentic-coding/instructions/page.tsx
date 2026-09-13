"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { FileSearch, Plus, Upload, X } from "lucide-react";
import { apiJson, buildGeneratorApiHeaders, describeRequestError } from "@/config";
import { copyToClipboard } from "../../lib/copyToClipboard";
import { downloadFile } from "../../lib/downloadFile";
import { buildPackZip } from "../../lib/packZip";
import { isInstructionReview, type InstructionFile, type InstructionReview } from "./types";

const MAX_FILES = 12;
const MAX_CHARS = 120000;
const SAMPLE = "# Project rules\n\n- Keep changes small.\n- Keep changes small.\n- Never log credentials.\n\n## Build\n\nSee [build guide](docs/build.md).\n";
const fieldClass = "w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-cyan-300/60 focus:ring-2 focus:ring-cyan-300/10";

export default function InstructionReviewPage() {
  const [files, setFiles] = useState<InstructionFile[]>([{ path: "CLAUDE.md", content: "" }]);
  const [knownFiles, setKnownFiles] = useState("");
  const [result, setResult] = useState<InstructionReview | null>(null);
  const [selectedPath, setSelectedPath] = useState("");
  const [acceptedPaths, setAcceptedPaths] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const inFlight = useRef(false);
  const chars = files.reduce((total, file) => total + file.content.length, 0);
  const locked = busy || uploading;
  const current = result?.files.find((file) => file.path === selectedPath) ?? result?.files[0];

  const clearResult = () => {
    setResult(null);
    setAcceptedPaths(new Set());
    setNotice(null);
    setError(null);
  };
  const changeFile = (index: number, key: keyof InstructionFile, value: string) => {
    setFiles((currentFiles) => currentFiles.map((file, position) => position === index ? { ...file, [key]: value } : file));
    clearResult();
  };

  const upload = async (selected: FileList | null) => {
    if (!selected?.length || locked) return;
    setUploading(true);
    setError(null);
    try {
      const incoming = Array.from(selected);
      const base = files.length === 1 && !files[0].content.trim() ? [] : files;
      if (base.length + incoming.length > MAX_FILES) throw new Error("Review up to 12 files at a time.");
      if (incoming.some((file) => file.size > MAX_CHARS * 4)) throw new Error("One of these files is too large. Choose smaller instruction files.");
      if (incoming.some((file) => !/\.(md|mdc|txt)$/i.test(file.name))) throw new Error("Choose Markdown, MDC or plain text instruction files.");
      const loaded = await Promise.all(incoming.map(async (file) => ({ path: file.name, content: await file.text() })));
      const next = [...base, ...loaded];
      if (next.reduce((total, file) => total + file.content.length, 0) > MAX_CHARS) throw new Error("The combined files exceed 120,000 characters.");
      setFiles(next);
      clearResult();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The files could not be read.");
    } finally {
      setUploading(false);
      if (uploadRef.current) uploadRef.current.value = "";
    }
  };

  const analyze = async () => {
    if (inFlight.current || uploading) return;
    if (!files.some((file) => file.content.trim())) { setError("Paste or upload at least one instruction file."); return; }
    if (chars > MAX_CHARS) { setError("The combined files exceed 120,000 characters."); return; }
    const paths = files.map((file) => file.path.trim());
    if (paths.some((path) => !path) || new Set(paths).size !== paths.length) {
      setError("Give each file a unique relative name, such as CLAUDE.md or .claude/rules/testing.md."); return;
    }
    inFlight.current = true;
    setBusy(true);
    clearResult();
    try {
      const response = await apiJson<unknown>("/instruction-review/analyze", {
        method: "POST",
        headers: buildGeneratorApiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          files: files.map((file) => ({ ...file, path: file.path.trim() })),
          ...(knownFiles.trim() ? { known_repo_files: knownFiles.split(/\r?\n/).map((path) => path.trim()).filter(Boolean) } : {}),
        }),
      });
      if (!isInstructionReview(response)) throw new Error("The review returned an unexpected response. Your original files are unchanged; try again.");
      setResult(response);
      setSelectedPath(response.files[0].path);
    } catch (err) {
      setError(describeRequestError(err, { fallback: "The instructions could not be reviewed. Try again." }));
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  };

  return <main className="min-h-full bg-[#07090d] p-4 text-zinc-300 sm:p-8">
    <div className="mx-auto max-w-6xl">
      <Link href="/agentic-coding" className="text-sm text-cyan-300 hover:underline">← Agentic Coding / Projects</Link>
      <header className="my-6 flex items-start gap-3">
        <FileSearch className="mt-1 shrink-0 text-cyan-300" aria-hidden="true" />
        <div><h1 className="text-2xl font-semibold text-white">Review instructions</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">Find repeated rules, possible conflicts and outdated references. Compare suggested changes before using them in your project.</p>
          <p className="mt-2 text-xs text-zinc-500">Rule-based checks; no LLM call. Submitted text is sent to this app&apos;s backend for analysis. Your repository files are never changed.</p>
        </div>
      </header>
      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-label="Instruction files" className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" disabled={locked || files.length >= MAX_FILES} onClick={() => {
              setFiles((currentFiles) => [...currentFiles, { path: "", content: "" }]); clearResult();
            }} className="rounded-lg border border-white/15 px-3 py-2 text-sm disabled:opacity-40"><Plus size={14} className="mr-1 inline" aria-hidden="true" />Add file</button>
            <button type="button" disabled={locked} onClick={() => uploadRef.current?.click()} className="rounded-lg border border-white/15 px-3 py-2 text-sm"><Upload size={14} className="mr-1 inline" aria-hidden="true" />Upload files</button>
            <input ref={uploadRef} type="file" multiple accept=".md,.mdc,.txt,text/plain,text/markdown" aria-label="Upload instruction files" className="hidden" onChange={(event) => void upload(event.target.files)} />
            {files.length === 1 && !files[0].content && <button type="button" disabled={locked} onClick={() => { setFiles([{ path: "CLAUDE.md", content: SAMPLE }]); clearResult(); }} className="px-2 py-2 text-xs text-cyan-300">Try an example</button>}
          </div>
          {files.map((file, index) => <div key={index} className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.025] p-4">
            <div className="flex items-end gap-2"><label className="min-w-0 flex-1 text-xs text-zinc-400">File name
              <input aria-label={`File ${index + 1} name`} value={file.path} disabled={locked} maxLength={240} placeholder=".claude/rules/testing.md" onChange={(event) => changeFile(index, "path", event.target.value)} className={`${fieldClass} mt-1`} />
            </label>
              {files.length > 1 && <button type="button" disabled={locked} aria-label={`Remove file ${index + 1}`} onClick={() => { setFiles((items) => items.filter((_, position) => position !== index)); clearResult(); }} className="rounded-lg p-2 text-zinc-400 hover:text-rose-300"><X size={18} aria-hidden="true" /></button>}
            </div>
            <label className="block text-xs text-zinc-400">Instructions
              <textarea aria-label={`File ${index + 1} contents`} rows={10} value={file.content} disabled={locked} maxLength={MAX_CHARS} onChange={(event) => changeFile(index, "content", event.target.value)} placeholder="Paste the original instructions here…" className={`${fieldClass} mt-1 font-mono leading-6`} />
            </label>
          </div>)}
          <details className="rounded-xl border border-white/10 p-3 text-sm">
            <summary className="cursor-pointer text-zinc-300">Check references against a file list (optional)</summary>
            <p className="my-2 text-xs leading-5 text-zinc-400">Paste the complete list of repository-relative file names, one per line. Without a list, references remain unverified. This does not scan your repository.</p>
            <textarea aria-label="Known repository files" rows={4} disabled={locked} value={knownFiles} onChange={(event) => { setKnownFiles(event.target.value); clearResult(); }} placeholder="README.md&#10;docs/build.md" className={`${fieldClass} font-mono`} />
          </details>
          <p className="text-xs text-zinc-500">{files.length}/{MAX_FILES} files · {chars.toLocaleString()}/120,000 characters</p>
          {error && <p role="alert" className="rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
          <button type="button" disabled={locked} onClick={() => void analyze()} className="w-full rounded-xl bg-cyan-300 px-4 py-3 font-medium text-zinc-950 disabled:opacity-50">{busy ? "Reviewing…" : uploading ? "Reading files…" : "Review instructions"}</button>
        </section>
        <section aria-label="Review results" className="min-w-0">
          {!result ? <div className="rounded-2xl border border-dashed border-white/15 p-6 text-sm leading-6 text-zinc-400">
            <h2 className="mb-2 font-semibold text-white">Keep the rules that matter</h2>
            Only exact repeated rules in the same scope can receive a cleanup suggestion. Possible conflicts need your judgment. Moving text into imported files alone does not guarantee a smaller context.
          </div> : <div className="space-y-4">
            <div className="rounded-xl border border-cyan-300/20 bg-cyan-300/5 p-4">
              <h2 className="font-semibold text-white">Review complete</h2>
              <p className="mt-1 text-sm">{result.files.length} files · {result.findings.length} findings · {result.files.filter((file) => file.original !== file.suggested).length} suggested file changes</p>
              <p className="mt-2 text-xs text-zinc-400">These checks do not prove that an agent will follow the instructions. Original inputs stay unchanged.</p>
            </div>
            {!result.findings.length && <p className="text-sm text-zinc-400">No issues found by these checks. This is not a complete semantic review.</p>}
            <ul aria-label="Findings" className="max-h-72 space-y-2 overflow-y-auto">
              {result.findings.map((finding, index) => <li key={index} className="rounded-xl border border-white/10 p-3">
                <p className="text-xs font-medium text-cyan-200">{finding.path}:{finding.line} · {finding.severity}</p>
                <p className="mt-1 text-sm leading-5">{finding.message}</p>
                {!!finding.related?.length && <p className="mt-1 text-xs text-zinc-500">Related: {finding.related.map((item) => `${item.path}:${item.line}`).join(", ")}</p>}
              </li>)}
            </ul>
            <label className="block text-sm">Compare file
              <select className={`${fieldClass} mt-2`} aria-label="Compare file" value={current?.path ?? ""} onChange={(event) => { setSelectedPath(event.target.value); setNotice(null); }}>
                {result.files.map((file) => <option key={file.path} value={file.path}>{file.path}</option>)}
              </select>
            </label>
            {current && <div className="space-y-3 rounded-2xl border border-white/10 p-4">
              <h3 className="font-medium text-white">Proposed changes</h3>
              <pre aria-label="Suggested changes" className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-black/40 p-3 font-mono text-xs leading-5 text-zinc-300">{current.diff || "No changes suggested for this file."}</pre>
              <details><summary className="cursor-pointer text-sm">Original file</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs">{current.original}</pre></details>
              {current.original !== current.suggested && <label className="flex items-start gap-2 text-sm text-zinc-200">
                <input type="checkbox" checked={acceptedPaths.has(current.path)} onChange={(event) => setAcceptedPaths((paths) => { const next = new Set(paths); if (event.target.checked) next.add(current.path); else next.delete(current.path); return next; })} className="mt-1" />
                Use the suggested version for this download
              </label>}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => {
                  const content = acceptedPaths.has(current.path) ? current.suggested : current.original;
                  if (current.path.includes("/")) downloadFile(buildPackZip([{ path: current.path, content }]), "reviewed-instructions.zip");
                  else downloadFile(content, current.path, "text/markdown");
                }} className="rounded-lg bg-cyan-300 px-3 py-2 text-sm font-medium text-zinc-950">Download {acceptedPaths.has(current.path) ? "suggested" : "original"} file</button>
                <button type="button" onClick={async () => { if (await copyToClipboard(acceptedPaths.has(current.path) ? current.suggested : current.original)) setNotice("Copied the selected version."); }} className="rounded-lg border border-white/15 px-3 py-2 text-sm">Copy {acceptedPaths.has(current.path) ? "suggested" : "original"}</button>
              </div>
              <p className="break-all text-xs text-zinc-400">Destination in your project: {current.path}{current.path.includes("/") ? ". Downloads as a ZIP to preserve its folders." : "."}</p>
              {notice && <p role="status" className="text-xs text-cyan-200">{notice}</p>}
            </div>}
          </div>}
        </section>
      </div>
    </div>
  </main>;
}
